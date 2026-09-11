import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Nav from "../components/Nav";
import { api, clearTokens, Me, WorkspaceInfo } from "../lib/api";

export default function Today() {
  const navigate = useNavigate();
  const [me, setMe] = useState<Me | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.me(), api.myWorkspace()])
      .then(([meResp, wsResp]) => {
        setMe(meResp);
        setWorkspace(wsResp);
      })
      .catch(() => {
        clearTokens();
        navigate("/login");
      });
  }, [navigate]);

  async function toggleKillSwitch() {
    if (!workspace) return;
    setError(null);
    try {
      const updated = await api.setKillSwitch(!workspace.kill_switch);
      setWorkspace(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update kill switch");
    }
  }

  if (!me || !workspace) {
    return <div className="p-8 text-sm text-muted dark:text-muted-dark">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <Nav />
      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">Today</h1>
        <p className="text-sm text-muted dark:text-muted-dark">{workspace.name}</p>
      </div>

      <div className="card mb-4">
        <p className="text-sm text-muted dark:text-muted-dark">Signed in as</p>
        <p className="font-medium">
          {me.full_name || me.email} <span className="text-muted dark:text-muted-dark">· {me.role}</span>
        </p>
      </div>

      <div className="card mb-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="font-medium">Kill switch</p>
            <p className="text-sm text-muted dark:text-muted-dark">
              Stops all automated sending across the workspace instantly (Section 11).
            </p>
          </div>
          <button
            onClick={toggleKillSwitch}
            className={workspace.kill_switch ? "btn-danger" : "btn-secondary"}
          >
            {workspace.kill_switch ? "Engaged — tap to release" : "Engage kill switch"}
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="card text-sm text-muted dark:text-muted-dark">
        Head to <span className="font-medium text-ink dark:text-ink-dark">Inbox</span> to try the
        pipeline: simulate an inbound email or text, watch it get triaged, and pick a reply option
        to send.
      </div>
    </div>
  );
}
