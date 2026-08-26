import { useEffect, useState } from "react";

import { ApiRequestError } from "../api/client";
import {
  batchUpdatePipelineStages,
  listPipelineStages,
  resetPipelineStagesToDefault,
  type PipelineStage,
} from "../api/pipelineStages";
import {
  listPipelineStageTemplates,
  type PipelineStageTemplate,
} from "../api/pipelineStageTemplates";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { PageSpinner, Spinner } from "../components/Spinner";
import { stageColor, stageIcon } from "../stageColor";
import { useMe } from "../useMe";

interface StageSeed {
  name: string;
  isWon: boolean;
  isLost: boolean;
  isInvoiceStage: boolean;
  isReworkStage: boolean;
}

// PIPELINE_CONFIG_RESET_PLAN.md §7 task 5 — the whole page now edits a
// local draft; nothing hits the API until Save. `id` is absent for a
// stage the admin added this session (not yet saved) — `clientKey` gives
// every row (saved or not) a stable React key and drag/rename identity
// that doesn't depend on a server id existing yet.
interface DraftStage {
  clientKey: string;
  id?: string;
  name: string;
  is_won: boolean;
  is_lost: boolean;
  is_invoice_stage: boolean;
  is_rework_stage: boolean;
}

function toDraft(stage: PipelineStage): DraftStage {
  return {
    clientKey: stage.id,
    id: stage.id,
    name: stage.name,
    is_won: stage.is_won,
    is_lost: stage.is_lost,
    is_invoice_stage: stage.is_invoice_stage,
    is_rework_stage: stage.is_rework_stage,
  };
}

// Order-sensitive on purpose — array position is what "changed" means
// for a reorder, same as the batch/reorder endpoints themselves.
function draftSignature(stages: DraftStage[]): string {
  return JSON.stringify(
    stages.map((s) => [
      s.id ?? null,
      s.name,
      s.is_won,
      s.is_lost,
      s.is_invoice_stage,
      s.is_rework_stage,
    ]),
  );
}

const RESET_TO_DEFAULT_PHRASE = "RESET TO DEFAULT";

export function PipelineConfigPage() {
  const { token } = useAuth();
  const { me } = useMe();
  const [savedStages, setSavedStages] = useState<PipelineStage[]>([]);
  const [draftStages, setDraftStages] = useState<DraftStage[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [templates, setTemplates] = useState<PipelineStageTemplate[]>([]);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [createSeed, setCreateSeed] = useState<StageSeed | undefined>(undefined);
  const [draggingKey, setDraggingKey] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showResetToDefault, setShowResetToDefault] = useState(false);

  function load() {
    if (!token) return;
    listPipelineStages(token).then((response) => {
      setSavedStages(response.data);
      setDraftStages(response.data.map(toDraft));
      setLoaded(true);
    });
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [token]);

  useEffect(() => {
    if (!token || me?.user.role !== "admin") return;
    listPipelineStageTemplates(token).then((response) => setTemplates(response.data));
  }, [token, me?.user.role]);

  const dirty = draftSignature(draftStages) !== draftSignature(savedStages.map(toDraft));

  function applyTemplate(template: PipelineStageTemplate) {
    setCreateSeed({
      name: template.name,
      isWon: template.is_won,
      isLost: template.is_lost,
      isInvoiceStage: template.is_invoice_stage,
      isReworkStage: template.is_rework_stage,
    });
    setShowTemplates(false);
    setShowCreate(true);
  }

  if (me && me.user.role !== "admin") {
    return (
      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "var(--space-6)" }}>
        <EmptyState headline="Admins only" />
      </div>
    );
  }

  function addDraftStage(seed: StageSeed) {
    setDraftStages((current) => [
      ...current,
      {
        clientKey: `new-${crypto.randomUUID()}`,
        name: seed.name,
        is_won: seed.isWon,
        is_lost: seed.isLost,
        is_invoice_stage: seed.isInvoiceStage,
        is_rework_stage: seed.isReworkStage,
      },
    ]);
  }

  function removeDraftStage(clientKey: string) {
    setDraftStages((current) => current.filter((s) => s.clientKey !== clientKey));
  }

  function renameDraftStage(clientKey: string, name: string) {
    setDraftStages((current) =>
      current.map((s) => (s.clientKey === clientKey ? { ...s, name } : s)),
    );
  }

  function handleDrop(targetKey: string) {
    if (!draggingKey || draggingKey === targetKey) {
      setDraggingKey(undefined);
      return;
    }
    const fromIndex = draftStages.findIndex((s) => s.clientKey === draggingKey);
    const toIndex = draftStages.findIndex((s) => s.clientKey === targetKey);
    setDraggingKey(undefined);
    if (fromIndex === -1 || toIndex === -1) return;
    const reordered = [...draftStages];
    const [moved] = reordered.splice(fromIndex, 1);
    reordered.splice(toIndex, 0, moved!);
    setDraftStages(reordered);
  }

  async function handleSave() {
    if (!token) return;
    setSaving(true);
    setError(undefined);
    try {
      const response = await batchUpdatePipelineStages(
        token,
        draftStages.map((s) => ({
          id: s.id,
          name: s.name,
          is_won: s.is_won,
          is_lost: s.is_lost,
          is_invoice_stage: s.is_invoice_stage,
          is_rework_stage: s.is_rework_stage,
        })),
      );
      setSavedStages(response.data);
      setDraftStages(response.data.map(toDraft));
    } catch (err) {
      // Batch is all-or-nothing server-side — nothing was applied, so
      // the draft is left exactly as the admin had it, not reset.
      setError(err instanceof ApiRequestError ? err.message : "Couldn't save changes");
    } finally {
      setSaving(false);
    }
  }

  function handleResetConfirmed() {
    setDraftStages(savedStages.map(toDraft));
    setShowResetConfirm(false);
    setError(undefined);
  }

  async function handleResetToDefaultConfirmed() {
    if (!token) return;
    setError(undefined);
    try {
      const response = await resetPipelineStagesToDefault(token);
      setSavedStages(response.data);
      setDraftStages(response.data.map(toDraft));
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't reset to default");
    } finally {
      setShowResetToDefault(false);
    }
  }

  if (!loaded) {
    return <PageSpinner />;
  }

  return (
    <>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        {error && (
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        )}

        {showTemplates && (
          <Card
            title="Start from a template"
            action={
              <Button variant="text" onClick={() => setShowTemplates(false)}>
                Close
              </Button>
            }
          >
            {templates.length === 0 && <EmptyState headline="No templates available" />}
            {templates.length > 0 && (
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {templates.map((template, index) => (
                  <li
                    key={template.id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "var(--space-3) var(--space-2)",
                      borderTop: index === 0 ? "none" : "1px solid var(--border)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                      <div>
                        <div style={{ fontWeight: "var(--weight-semibold)" }}>{template.name}</div>
                        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                          {template.category}
                        </div>
                      </div>
                      {template.is_won && <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Won</span>}
                      {template.is_lost && <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Lost</span>}
                      {template.is_invoice_stage && (
                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Invoice</span>
                      )}
                      {template.is_rework_stage && (
                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Rework</span>
                      )}
                    </div>
                    <Button variant="secondary" onClick={() => applyTemplate(template)}>
                      Use template
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}

        {showCreate && (
          <CreateStageForm
            initial={createSeed}
            onCreated={(seed) => {
              addDraftStage(seed);
              setShowCreate(false);
              setCreateSeed(undefined);
            }}
            onCancel={() => {
              setShowCreate(false);
              setCreateSeed(undefined);
            }}
          />
        )}

        <Card
          title="Configured stages"
          action={
            <div style={{ display: "flex", gap: "var(--space-2)" }}>
              <Button variant="secondary" onClick={() => setShowTemplates((v) => !v)}>
                {showTemplates ? "Hide templates" : "Start from a template"}
              </Button>
              <Button
                variant="primary"
                onClick={() => {
                  setCreateSeed(undefined);
                  setShowCreate((v) => !v);
                }}
              >
                {showCreate ? "Cancel" : "+ New stage"}
              </Button>
            </div>
          }
        >
          {draftStages.length === 0 && <EmptyState headline="No pipeline stages yet" />}

          {draftStages.length > 0 && (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {draftStages.map((stage, index) => (
                <li
                  key={stage.clientKey}
                  draggable
                  onDragStart={() => setDraggingKey(stage.clientKey)}
                  onDragEnd={() => setDraggingKey(undefined)}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={() => handleDrop(stage.clientKey)}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "var(--space-3) var(--space-2)",
                    borderTop: index === 0 ? "none" : "1px solid var(--border)",
                    cursor: "grab",
                    opacity: draggingKey === stage.clientKey ? 0.5 : 1,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                    <span style={{ color: "var(--text-muted)" }}>::</span>
                    <StageNameEditor
                      stage={stage}
                      index={index}
                      onRename={(name) => renameDraftStage(stage.clientKey, name)}
                    />
                    {!stage.id && (
                      <span style={{ fontSize: 12, color: "var(--accent)" }}>New</span>
                    )}
                    {stage.is_won && (
                      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Won</span>
                    )}
                    {stage.is_lost && (
                      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Lost</span>
                    )}
                    {stage.is_invoice_stage && (
                      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Invoice</span>
                    )}
                    {stage.is_rework_stage && (
                      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Rework</span>
                    )}
                  </div>
                  <Button variant="text" onClick={() => removeDraftStage(stage.clientKey)}>
                    Delete
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div style={{ display: "flex", gap: "var(--space-3)" }}>
          <Button variant="primary" disabled={!dirty || saving} onClick={() => void handleSave()}>
            {saving ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Spinner size={12} /> Saving…
              </span>
            ) : (
              "Save"
            )}
          </Button>
          <Button variant="secondary" disabled={!dirty} onClick={() => setShowResetConfirm(true)}>
            Reset
          </Button>
          <Button variant="secondary" onClick={() => setShowResetToDefault(true)}>
            Reset to Default
          </Button>
        </div>
      </div>

      {showResetConfirm && (
        <div
          style={{
            position: "fixed",
            bottom: 24,
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--elevation-2)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            boxShadow: "var(--shadow-md)",
            padding: "var(--space-4)",
            display: "flex",
            gap: "var(--space-3)",
            alignItems: "center",
          }}
        >
          <span>Discard your unsaved pipeline changes?</span>
          <Button variant="primary" onClick={handleResetConfirmed}>
            Discard changes
          </Button>
          <Button variant="secondary" onClick={() => setShowResetConfirm(false)}>
            Cancel
          </Button>
        </div>
      )}

      {showResetToDefault && (
        <ResetToDefaultModal
          onConfirm={() => void handleResetToDefaultConfirmed()}
          onCancel={() => setShowResetToDefault(false)}
        />
      )}
    </>
  );
}

function StageNameEditor({
  stage,
  index,
  onRename,
}: {
  stage: DraftStage;
  index: number;
  onRename: (name: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(stage.name);
  const tone = stageColor(stage, index);

  function commit() {
    setEditing(false);
    const trimmed = draft.trim();
    if (trimmed && trimmed !== stage.name) onRename(trimmed);
    else setDraft(stage.name);
  }

  if (editing) {
    return (
      <input
        autoFocus
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") commit();
          if (event.key === "Escape") {
            setDraft(stage.name);
            setEditing(false);
          }
        }}
        style={{ fontSize: "var(--text-sm)" }}
      />
    );
  }

  return (
    <span
      onClick={() => {
        setDraft(stage.name);
        setEditing(true);
      }}
      style={{ cursor: "text" }}
    >
      <Badge label={stage.name} tone={tone} icon={stageIcon(stage)} />
    </span>
  );
}

function ResetToDefaultModal({
  onConfirm,
  onCancel,
}: {
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [typed, setTyped] = useState("");
  const [submitting, setSubmitting] = useState(false);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.3)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
      onClick={onCancel}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          width: 440,
          maxWidth: "calc(100% - var(--space-4))",
          background: "var(--elevation-2)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-md)",
          padding: "var(--space-5)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-3)",
        }}
      >
        <h2 style={{ fontSize: "var(--text-lg)", lineHeight: "var(--line-lg)", margin: 0 }}>
          Reset pipeline to default?
        </h2>
        <p style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", margin: 0 }}>
          This replaces every current stage with this tenant's original default
          set — including any unsaved changes you haven't saved yet. This can't
          be undone.
        </p>
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          Type <strong>{RESET_TO_DEFAULT_PHRASE}</strong> to confirm
          <input
            autoFocus
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            onPaste={(event) => event.preventDefault()}
            style={{ width: "100%", marginTop: 4 }}
          />
        </label>
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button
            variant="primary"
            disabled={typed !== RESET_TO_DEFAULT_PHRASE || submitting}
            onClick={() => {
              setSubmitting(true);
              onConfirm();
            }}
          >
            {submitting ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Spinner size={12} /> Resetting…
              </span>
            ) : (
              "Reset to default"
            )}
          </Button>
          <Button variant="text" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}

function CreateStageForm({
  initial,
  onCreated,
  onCancel,
}: {
  initial?: StageSeed;
  onCreated: (seed: StageSeed) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [isWon, setIsWon] = useState(initial?.isWon ?? false);
  const [isLost, setIsLost] = useState(initial?.isLost ?? false);
  const [isInvoiceStage, setIsInvoiceStage] = useState(initial?.isInvoiceStage ?? false);
  const [isReworkStage, setIsReworkStage] = useState(initial?.isReworkStage ?? false);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    onCreated({ name: name.trim(), isWon, isLost, isInvoiceStage, isReworkStage });
  }

  return (
    <form
      onSubmit={handleSubmit}
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
      <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <input
          type="checkbox"
          checked={isInvoiceStage}
          onChange={(event) => setIsInvoiceStage(event.target.checked)}
        />
        Prompts invoice creation when a deal enters this stage
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <input
          type="checkbox"
          checked={isReworkStage}
          onChange={(event) => setIsReworkStage(event.target.checked)}
        />
        Sends the deal's invoice back for rework when it enters this stage
      </label>
      <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
        Also fixed at creation — same reason as won/lost above.
      </p>
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <Button variant="primary" type="submit">
          Add stage
        </Button>
        <Button variant="text" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
