"""Deterministic, free, LLM-independent safety pre-screen (Section 2
principle 3, Section 4.4.6).

Runs on every inbound message before anything reaches an LLM. This is
plain pattern matching, not a model — it costs nothing, it can't be
talked out of flagging something, and it's the first line of defense
against prompt injection and scams even when `ANTHROPIC_API_KEY` is
unset and the Triage agent is running on the free stub provider.

It complements, never replaces, LLM-based triage: a message that gets
past this screen can still be flagged `low_confidence` by the Triage
agent itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Section 2 principle 3: "ignore previous instructions", "as the
# assistant you must…" style phrases aimed at an AI reading the message.
_INJECTION_PATTERNS = [
    re.compile(
        r"\bignore\s+(?:all\s+|any\s+|your\s+|these\s+|the\s+)?(?:previous|prior|above)\s+instructions?\b",
        re.I,
    ),
    re.compile(
        r"\bdisregard\s+(?:all\s+|any\s+|your\s+|these\s+|the\s+)?(?:previous|prior|above)\s+instructions?\b",
        re.I,
    ),
    re.compile(r"\bas\s+the\s+assistant[,]?\s+you\s+(?:must|should|will)\b", re.I),
    re.compile(r"\byou\s+are\s+now\s+(?:in\s+)?(?:dan|developer\s+mode|unrestricted)\b", re.I),
    re.compile(r"\bnew\s+instructions?\s*:\s*", re.I),
    re.compile(r"\bsystem\s*prompt\s*:\s*", re.I),
    re.compile(
        r"\bforward\s+(?:us\s+|me\s+|over\s+)?(?:this|your|the)\s+(?:full\s+)?"
        r"(?:inbox|contacts?|contact\s+list|data|emails?)\b",
        re.I,
    ),
    re.compile(r"\bexport\s+(?:your|the)\s+(?:full\s+)?(?:inbox|contact\s+list|database)\b", re.I),
    re.compile(r"\binbox\s+export\b", re.I),
    re.compile(
        r"\blist\s+of\s+all\s+(?:the\s+)?(?:brands?|schools?|clients?|contacts?|creators?)\b", re.I
    ),
    re.compile(r"\bwithout\s+(?:checking|asking|confirming)\s+with\s+(?:the\s+)?talent\b", re.I),
    re.compile(r"\bbypass\s+(?:the\s+)?(?:approval|policy)\b", re.I),
]

# Section 4.4.6: lookalike domains, overpayment/check schemes, requests
# to download apps or move off-platform, requests for banking info.
_SCAM_PATTERNS = [
    re.compile(r"\boverpay(?:ment|ing)?\b", re.I),
    re.compile(r"\bmore\s+than\s+(?:your|the)\s+(?:fee|rate|price)\b", re.I),
    re.compile(r"\bwire\s+(?:the\s+)?(?:difference|remainder|balance)\b", re.I),
    re.compile(r"\bwire\s+transfer\b", re.I),
    re.compile(r"\bcashier'?s?\s+check\b", re.I),
    re.compile(r"\bdeposit\s+(?:the\s+)?check\b", re.I),
    re.compile(r"\bdownload\s+(?:our|the|this)\s+app\b", re.I),
    re.compile(r"\brouting\s+number\b", re.I),
    re.compile(r"\baccount\s+number\s+and\s+routing\b", re.I),
    re.compile(
        r"\bmove\s+(?:this\s+)?(?:conversation|chat)\s+to\s+(?:whatsapp|telegram|signal)\b", re.I
    ),
    re.compile(r"\bpay(?:ment)?\s+to\s+be\s+featured\b", re.I),
    re.compile(r"\bprocessing\s+fee\s+(?:in\s+)?(?:advance|upfront)\b", re.I),
]

FREEMAIL_DOMAINS = frozenset(
    {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com", "icloud.com", "proton.me"}
)


@dataclass
class SafetyScreenResult:
    flags: set[str] = field(default_factory=set)
    matched_injection_phrases: list[str] = field(default_factory=list)
    matched_scam_phrases: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)  # human-readable, shown to the talent


def _sender_domain(sender: str) -> str:
    if "@" not in sender:
        return ""
    return sender.rsplit("@", 1)[-1].strip().lower()


def screen_message(*, sender: str, subject: str, body: str) -> SafetyScreenResult:
    """Evidence-producing, never a bare verdict (Section 4.4.6: 'show
    evidence, never just a verdict')."""
    result = SafetyScreenResult()
    text = f"{subject}\n{body}"

    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            result.flags.add("suspicious_injection")
            result.matched_injection_phrases.append(match.group(0))
            result.evidence.append(f'Instruction-like phrase aimed at an AI: "{match.group(0)}"')

    scam_hits = 0
    for pattern in _SCAM_PATTERNS:
        match = pattern.search(text)
        if match:
            scam_hits += 1
            result.matched_scam_phrases.append(match.group(0))
            result.evidence.append(f'Scam-pattern phrase: "{match.group(0)}"')

    # A single scam-adjacent phrase can be innocuous ("wire transfer" in a
    # legitimate payment-terms discussion); two or more independent hits,
    # or a lookalike/freemail sender claiming brand authority, raise
    # confidence enough to flag.
    domain = _sender_domain(sender)
    sender_is_freemail_or_lookalike = (
        domain in FREEMAIL_DOMAINS or "lookalike" in domain or "-" in domain
    )

    if scam_hits >= 2:
        result.flags.add("scam_suspected")
    elif scam_hits == 1 and sender_is_freemail_or_lookalike:
        result.flags.add("scam_suspected")
        result.evidence.append(
            f"Sender domain '{domain}' is freemail/lookalike, not a corporate domain."
        )

    return result
