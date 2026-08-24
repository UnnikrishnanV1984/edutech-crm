import { useEffect, useState } from "react";

import {
  listFollowUpFlags,
  resolveFollowUpFlag,
  type FollowUpFlag,
} from "../api/followUpFlags";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { useMe } from "../useMe";
import { CreateFollowUpFlagPanel } from "./CreateFollowUpFlagPanel";

export function FollowUpFlagsPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const [flags, setFlags] = useState<FollowUpFlag[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [busyId, setBusyId] = useState<string | undefined>(undefined);

  function load() {
    if (!token) return;
    listFollowUpFlags(token).then((response) => setFlags(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token]);

  if (me && me.user.role === "counselor") {
    return (
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
        <EmptyState headline="Managers and admins only" />
      </div>
    );
  }

  async function resolve(flag: FollowUpFlag) {
    if (!token) return;
    setBusyId(flag.id);
    try {
      await resolveFollowUpFlag(token, flag.id);
      setFlags((current) => current.filter((f) => f.id !== flag.id));
    } finally {
      setBusyId(undefined);
    }
  }

  const openFlags = flags.filter((f) => !f.resolved_at);

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <h1>Follow-ups</h1>
        <Button variant="primary" onClick={() => setShowCreate(true)}>
          + New follow-up
        </Button>
      </div>

      {openFlags.length === 0 && (
        <EmptyState
          headline="No follow-ups scheduled"
          subtext="A personal reminder tool — separate from escalations, never notifies the counselor."
          action={
            <Button variant="primary" onClick={() => setShowCreate(true)}>
              + New follow-up
            </Button>
          }
        />
      )}

      {openFlags.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {openFlags.map((flag) => (
            <li
              key={flag.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: 8,
                borderBottom: "1px solid var(--border)",
              }}
            >
              <div>
                <div>{flag.note}</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                  Remind on {new Date(flag.remind_on).toLocaleDateString()}
                </div>
              </div>
              <Button variant="text" disabled={busyId === flag.id} onClick={() => void resolve(flag)}>
                Done
              </Button>
            </li>
          ))}
        </ul>
      )}

      {showCreate && (
        <CreateFollowUpFlagPanel
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
    </div>
  );
}
