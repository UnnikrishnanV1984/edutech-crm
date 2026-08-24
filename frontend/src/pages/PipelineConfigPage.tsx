import { useEffect, useState } from "react";

import { ApiRequestError } from "../api/client";
import {
  createPipelineStage,
  deletePipelineStage,
  listPipelineStages,
  reorderPipelineStages,
  type PipelineStage,
} from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { stageColor, stageIcon } from "../stageColor";
import { useMe } from "../useMe";

export function PipelineConfigPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [busyId, setBusyId] = useState<string | undefined>(undefined);
  const [draggingId, setDraggingId] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | undefined>(undefined);

  function load() {
    if (!token) return;
    listPipelineStages(token).then((response) => setStages(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token]);

  if (me && me.user.role !== "admin") {
    return (
      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
        <EmptyState headline="Admins only" />
      </div>
    );
  }

  async function remove(stage: PipelineStage) {
    if (!token) return;
    setBusyId(stage.id);
    setError(undefined);
    try {
      await deletePipelineStage(token, stage.id);
      setStages((current) => current.filter((s) => s.id !== stage.id));
    } catch (err) {
      // Surface the backend's own message rather than guessing ahead of
      // time which stages are deletable (409 for in-use / last
      // won-lost-open stage — ADMIN_UX_IMPROVEMENTS_PLAN.md Sec4.3).
      setError(err instanceof ApiRequestError ? err.message : "Couldn't delete stage");
    } finally {
      setBusyId(undefined);
    }
  }

  function handleDrop(targetStage: PipelineStage) {
    if (!token || !draggingId || draggingId === targetStage.id) {
      setDraggingId(undefined);
      return;
    }
    const fromIndex = stages.findIndex((s) => s.id === draggingId);
    const toIndex = stages.findIndex((s) => s.id === targetStage.id);
    setDraggingId(undefined);
    if (fromIndex === -1 || toIndex === -1) return;

    const reordered = [...stages];
    const [moved] = reordered.splice(fromIndex, 1);
    reordered.splice(toIndex, 0, moved!);
    const previous = stages;
    setStages(reordered);
    setError(undefined);
    reorderPipelineStages(
      token,
      reordered.map((s) => s.id),
    )
      .then((response) => setStages(response.data))
      .catch((err) => {
        setStages(previous);
        setError(err instanceof ApiRequestError ? err.message : "Couldn't reorder stages");
      });
  }

  return (
    <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
      <h1 style={{ marginBottom: "var(--space-5)" }}>Pipeline config</h1>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        {error && (
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        )}

        {showCreate && (
          <CreateStageForm
            onCreated={() => {
              setShowCreate(false);
              load();
            }}
            onCancel={() => setShowCreate(false)}
          />
        )}

        <Card
          title="Configured stages"
          action={
            <Button variant="primary" onClick={() => setShowCreate((v) => !v)}>
              {showCreate ? "Cancel" : "+ New stage"}
            </Button>
          }
        >
          {stages.length === 0 && <EmptyState headline="No pipeline stages yet" />}

          {stages.length > 0 && (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {stages.map((stage, index) => {
                const tone = stageColor(stage, index);
                return (
                  <li
                    key={stage.id}
                    draggable
                    onDragStart={() => setDraggingId(stage.id)}
                    onDragEnd={() => setDraggingId(undefined)}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={() => handleDrop(stage)}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "var(--space-3) var(--space-2)",
                      borderTop: index === 0 ? "none" : "1px solid var(--border)",
                      cursor: "grab",
                      opacity: draggingId === stage.id ? 0.5 : 1,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                      <span style={{ color: "var(--text-muted)" }}>::</span>
                      <Badge label={stage.name} tone={tone} icon={stageIcon(stage)} />
                      {stage.is_won && (
                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Won</span>
                      )}
                      {stage.is_lost && (
                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Lost</span>
                      )}
                    </div>
                    <Button
                      variant="text"
                      disabled={busyId === stage.id}
                      onClick={() => void remove(stage)}
                    >
                      Delete
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function CreateStageForm({
  onCreated,
  onCancel,
}: {
  onCreated: () => void;
  onCancel: () => void;
}) {
  const { token } = useAuth();
  const [name, setName] = useState("");
  const [isWon, setIsWon] = useState(false);
  const [isLost, setIsLost] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setSubmitting(true);
    setError(undefined);
    try {
      await createPipelineStage(token, { name, is_won: isWon, is_lost: isLost });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't create stage");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={(event) => {
        void handleSubmit(event);
      }}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-3)",
        padding: "var(--space-5)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
        background: "var(--elevation-2)",
        maxWidth: 480,
      }}
    >
      <label>
        Name*
        <input
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
          style={{ display: "block", width: "100%", marginTop: 4 }}
        />
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <input
          type="checkbox"
          checked={isWon}
          onChange={(event) => {
            setIsWon(event.target.checked);
            if (event.target.checked) setIsLost(false);
          }}
        />
        Marks a deal as won
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <input
          type="checkbox"
          checked={isLost}
          onChange={(event) => {
            setIsLost(event.target.checked);
            if (event.target.checked) setIsWon(false);
          }}
        />
        Marks a deal as lost
      </label>
      <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
        Won/lost can't be changed after creation — later features (forecast,
        conversion-signal sends) depend on this being stable.
      </p>
      {error && (
        <p role="alert" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <Button variant="primary" type="submit" disabled={submitting}>
          {submitting ? "Creating…" : "Create stage"}
        </Button>
        <Button variant="text" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
