import { useEffect, useState } from "react";

import { listContactActivities, type Activity } from "../api/contacts";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { Spinner } from "../components/Spinner";
import { relativeTime } from "../relativeTime";
import { userDisplayName, useUsers } from "../useUsers";

interface ActivitySectionProps {
  contactId: string;
}

function describeActivity(activity: Activity, stageName: (id: string) => string): string {
  const payload = activity.payload as Record<string, unknown> | null;
  if (activity.type === "deal_stage_changed" && payload && typeof payload.old_stage_id === "string") {
    return `Moved ${stageName(payload.old_stage_id)} → ${stageName(String(payload.new_stage_id))}`;
  }
  if (activity.type === "manual_note" && payload && typeof payload.note === "string") {
    const channel = typeof payload.channel === "string" ? payload.channel : "note";
    const label = channel.charAt(0).toUpperCase() + channel.slice(1);
    return `${label}: ${payload.note}`;
  }
  if (activity.type === "lead_captured") {
    return "Lead captured";
  }
  return activity.type.replace(/_/g, " ");
}

export function ActivitySection({ contactId }: ActivitySectionProps) {
  const { token } = useAuth();
  const users = useUsers();
  const [activities, setActivities] = useState<Activity[] | undefined>(undefined);
  const [stages, setStages] = useState<PipelineStage[]>([]);

  useEffect(() => {
    if (!token) return;
    listContactActivities(token, contactId).then((response) => setActivities(response.data));
    listPipelineStages(token).then((response) => setStages(response.data));
  }, [token, contactId]);

  function stageName(stageId: string) {
    return stages.find((s) => s.id === stageId)?.name ?? "Unknown stage";
  }

  return (
    <Card title="Activity">
      {activities === undefined && (
        <div style={{ padding: 8 }}>
          <Spinner size={16} />
        </div>
      )}
      {activities && activities.length === 0 && <EmptyState headline="No activity yet" />}
      {activities && activities.length > 0 && (
        <div>
          {activities.map((activity, index) => (
            <div key={activity.id} style={{ display: "flex", gap: 11 }}>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                <div
                  style={{
                    width: 9,
                    height: 9,
                    borderRadius: "50%",
                    background: index === 0 ? "var(--accent)" : "var(--text-muted)",
                    flexShrink: 0,
                  }}
                />
                {index < activities.length - 1 && (
                  <div style={{ width: 1, flex: 1, background: "var(--border)" }} />
                )}
              </div>
              <div style={{ paddingBottom: 16, flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: "var(--text-sm)" }}>{describeActivity(activity, stageName)}</div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginTop: 2 }}>
                  {userDisplayName(users, activity.actor_id)} · {relativeTime(activity.created_at)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
