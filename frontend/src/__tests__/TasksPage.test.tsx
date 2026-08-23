import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { listTasks, updateTask } from "../api/tasks";
import { useAuth } from "../auth/context";
import { TasksPage } from "../pages/TasksPage";
import { useMe } from "../useMe";

vi.mock("../auth/context", () => ({ useAuth: vi.fn() }));
vi.mock("../useMe", () => ({ useMe: vi.fn() }));
vi.mock("../api/tasks", () => ({ listTasks: vi.fn(), updateTask: vi.fn(), createTask: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseMe = vi.mocked(useMe);
const mockedListTasks = vi.mocked(listTasks);
const mockedUpdateTask = vi.mocked(updateTask);

const TASK = {
  id: "t1",
  contact_id: "c1",
  deal_id: null,
  assignee_id: "u1",
  title: "Call back",
  description: null,
  due_at: null,
  status: "open" as const,
  completed_at: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

afterEach(() => {
  vi.resetAllMocks();
});

function setup() {
  mockedUseAuth.mockReturnValue({ authenticated: true, token: "test-token", logout: vi.fn() });
  mockedUseMe.mockReturnValue({
    me: {
      user: { id: "u1", email: "a@example.test", full_name: "Asha", role: "counselor", status: "active" },
      tenant: { id: "t1", slug: "tenant-a", name: "Tenant A" },
    },
    error: undefined,
  });
}

describe("TasksPage complete/undo", () => {
  it("optimistically removes a completed task and shows Undo", async () => {
    setup();
    mockedListTasks.mockResolvedValue({
      data: [TASK],
      meta: { request_id: "r1", page: 1, page_size: 100, total: 1 },
    });
    mockedUpdateTask.mockResolvedValue({ data: { ...TASK, status: "done" }, meta: { request_id: "r1" } });

    render(<TasksPage />);
    await waitFor(() => expect(screen.getByText("Call back")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Complete Call back"));

    await waitFor(() => expect(screen.queryByText("Call back")).not.toBeInTheDocument());
    expect(screen.getByText(/Completed "Call back"/)).toBeInTheDocument();
    expect(mockedUpdateTask).toHaveBeenCalledWith("test-token", "t1", { status: "done" });
  });

  it("clicking Undo restores the task and reverses the status", async () => {
    setup();
    mockedListTasks.mockResolvedValue({
      data: [TASK],
      meta: { request_id: "r1", page: 1, page_size: 100, total: 1 },
    });
    mockedUpdateTask.mockResolvedValue({ data: { ...TASK, status: "done" }, meta: { request_id: "r1" } });

    render(<TasksPage />);
    await waitFor(() => expect(screen.getByText("Call back")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("Complete Call back"));
    await waitFor(() => expect(screen.getByText(/Completed/)).toBeInTheDocument());

    fireEvent.click(screen.getByText("Undo"));

    await waitFor(() => expect(screen.getByText("Call back")).toBeInTheDocument());
    expect(mockedUpdateTask).toHaveBeenLastCalledWith("test-token", "t1", { status: "open" });
  });

  it("reverts on failure instead of showing Undo", async () => {
    setup();
    mockedListTasks.mockResolvedValue({
      data: [TASK],
      meta: { request_id: "r1", page: 1, page_size: 100, total: 1 },
    });
    mockedUpdateTask.mockRejectedValue(new Error("network error"));

    render(<TasksPage />);
    await waitFor(() => expect(screen.getByText("Call back")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("Complete Call back"));

    await waitFor(() => expect(screen.getByText("Call back")).toBeInTheDocument());
    expect(screen.queryByText(/Completed/)).not.toBeInTheDocument();
  });
});
