import { useEffect, useState } from "react";

import { listCourses, type Course } from "../api/courses";
import { listDeals, type Deal } from "../api/deals";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { stageColor } from "../stageColor";
import { CreateDealPanel } from "./CreateDealPanel";

interface DealsSectionProps {
  contactId: string;
}

export function DealsSection({ contactId }: DealsSectionProps) {
  const { token } = useAuth();
  const [deals, setDeals] = useState<Deal[]>([]);
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [showCreate, setShowCreate] = useState(false);

  function load() {
    if (!token) return;
    listDeals(token, { contact_id: contactId }).then((response) => setDeals(response.data));
    listPipelineStages(token).then((response) => setStages(response.data));
    listCourses(token).then((response) => setCourses(response.data));
  }

  useEffect(load, [token, contactId]);

  function stageFor(stageId: string) {
    const index = stages.findIndex((s) => s.id === stageId);
    const stage = stages[index];
    return stage ? { stage, index } : undefined;
  }

  function courseName(courseId: string | null) {
    if (!courseId) return "General deal"; // non-EdTech deal, no course attached
    return courses.find((c) => c.id === courseId)?.name ?? "Unknown course";
  }

  return (
    <section>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ fontSize: 15 }}>Deals ({deals.length})</h2>
        <Button variant="text" onClick={() => setShowCreate(true)}>
          + New Deal
        </Button>
      </div>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {deals.length === 0 && (
          <li style={{ color: "var(--text-muted)", padding: 8 }}>No deals yet</li>
        )}
        {deals.map((deal) => {
          const stageInfo = stageFor(deal.stage_id);
          return (
            <li
              key={deal.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: 8,
                borderBottom: "1px solid var(--border)",
              }}
            >
              <span>{courseName(deal.course_id)}</span>
              {stageInfo && (
                <Badge label={stageInfo.stage.name} tone={stageColor(stageInfo.stage, stageInfo.index)} />
              )}
            </li>
          );
        })}
      </ul>
      {showCreate && (
        <CreateDealPanel
          contactId={contactId}
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
    </section>
  );
}
