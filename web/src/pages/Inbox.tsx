import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Nav from "../components/Nav";
import { api, Brand, Channel, clearTokens, ThreadSummary } from "../lib/api";

const URGENCY_BADGE: Record<string, string> = {
  high: "badge-bad",
  normal: "badge-neutral",
  low: "badge-neutral",
};

function ThreadRow({ thread }: { thread: ThreadSummary }) {
  const preview = thread.triage?.summary || "Not triaged yet";
  return (
    <Link
      to={`/threads/${thread.id}`}
      className="card mb-2 block transition-colors hover:bg-black/[0.02] dark:hover:bg-white/[0.03]"
    >
      <div className="mb-1 flex items-center gap-2">
        <span className="badge-neutral">{thread.channel}</span>
        {thread.needs_a_look && <span className="badge-warn">Needs a look</span>}
        {thread.triage && (
          <span className={URGENCY_BADGE[thread.triage.urgency] ?? "badge-neutral"}>
            {thread.triage.urgency}
          </span>
        )}
        <span className="ml-auto text-xs text-muted dark:text-muted-dark">
          {new Date(thread.last_message_at).toLocaleString()}
        </span>
      </div>
      <p className="font-medium">{thread.subject || thread.participants.join(", ")}</p>
      <p className="truncate text-sm text-muted dark:text-muted-dark">{preview}</p>
    </Link>
  );
}

export default function Inbox() {
  const navigate = useNavigate();
  const [brands, setBrands] = useState<Brand[] | null>(null);
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [newBrandName, setNewBrandName] = useState("");
  const [channel, setChannel] = useState<Channel>("email");
  const [sender, setSender] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");

  async function refresh() {
    const [brandList, threadList] = await Promise.all([api.listBrands(), api.listThreads()]);
    setBrands(brandList);
    setThreads(threadList);
  }

  useEffect(() => {
    refresh().catch(() => {
      clearTokens();
      navigate("/login");
    });
  }, [navigate]);

  async function createBrand(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.createBrand({ persona_name: newBrandName });
      setNewBrandName("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create brand");
    }
  }

  async function ingest(e: FormEvent) {
    e.preventDefault();
    if (!brands || brands.length === 0) return;
    setError(null);
    setLoading(true);
    try {
      await api.ingestMessage({
        brand_id: brands[0].id,
        channel,
        sender,
        subject,
        body,
      });
      setSender("");
      setSubject("");
      setBody("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to ingest message");
    } finally {
      setLoading(false);
    }
  }

  if (brands === null) {
    return <div className="p-8 text-sm text-muted dark:text-muted-dark">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <Nav />
      <h1 className="mb-6 text-xl font-semibold tracking-tight">Inbox</h1>

      {brands.length === 0 ? (
        <div className="card mb-6">
          <p className="mb-3 text-sm text-muted dark:text-muted-dark">
            Create a brand first — this is who the assistant works on behalf of.
          </p>
          <form onSubmit={createBrand} className="flex gap-2">
            <input
              className="input"
              placeholder="Persona name, e.g. Jordan Rivers"
              value={newBrandName}
              onChange={(e) => setNewBrandName(e.target.value)}
              required
            />
            <button type="submit" className="btn-primary shrink-0">
              Create
            </button>
          </form>
        </div>
      ) : (
        <details className="card mb-6">
          <summary className="cursor-pointer text-sm font-medium">
            Simulate an inbound message
          </summary>
          <p className="mb-3 mt-2 text-xs text-muted dark:text-muted-dark">
            Stands in for a real Gmail/SMS webhook until live credentials are connected — runs the
            same Triage → Brand Voice → Policy Engine pipeline either way.
          </p>
          <form onSubmit={ingest} className="space-y-2">
            <div className="flex gap-2">
              <select
                className="input"
                value={channel}
                onChange={(e) => setChannel(e.target.value as Channel)}
              >
                <option value="email">Email</option>
                <option value="sms">SMS</option>
              </select>
              <input
                className="input"
                placeholder={channel === "sms" ? "From (phone number)" : "From (email)"}
                value={sender}
                onChange={(e) => setSender(e.target.value)}
                required
              />
            </div>
            <input
              className="input"
              placeholder="Subject (optional)"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
            <textarea
              className="input min-h-24"
              placeholder="Message body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              required
            />
            <button type="submit" disabled={loading} className="btn-primary">
              {loading ? "Running triage…" : "Send test message"}
            </button>
          </form>
        </details>
      )}

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {threads.length === 0 ? (
        <p className="text-sm text-muted dark:text-muted-dark">No threads yet.</p>
      ) : (
        threads.map((t) => <ThreadRow key={t.id} thread={t} />)
      )}
    </div>
  );
}
