import { apiGet, apiPost } from "./client";
import type { DataEnvelope } from "./types";

export interface Course {
  id: string;
  name: string;
  code: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export async function listCourses(token: string): Promise<DataEnvelope<Course[]>> {
  return apiGet<DataEnvelope<Course[]>>(token, "/api/v1/courses");
}

export async function createCourse(
  token: string,
  input: { name: string; code: string },
): Promise<DataEnvelope<Course>> {
  return apiPost<DataEnvelope<Course>>(token, "/api/v1/courses", input);
}
