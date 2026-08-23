import { useEffect, useState } from "react";

import { listCourses, type Course } from "../api/courses";
import { createDeal, type Deal } from "../api/deals";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { SlideOverPanel } from "../components/SlideOverPanel";

interface CreateDealPanelProps {
  contactId: string;
  onClose: () => void;
  onCreated: (deal: Deal) => void;
}

export function CreateDealPanel({ contactId, onClose, onCreated }: CreateDealPanelProps) {
  const { token } = useAuth();
  const [courses, setCourses] = useState<Course[]>([]);
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [courseId, setCourseId] = useState("");
  const [stageId, setStageId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!token) {
      return;
    }
    listCourses(token).then((response) => {
      setCourses(response.data);
      if (response.data.length > 0) {
        setCourseId(response.data[0]!.id);
      }
    });
    listPipelineStages(token).then((response) => setStages(response.data));
  }, [token]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token || !courseId) {
      return;
    }
    setSubmitting(true);
    setError(undefined);
    try {
      const response = await createDeal(token, contactId, {
        course_id: courseId,
        stage_id: stageId || undefined,
      });
      onCreated(response.data);
    } catch {
      setError("Couldn't create deal — try again");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SlideOverPanel title="New Deal" onClose={onClose}>
      {courses.length === 0 ? (
        <p style={{ color: "var(--text-muted)" }}>
          No courses yet — create one in course settings first.
        </p>
      ) : (
        <form
          onSubmit={(event) => {
            void handleSubmit(event);
          }}
          style={{ display: "flex", flexDirection: "column", gap: 12 }}
        >
          <label>
            Course
            <select
              value={courseId}
              onChange={(event) => setCourseId(event.target.value)}
              style={{ display: "block", width: "100%", marginTop: 4 }}
            >
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Stage
            <select
              value={stageId}
              onChange={(event) => setStageId(event.target.value)}
              style={{ display: "block", width: "100%", marginTop: 4 }}
            >
              <option value="">First open stage</option>
              {stages.map((stage) => (
                <option key={stage.id} value={stage.id}>
                  {stage.name}
                </option>
              ))}
            </select>
          </label>
          {error && (
            <p role="alert" style={{ color: "var(--danger)" }}>
              {error}
            </p>
          )}
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <Button variant="secondary" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" disabled={submitting}>
              {submitting ? "Creating…" : "Create Deal"}
            </Button>
          </div>
        </form>
      )}
    </SlideOverPanel>
  );
}
