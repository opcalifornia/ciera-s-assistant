import { FormEvent, useEffect, useState } from "react";
import Nav from "../components/Nav";
import { api, Brand, ConcessionRule, Offering } from "../lib/api";

const OPPORTUNITY_TYPES = [
  "brand_deal",
  "speaking",
  "school_visit",
  "show_appearance",
  "media",
  "production_gig",
  "book_order",
  "collaboration",
];

function OfferingCard({ offering }: { offering: Offering }) {
  return (
    <div className="card mb-2">
      <div className="mb-1 flex items-center gap-2">
        <span className="badge-neutral">{offering.opportunity_type}</span>
        <p className="font-medium">{offering.name}</p>
      </div>
      <p className="text-sm text-muted dark:text-muted-dark">
        Anchor {offering.anchor ?? "—"} · Target {offering.target ?? "—"} · Floor{" "}
        {offering.floor ?? "—"} {offering.currency}
      </p>
      {offering.concession_ladder.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-muted dark:text-muted-dark">
          {offering.concession_ladder.map((rule) => (
            <li key={rule.label}>
              {rule.label}: {Math.round(rule.fee_adjustment_pct * 100)}% for "{rule.requires}"
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function BrandBrain() {
  const [brand, setBrand] = useState<Brand | null>(null);
  const [offerings, setOfferings] = useState<Offering[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [opportunityType, setOpportunityType] = useState(OPPORTUNITY_TYPES[0]);
  const [name, setName] = useState("");
  const [anchor, setAnchor] = useState("");
  const [target, setTarget] = useState("");
  const [floor, setFloor] = useState("");
  const [concessionLabel, setConcessionLabel] = useState("");
  const [concessionPct, setConcessionPct] = useState("");
  const [concessionRequires, setConcessionRequires] = useState("");

  async function refresh() {
    const brands = await api.listBrands();
    if (brands.length === 0) return;
    setBrand(brands[0]);
    setOfferings(await api.listOfferings(brands[0].id));
  }

  useEffect(() => {
    refresh().catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, []);

  async function createOffering(e: FormEvent) {
    e.preventDefault();
    if (!brand) return;
    setError(null);
    try {
      const concession_ladder: ConcessionRule[] =
        concessionLabel && concessionPct
          ? [
              {
                label: concessionLabel,
                fee_adjustment_pct: -Math.abs(Number(concessionPct)) / 100,
                requires: concessionRequires,
              },
            ]
          : [];
      await api.createOffering(brand.id, {
        opportunity_type: opportunityType,
        name,
        anchor: anchor ? Number(anchor) : undefined,
        target: target ? Number(target) : undefined,
        floor: floor ? Number(floor) : undefined,
        concession_ladder,
      });
      setName("");
      setAnchor("");
      setTarget("");
      setFloor("");
      setConcessionLabel("");
      setConcessionPct("");
      setConcessionRequires("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create offering");
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <Nav />
      <h1 className="mb-2 text-xl font-semibold tracking-tight">Brand Brain</h1>

      {!brand ? (
        <p className="text-sm text-muted dark:text-muted-dark">
          Create a brand on the Inbox page first.
        </p>
      ) : (
        <>
          <p className="mb-6 text-sm text-muted dark:text-muted-dark">
            Rate cards for {brand.persona_name}. Deal Desk uses anchor/target/floor plus the
            concession ladder to compute real quotes for free — no LLM required for the numbers.
          </p>

          <details className="card mb-6">
            <summary className="cursor-pointer text-sm font-medium">Add an offering</summary>
            <form onSubmit={createOffering} className="mt-3 space-y-2">
              <select
                className="input"
                value={opportunityType}
                onChange={(e) => setOpportunityType(e.target.value)}
              >
                {OPPORTUNITY_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <input
                className="input"
                placeholder="Name, e.g. Sponsored Reel"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
              <div className="flex gap-2">
                <input
                  className="input"
                  type="number"
                  placeholder="Anchor $"
                  value={anchor}
                  onChange={(e) => setAnchor(e.target.value)}
                />
                <input
                  className="input"
                  type="number"
                  placeholder="Target $"
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                />
                <input
                  className="input"
                  type="number"
                  placeholder="Floor $"
                  value={floor}
                  onChange={(e) => setFloor(e.target.value)}
                />
              </div>
              <p className="pt-1 text-xs font-medium text-muted dark:text-muted-dark">
                Optional concession (one rung of the ladder)
              </p>
              <div className="flex gap-2">
                <input
                  className="input"
                  placeholder="Label, e.g. Shorter usage window"
                  value={concessionLabel}
                  onChange={(e) => setConcessionLabel(e.target.value)}
                />
                <input
                  className="input w-28"
                  type="number"
                  placeholder="% off"
                  value={concessionPct}
                  onChange={(e) => setConcessionPct(e.target.value)}
                />
              </div>
              <input
                className="input"
                placeholder="Requires, e.g. usage <= 90 days"
                value={concessionRequires}
                onChange={(e) => setConcessionRequires(e.target.value)}
              />
              <button type="submit" className="btn-primary">
                Add offering
              </button>
            </form>
          </details>

          {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

          {offerings.length === 0 ? (
            <p className="text-sm text-muted dark:text-muted-dark">
              No offerings yet — add one above, then simulate a message with a matching budget
              in Inbox to see Deal Desk quote it for real.
            </p>
          ) : (
            offerings.map((o) => <OfferingCard key={o.id} offering={o} />)
          )}
        </>
      )}
    </div>
  );
}
