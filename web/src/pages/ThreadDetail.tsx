import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Nav from "../components/Nav";
import { api, MessageItem, OptionSet, PolicyStatus, ThreadDetail as ThreadDetailT } from "../lib/api";

const POLICY_BADGE: Record<PolicyStatus, string> = {
  allow: "badge-good",
  require_approval: "badge-warn",
  deny: "badge-bad",
};

const POLICY_LABEL: Record<PolicyStatus, string> = {
  allow: "Ready to send",
  require_approval: "Needs your approval",
  deny: "Blocked by policy",
};

function MessageBubble({ message }: { message: MessageItem }) {
  const isOutbound = message.direction === "outbound";
  return (
    <div className={`mb-3 flex ${isOutbound ? "justify-end" : "justify-start"}`}>
      <div className={isOutbound ? "bubble-outbound" : "bubble-inbound"}>
        {message.subject && <p className="mb-1 text-xs opacity-70">{message.subject}</p>}
        <p className="whitespace-pre-wrap">{message.body_text}</p>
      </div>
    </div>
  );
}

export default function ThreadDetail() {
  const { threadId } = useParams<{ threadId: string }>();
  const [thread, setThread] = useState<ThreadDetailT | null>(null);
  const [optionSet, setOptionSet] = useState<OptionSet | null>(null);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [customText, setCustomText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    if (!threadId) return;
    const [threadResp, optionSets] = await Promise.all([
      api.getThread(threadId),
      api.listOptionSets(threadId),
    ]);
    setThread(threadResp);
    const pending = optionSets.find((os) => os.status === "pending") ?? null;
    setOptionSet(pending);
    if (pending) {
      setDrafts(Object.fromEntries(pending.options.map((o, i) => [i, o.draft])));
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId]);

  async function sendOption(index: number) {
    if (!optionSet) return;
    const original = optionSet.options[index].draft;
    const current = drafts[index] ?? original;
    setBusy(true);
    setError(null);
    try {
      await api.chooseOption(optionSet.id, {
        kind: "option",
        index,
        adjusted_text: current !== original ? current : undefined,
        send: true,
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send");
    } finally {
      setBusy(false);
    }
  }

  async function sendQuickReply(index: number) {
    if (!optionSet) return;
    setBusy(true);
    setError(null);
    try {
      await api.chooseOption(optionSet.id, { kind: "quick_reply", index, send: true });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send");
    } finally {
      setBusy(false);
    }
  }

  async function sendCustom() {
    if (!optionSet || !customText.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.chooseOption(optionSet.id, { kind: "custom", custom_text: customText, send: true });
      setCustomText("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send");
    } finally {
      setBusy(false);
    }
  }

  async function adjust(index: number) {
    if (!optionSet) return;
    const instruction = window.prompt("Adjust this draft how? (e.g. \"warmer\", \"shorter\")");
    if (!instruction) return;
    setBusy(true);
    setError(null);
    try {
      const { draft } = await api.adjustOption(optionSet.id, { index, instruction });
      setDrafts((prev) => ({ ...prev, [index]: draft }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to adjust");
    } finally {
      setBusy(false);
    }
  }

  if (!thread) {
    return <div className="p-8 text-sm text-muted dark:text-muted-dark">Loading…</div>;
  }

  const recommended = optionSet?.options.find((o) => o.is_recommended);
  const rest = optionSet?.options.filter((o) => !o.is_recommended) ?? [];
  const orderedOptions = optionSet ? [...(recommended ? [recommended] : []), ...rest] : [];

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <Nav />
      <Link to="/inbox" className="mb-4 inline-block text-sm text-muted hover:text-ink dark:text-muted-dark">
        ← Inbox
      </Link>

      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">
          {thread.subject || thread.participants.join(", ")}
        </h1>
        <div className="mt-1 flex items-center gap-2">
          <span className="badge-neutral">{thread.channel}</span>
          {thread.triage && <span className="badge-neutral">{thread.triage.classification}</span>}
        </div>
        {thread.triage?.summary && (
          <p className="mt-2 text-sm text-muted dark:text-muted-dark">{thread.triage.summary}</p>
        )}
      </div>

      <div className="mb-6">
        {thread.messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
      </div>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {optionSet ? (
        <div className="space-y-3">
          {optionSet.quick_replies.map((qr, i) => (
            <div key={qr.label} className="card">
              <div className="mb-2 flex items-center gap-2">
                <p className="font-medium">{qr.label}</p>
                <span className={POLICY_BADGE[qr.policy_status]}>{POLICY_LABEL[qr.policy_status]}</span>
              </div>
              {qr.draft ? (
                <p className="mb-3 whitespace-pre-wrap text-sm text-muted dark:text-muted-dark">
                  {qr.draft}
                </p>
              ) : (
                <p className="mb-3 text-sm text-muted dark:text-muted-dark">
                  No draft yet — write your own reply below instead.
                </p>
              )}
              {qr.draft && (
                <button
                  onClick={() => sendQuickReply(i)}
                  disabled={busy || qr.policy_status === "deny"}
                  className="btn-primary"
                >
                  Send
                </button>
              )}
            </div>
          ))}

          {orderedOptions.map((opt) => {
            const index = optionSet.options.indexOf(opt);
            return (
              <div key={opt.label} className="card">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <p className="font-medium">{opt.label}</p>
                  {opt.is_recommended && <span className="badge-good">Recommended</span>}
                  <span className={POLICY_BADGE[opt.policy_status]}>
                    {POLICY_LABEL[opt.policy_status]}
                  </span>
                </div>
                <p className="text-sm text-muted dark:text-muted-dark">{opt.strategy}</p>
                <p className="mt-1 text-xs text-muted dark:text-muted-dark">
                  <span className="font-medium">Tradeoff:</span> {opt.tradeoff} ·{" "}
                  <span className="font-medium">Likely next:</span> {opt.likely_outcome}
                </p>
                <textarea
                  className="input mt-3 min-h-24"
                  value={drafts[index] ?? opt.draft}
                  onChange={(e) => setDrafts((prev) => ({ ...prev, [index]: e.target.value }))}
                />
                <div className="mt-2 flex gap-2">
                  <button
                    onClick={() => sendOption(index)}
                    disabled={busy || opt.policy_status === "deny"}
                    className="btn-primary"
                  >
                    Send
                  </button>
                  <button onClick={() => adjust(index)} disabled={busy} className="btn-secondary">
                    Adjust
                  </button>
                </div>
              </div>
            );
          })}

          <div className="card">
            <p className="mb-2 font-medium">Write my own</p>
            <textarea
              className="input min-h-24"
              placeholder="Type a custom reply…"
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
            />
            <button
              onClick={sendCustom}
              disabled={busy || !customText.trim()}
              className="btn-secondary mt-2"
            >
              Send
            </button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted dark:text-muted-dark">
          Nothing pending — this thread has been handled.
        </p>
      )}
    </div>
  );
}
