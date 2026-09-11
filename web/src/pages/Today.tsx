import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
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

  function signOut() {
    clearTokens();
    navigate("/login");
  }

  if (!me || !workspace) {
    return <div className="p-8 text-sm text-muted dark:text-muted-dark">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Today</h1>
          <p className="text-sm text-muted dark:text-muted-dark">{workspace.name}</p>
        </div>
        <button onClick={signOut} className="text-sm text-muted hover:text-ink dark:text-muted-dark">
          Sign out
        </button>
      </div>

      <div className="card mb-4">
        <p className="text-sm text-muted dark:text-muted-dark">Signed in as</p>
        <p className="font-medium">
          {me.full_name || me.email} <span className="text-muted dark:text-muted-dark">· {me.role}</span>
        </p>
      </div>

      <div className="card mb-4">
        <div className="flex items-center justify-between">
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
        Approvals, Inbox, Pipeline, and the rest of Section 12's screens land in Phase 1+ as
        their owning features ship. This is the Phase 0 foundation: auth, workspace, and the
        policy engine's kill switch, wired end-to-end.
      </div>
    </div>
  );
}
