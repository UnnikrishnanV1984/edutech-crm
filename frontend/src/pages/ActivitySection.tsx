import { useEffect, useState } from "react";

import { listContactActivities, type Activity } from "../api/contacts";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { Spinner } from "../components/Spinner";
import { relativeTime } from "../relativeTime";
import { userDisplayName, useUsers } from "../useUsers";

interface ActivitySectionProps {
  contactId: string;
  hasDeals: boolean;
}

export function ActivitySection({ contactId, hasDeals }: ActivitySectionProps) {
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
    <section>
      <h2 style={{ fontSize: 15 }}>Activity</h2>
      {activities === undefined && (
        <div style={{ padding: 8 }}>
          <Spinner size={16} />
        </div>
      )}
      {activities && activities.length === 0 && (
        <p style={{ color: "var(--text-muted)" }}>
          {hasDeals ? "No activity yet" : "No activity yet"}
        </p>
      )}
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {activities?.map((activity) => (
          <li
            key={activity.id}
            style={{ padding: "8px 0", borderLeft: "2px solid var(--border)", paddingLeft: 12 }}
          >
            {activity.payload && (
              <span>
                Moved {stageName(activity.payload.old_stage_id)} →{" "}
                {stageName(activity.payload.new_stage_id)}
              </span>
            )}
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
              {userDisplayName(users, activity.actor_id)} · {relativeTime(activity.created_at)}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
