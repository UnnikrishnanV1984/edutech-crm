import { useEffect, useState } from "react";

import { listCourses, type Course } from "../api/courses";
import { createDeal, type Deal } from "../api/deals";
import { listPipelineStages, type PipelineStage } from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { Button } from "../components/Button";
import { Select } from "../components/Select";
import { SlideOverPanel } from "../components/SlideOverPanel";
import { Spinner } from "../components/Spinner";

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
            <div style={{ marginTop: 4 }}>
              <Select
                ariaLabel="Course"
                value={courseId}
                onChange={setCourseId}
                options={courses.map((course) => ({ value: course.id, label: course.name }))}
                triggerStyle={{ width: "100%" }}
              />
            </div>
          </label>
          <label>
            Stage
            <div style={{ marginTop: 4 }}>
              <Select
                ariaLabel="Stage"
                value={stageId}
                onChange={setStageId}
                options={[
                  { value: "", label: "First open stage" },
                  ...stages.map((stage) => ({ value: stage.id, label: stage.name })),
                ]}
                triggerStyle={{ width: "100%" }}
              />
            </div>
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
              {submitting ? (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <Spinner size={12} /> Creating…
                </span>
              ) : (
                "Create Deal"
              )}
            </Button>
          </div>
        </form>
      )}
    </SlideOverPanel>
  );
}
