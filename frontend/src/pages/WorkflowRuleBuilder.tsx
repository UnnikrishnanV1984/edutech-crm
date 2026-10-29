import { useEffect, useState } from "react";

import { ApiRequestError } from "../api/client";
import { type Course, listCourses } from "../api/courses";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import {
  createWorkflowRule,
  testRunWorkflowRule,
  updateWorkflowRule,
  type ActionType,
  type TriggerType,
  type WorkflowAction,
  type WorkflowCondition,
  type WorkflowRule,
  type WorkflowTestRunResult,
} from "../api/workflowRules";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Select } from "../components/Select";
import { Spinner } from "../components/Spinner";

const TRIGGERS: { value: TriggerType; label: string; sourceType: "contact" | "deal" | "task" }[] = [
  { value: "lead_created", label: "A new lead is created", sourceType: "contact" },
  { value: "stage_changed", label: "A deal's stage changes", sourceType: "deal" },
  { value: "task_overdue", label: "A task becomes overdue", sourceType: "task" },
  { value: "elapsed_time", label: "Time elapses since stage entry", sourceType: "deal" },
];

const ACTIONS: { value: ActionType; label: string; available: boolean }[] = [
  { value: "assign_round_robin", label: "Assign round-robin", available: true },
  {
    value: "assign_by_territory",
    label: "Assign by territory (falls back to round-robin)",
    available: true,
  },
  { value: "create_task", label: "Create a follow-up task", available: true },
  { value: "change_stage", label: "Change the deal's stage", available: true },
  { value: "notify_manager", label: "Notify the manager", available: true },
  { value: "raise_escalation", label: "Raise an escalation", available: true },
  { value: "send_message", label: "Send a message (not yet available)", available: false },
];

const FIELD_OPTIONS: Record<string, { value: string; label: string }[]> = {
  contact: [{ value: "lead_source", label: "Lead source" }],
  deal: [
    { value: "stage_id", label: "Pipeline stage" },
    { value: "course_id", label: "Course" },
  ],
  task: [],
};

const LEAD_SOURCES = ["meta", "google", "web", "whatsapp", "manual"];

function triggerSourceType(triggerType: TriggerType): "contact" | "deal" | "task" {
  return TRIGGERS.find((t) => t.value === triggerType)?.sourceType ?? "contact";
}

function describeTrigger(triggerType: TriggerType, elapsedMinutes: number): string {
  if (triggerType === "elapsed_time") {
    return `${elapsedMinutes} minute(s) elapse since the deal entered its current stage`;
  }
  return TRIGGERS.find((t) => t.value === triggerType)?.label.toLowerCase() ?? triggerType;
}

function describeCondition(
  condition: WorkflowCondition,
  stages: PipelineStage[],
  courses: Course[],
): string {
  const fieldLabel =
    Object.values(FIELD_OPTIONS)
      .flat()
      .find((f) => f.value === condition.field)?.label ?? condition.field;
  const op = condition.op === "in" ? "is any of" : "is";
  let valueLabel = String(condition.value);
  if (condition.field === "stage_id") {
    valueLabel = stages.find((s) => s.id === condition.value)?.name ?? valueLabel;
  } else if (condition.field === "course_id") {
    valueLabel = courses.find((c) => c.id === condition.value)?.name ?? valueLabel;
  }
  return `${fieldLabel} ${op} "${valueLabel}"`;
}

function describeAction(action: WorkflowAction, stages: PipelineStage[]): string {
  const label = ACTIONS.find((a) => a.value === action.type)?.label ?? action.type;
  if (action.type === "create_task" && action.config?.title) {
    return `create a task "${action.config.title}"`;
  }
  if (action.type === "change_stage" && action.config?.to_stage_id) {
    const stageName = stages.find((s) => s.id === action.config?.to_stage_id)?.name;
    return stageName ? `change the deal's stage to "${stageName}"` : label;
  }
  if (action.type === "notify_manager" && action.config?.message) {
    return `notify the manager: "${action.config.message}"`;
  }
  return label.replace(" (not yet available)", "");
}

interface WorkflowRuleBuilderProps {
  mode: "create" | "edit" | "view";
  rule?: WorkflowRule;
  onSaved: (rule: WorkflowRule) => void;
  onCancel: () => void;
}

export function WorkflowRuleBuilder({ mode, rule, onSaved, onCancel }: WorkflowRuleBuilderProps) {
  const { token } = useAuth();
  const readOnly = mode === "view";

  const [name, setName] = useState(rule?.name ?? "");
  const [triggerType, setTriggerType] = useState<TriggerType>(rule?.trigger_type ?? "lead_created");
  const [elapsedMinutes, setElapsedMinutes] = useState<number>(
    (rule?.trigger_config.minutes as number) ?? 1440,
  );
  const [conditions, setConditions] = useState<WorkflowCondition[]>(rule?.conditions ?? []);
  const [actions, setActions] = useState<WorkflowAction[]>(
    rule?.actions ?? [{ type: "notify_manager", config: {} }],
  );

  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);

  const [testResult, setTestResult] = useState<WorkflowTestRunResult | undefined>(undefined);
  const [testing, setTesting] = useState(false);
  const [testError, setTestError] = useState<string | undefined>(undefined);

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!token) return;
    listPipelineStages(token).then((response) => setStages(response.data));
    listCourses(token).then((response) => setCourses(response.data));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const sourceType = triggerSourceType(triggerType);
  const fieldOptions = FIELD_OPTIONS[sourceType] ?? [];

  function valueOptions(field: string): { value: string; label: string }[] {
    if (field === "lead_source") return LEAD_SOURCES.map((s) => ({ value: s, label: s }));
    if (field === "stage_id") return stages.map((s) => ({ value: s.id, label: s.name }));
    if (field === "course_id") return courses.map((c) => ({ value: c.id, label: c.name }));
    return [];
  }

  function addCondition() {
    const firstField = fieldOptions[0]?.value ?? "";
    setConditions((current) => [
      ...current,
      { field: firstField, op: "eq", value: valueOptions(firstField)[0]?.value ?? "" },
    ]);
  }

  function updateCondition(index: number, patch: Partial<WorkflowCondition>) {
    setConditions((current) =>
      current.map((c, i) => (i === index ? { ...c, ...patch } : c)),
    );
  }

  function removeCondition(index: number) {
    setConditions((current) => current.filter((_, i) => i !== index));
  }

  function addAction() {
    setActions((current) => [...current, { type: "notify_manager", config: {} }]);
  }

  function updateAction(index: number, patch: Partial<WorkflowAction>) {
    setActions((current) => current.map((a, i) => (i === index ? { ...a, ...patch } : a)));
  }

  function updateActionConfig(index: number, key: string, value: unknown) {
    setActions((current) =>
      current.map((a, i) => (i === index ? { ...a, config: { ...a.config, [key]: value } } : a)),
    );
  }

  function removeAction(index: number) {
    setActions((current) => current.filter((_, i) => i !== index));
  }

  const triggerConfig =
    triggerType === "elapsed_time"
      ? { since: "stage_entered_at", minutes: elapsedMinutes }
      : {};

  async function handleTestRun() {
    if (!token) return;
    setTesting(true);
    setTestError(undefined);
    try {
      const response = await testRunWorkflowRule(token, { trigger_type: triggerType, trigger_config: triggerConfig, conditions });
      setTestResult(response.data);
    } catch (err) {
      setTestError(err instanceof ApiRequestError ? err.message : "Couldn't test run this rule");
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    if (!token || !name.trim() || actions.length === 0) return;
    setSaving(true);
    setSaveError(undefined);
    try {
      const body = { name: name.trim(), trigger_config: triggerConfig, conditions, actions };
      const response =
        mode === "create"
          ? await createWorkflowRule(token, {
              ...body,
              trigger_type: triggerType,
              status: "active",
            })
          : await updateWorkflowRule(token, rule!.id, body);
      onSaved(response.data);
    } catch (err) {
      setSaveError(err instanceof ApiRequestError ? err.message : "Couldn't save this rule");
    } finally {
      setSaving(false);
    }
  }

  const previewSentence = `When ${describeTrigger(triggerType, elapsedMinutes)}${
    conditions.length > 0
      ? `, if ${conditions.map((c) => describeCondition(c, stages, courses)).join(" and ")}`
      : ""
  }, then ${actions.map((a) => describeAction(a, stages)).join(", then ")}.`;

  return (
    <div
      style={{
        width: 392,
        maxWidth: "100%",
        flex: "none",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        padding: "var(--space-4)",
        background: "var(--elevation-2)",
        display: "flex",
        flexDirection: "column",
        gap: 16,
        alignSelf: "flex-start",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <h2 style={{ margin: 0, fontSize: "var(--text-lg)" }}>
          {mode === "create" ? "New rule" : readOnly ? "View rule" : "Edit rule"}
        </h2>
        <div style={{ flex: 1 }} />
        {rule && <Badge label={rule.status.replace("_", " ")} />}
      </div>

      <label>
        <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Rule name</span>
        <input
          disabled={readOnly}
          value={name}
          onChange={(event) => setName(event.target.value)}
          style={{ display: "block", width: "100%", marginTop: 4 }}
        />
      </label>

      <label>
        <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>When (trigger)</span>
        <div style={{ marginTop: 4 }}>
          <Select
            ariaLabel="When (trigger)"
            disabled={readOnly || mode === "edit"}
            value={triggerType}
            onChange={(value) => {
              setTriggerType(value as TriggerType);
              setConditions([]);
            }}
            options={TRIGGERS}
            triggerStyle={{ width: "100%" }}
          />
        </div>
      </label>
      {triggerType === "elapsed_time" && (
        <label>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
            Minutes since the deal entered its current stage
          </span>
          <input
            disabled={readOnly}
            type="number"
            min={1}
            value={elapsedMinutes}
            onChange={(event) => setElapsedMinutes(Number(event.target.value))}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
      )}

      <div>
        <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>If (conditions)</span>
        <div style={{ marginTop: 7, display: "flex", flexDirection: "column", gap: 8 }}>
          {conditions.map((condition, index) => (
            <div key={index} style={{ display: "flex", gap: 6, alignItems: "center" }}>
              {index > 0 && <Badge label="AND" />}
              <div style={{ flex: 1 }}>
                <Select
                  ariaLabel="Condition field"
                  disabled={readOnly}
                  value={condition.field}
                  onChange={(value) =>
                    updateCondition(index, {
                      field: value,
                      value: valueOptions(value)[0]?.value ?? "",
                    })
                  }
                  options={fieldOptions}
                  triggerStyle={{ width: "100%" }}
                />
              </div>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>is</span>
              <div style={{ flex: 1 }}>
                <Select
                  ariaLabel="Condition value"
                  disabled={readOnly}
                  value={String(condition.value)}
                  onChange={(value) => updateCondition(index, { value })}
                  options={valueOptions(condition.field)}
                  triggerStyle={{ width: "100%" }}
                />
              </div>
              {!readOnly && (
                <Button variant="text" type="button" onClick={() => removeCondition(index)}>
                  ✕
                </Button>
              )}
            </div>
          ))}
          {!readOnly && fieldOptions.length > 0 && (
            <Button variant="text" type="button" onClick={addCondition}>
              + Add condition
            </Button>
          )}
          {fieldOptions.length === 0 && (
            <p style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", margin: 0 }}>
              This trigger doesn't support conditions yet.
            </p>
          )}
        </div>
      </div>

      <div>
        <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Then (actions)</span>
        <div style={{ marginTop: 7, display: "flex", flexDirection: "column", gap: 8 }}>
          {actions.map((action, index) => (
            <div
              key={index}
              style={{
                border: "1px solid var(--border)",
                borderLeft: index === 0 ? "2px solid var(--accent)" : "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                padding: 10,
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <Badge
                  label={String(index + 1)}
                  tone={
                    index === 0
                      ? { bg: "var(--danger-bg)", fg: "var(--danger)", border: "transparent" }
                      : undefined
                  }
                />
                <div style={{ flex: 1 }}>
                  <Select
                    ariaLabel="Action type"
                    disabled={readOnly}
                    value={action.type}
                    onChange={(value) =>
                      updateAction(index, { type: value as ActionType, config: {} })
                    }
                    options={ACTIONS.map((a) => ({
                      value: a.value,
                      label: a.label,
                      disabled: !a.available,
                    }))}
                    triggerStyle={{ width: "100%" }}
                  />
                </div>
                {!readOnly && (
                  <Button variant="text" type="button" onClick={() => removeAction(index)}>
                    ✕
                  </Button>
                )}
              </div>
              {action.type === "create_task" && (
                <input
                  disabled={readOnly}
                  placeholder="Task title"
                  value={(action.config?.title as string) ?? ""}
                  onChange={(event) => updateActionConfig(index, "title", event.target.value)}
                />
              )}
              {action.type === "change_stage" && (
                <Select
                  ariaLabel="Target stage"
                  disabled={readOnly}
                  value={(action.config?.to_stage_id as string) ?? ""}
                  onChange={(value) => updateActionConfig(index, "to_stage_id", value)}
                  options={[
                    { value: "", label: "Select a stage…" },
                    ...stages.map((s) => ({ value: s.id, label: s.name })),
                  ]}
                />
              )}
              {action.type === "notify_manager" && (
                <input
                  disabled={readOnly}
                  placeholder="Message"
                  value={(action.config?.message as string) ?? ""}
                  onChange={(event) => updateActionConfig(index, "message", event.target.value)}
                />
              )}
            </div>
          ))}
          {!readOnly && (
            <Button variant="text" type="button" onClick={addAction}>
              + Add action
            </Button>
          )}
        </div>
      </div>

      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-sm)",
          padding: 10,
        }}
      >
        <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
          Plain-English preview
        </span>
        <p style={{ margin: "8px 0 0", fontSize: "var(--text-sm)" }}>{previewSentence}</p>
      </div>

      {testResult && (
        <p style={{ fontSize: "var(--text-sm)", margin: 0 }}>
          Checked {testResult.candidates_checked} recent record(s) — {testResult.matched.length}{" "}
          would match
          {testResult.matched.length > 0 &&
            `: ${testResult.matched.map((m) => m.label).join(", ")}`}
          .
        </p>
      )}
      {testError && (
        <p role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)", margin: 0 }}>
          {testError}
        </p>
      )}
      {saveError && (
        <p role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)", margin: 0 }}>
          {saveError}
        </p>
      )}

      <div style={{ display: "flex", gap: 10 }}>
        <Button variant="secondary" type="button" disabled={testing} onClick={() => void handleTestRun()}>
          {testing ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Spinner size={12} /> Testing…
            </span>
          ) : (
            "Test run"
          )}
        </Button>
        <div style={{ flex: 1 }} />
        <Button variant="secondary" type="button" onClick={onCancel}>
          {readOnly ? "Close" : "Cancel"}
        </Button>
        {!readOnly && (
          <Button
            variant="primary"
            type="button"
            disabled={saving || !name.trim() || actions.length === 0}
            onClick={() => void handleSave()}
          >
            {saving ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Spinner size={12} /> Saving…
              </span>
            ) : (
              "Save rule"
            )}
          </Button>
        )}
      </div>
    </div>
  );
}
