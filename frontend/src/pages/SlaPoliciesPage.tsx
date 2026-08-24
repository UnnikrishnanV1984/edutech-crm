import { useEffect, useState } from "react";

import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import {
  createSlaPolicy,
  listSlaPolicies,
  setSlaPolicyStatus,
  type SlaAppliesTo,
  type SlaPolicy,
} from "../api/slaPolicies";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { useMe } from "../useMe";

export function SlaPoliciesPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const [policies, setPolicies] = useState<SlaPolicy[]>([]);
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [busyId, setBusyId] = useState<string | undefined>(undefined);

  function load() {
    if (!token) return;
    listSlaPolicies(token).then((response) => setPolicies(response.data));
    listPipelineStages(token).then((response) => setStages(response.data));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token]);

  if (me && me.user.role !== "admin") {
    return (
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
        <EmptyState headline="Admins only" />
      </div>
    );
  }

  async function toggleStatus(policy: SlaPolicy) {
    if (!token) return;
    setBusyId(policy.id);
    const next = policy.status === "active" ? "disabled" : "active";
    try {
      const response = await setSlaPolicyStatus(token, policy.id, next);
      setPolicies((current) => current.map((p) => (p.id === policy.id ? response.data : p)));
    } finally {
      setBusyId(undefined);
    }
  }

  const stageName = (id: string | null) => stages.find((s) => s.id === id)?.name ?? "—";

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <h1>SLA policies</h1>
        <Button variant="primary" onClick={() => setShowCreate((v) => !v)}>
          {showCreate ? "Cancel" : "+ New policy"}
        </Button>
      </div>

      {showCreate && (
        <CreatePolicyForm
          stages={stages}
          onCreated={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}

      {policies.length === 0 && !showCreate && <EmptyState headline="No SLA policies yet" />}

      {policies.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 16 }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
              <th style={{ padding: 8 }}>Name</th>
              <th style={{ padding: 8 }}>Applies to</th>
              <th style={{ padding: 8 }}>Target</th>
              <th style={{ padding: 8 }}>Status</th>
              <th style={{ padding: 8 }}></th>
            </tr>
          </thead>
          <tbody>
            {policies.map((policy) => (
              <tr key={policy.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: 8 }}>{policy.name}</td>
                <td style={{ padding: 8 }}>
                  {policy.applies_to === "stage_entry"
                    ? `Stage: ${stageName(policy.stage_id)}`
                    : "Any task due date"}
                </td>
                <td style={{ padding: 8 }}>{policy.target_minutes} min</td>
                <td style={{ padding: 8 }}>
                  <Badge
                    variant="chip"
                    label={policy.status}
                    tone={
                      policy.status === "active"
                        ? { bg: "var(--success-bg)", fg: "var(--success)", border: "transparent" }
                        : { bg: "var(--surface)", fg: "var(--text-muted)", border: "var(--border)" }
                    }
                  />
                </td>
                <td style={{ padding: 8, textAlign: "right" }}>
                  <Button
                    variant="text"
                    disabled={busyId === policy.id}
                    onClick={() => void toggleStatus(policy)}
                  >
                    {policy.status === "active" ? "Disable" : "Enable"}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function CreatePolicyForm({
  stages,
  onCreated,
}: {
  stages: PipelineStage[];
  onCreated: () => void;
}) {
  const { token } = useAuth();
  const [name, setName] = useState("");
  const [appliesTo, setAppliesTo] = useState<SlaAppliesTo>("task_due");
  const [stageId, setStageId] = useState("");
  const [targetMinutes, setTargetMinutes] = useState(60);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setSubmitting(true);
    setError(undefined);
    try {
      await createSlaPolicy(token, {
        name,
        applies_to: appliesTo,
        stage_id: appliesTo === "stage_entry" ? stageId : undefined,
        target_minutes: targetMinutes,
      });
      onCreated();
    } catch {
      setError("Couldn't create policy — check the fields and try again");
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
        gap: 12,
        padding: 16,
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
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
      <label>
        Applies to*
        <select
          value={appliesTo}
          onChange={(event) => setAppliesTo(event.target.value as SlaAppliesTo)}
          style={{ display: "block", width: "100%", marginTop: 4 }}
        >
          <option value="task_due">Any task, by its due date</option>
          <option value="stage_entry">Entering a pipeline stage</option>
        </select>
      </label>
      {appliesTo === "stage_entry" && (
        <label>
          Stage*
          <select
            required
            value={stageId}
            onChange={(event) => setStageId(event.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          >
            <option value="" disabled>
              Select a stage
            </option>
            {stages.map((stage) => (
              <option key={stage.id} value={stage.id}>
                {stage.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        Target (minutes)*
        <input
          required
          type="number"
          min={1}
          value={targetMinutes}
          onChange={(event) => setTargetMinutes(Number(event.target.value))}
          style={{ display: "block", width: "100%", marginTop: 4 }}
        />
      </label>
      {error && (
        <p role="alert" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}
      <Button variant="primary" type="submit" disabled={submitting}>
        {submitting ? "Creating…" : "Create policy"}
      </Button>
    </form>
  );
}
