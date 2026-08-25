import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getContact } from "../api/contacts";
import { listTasks, updateTask } from "../api/tasks";
import { useAuth } from "../auth/context";
import { TasksPage } from "../pages/TasksPage";
import { useMe } from "../useMe";
import { userDisplayName, useUsers } from "../useUsers";

vi.mock("../auth/context", () => ({ useAuth: vi.fn() }));
vi.mock("../useMe", () => ({ useMe: vi.fn() }));
vi.mock("../useUsers", () => ({ useUsers: vi.fn(), userDisplayName: vi.fn() }));
vi.mock("../api/tasks", () => ({ listTasks: vi.fn(), updateTask: vi.fn(), createTask: vi.fn() }));
vi.mock("../api/contacts", () => ({ getContact: vi.fn(), listContacts: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseMe = vi.mocked(useMe);
const mockedUseUsers = vi.mocked(useUsers);
const mockedUserDisplayName = vi.mocked(userDisplayName);
const mockedListTasks = vi.mocked(listTasks);
const mockedUpdateTask = vi.mocked(updateTask);
const mockedGetContact = vi.mocked(getContact);

function renderTasksPage() {
  return render(
    <MemoryRouter>
      <TasksPage />
    </MemoryRouter>,
  );
}

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

function setup(role: "counselor" | "manager" | "admin" = "counselor") {
  mockedUseAuth.mockReturnValue({ authenticated: true, token: "test-token", logout: vi.fn() });
  mockedUseMe.mockReturnValue({
    me: {
      user: { id: "u1", email: "a@example.test", full_name: "Asha", role, status: "active" },
      tenant: { id: "t1", slug: "tenant-a", name: "Tenant A" },
    },
    error: undefined,
  });
  mockedUseUsers.mockReturnValue([]);
  mockedUserDisplayName.mockReturnValue("Someone");
  mockedGetContact.mockResolvedValue({
    data: {
      id: "c1",
      full_name: "Priya Shah",
      email: null,
      phone: null,
      lead_source: "web",
      owner_id: "u1",
      status: "active",
      territory: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      current_deal_id: null,
      stage_id: null,
      stage_name: null,
      sla_state: null,
      sla_target_at: null,
      sla_target_minutes: null,
      has_open_follow_up: false,
    },
    meta: { request_id: "r1" },
  });
}

describe("TasksPage complete/undo", () => {
  it("optimistically strikes through a completed task and shows an inline Undo", async () => {
    setup();
    mockedListTasks.mockResolvedValue({
      data: [TASK],
      meta: { request_id: "r1", page: 1, page_size: 100, total: 1 },
    });
    mockedUpdateTask.mockResolvedValue({ data: { ...TASK, status: "done" }, meta: { request_id: "r1" } });

    renderTasksPage();
    await waitFor(() => expect(screen.getByText("Call back")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Complete Call back"));

    await waitFor(() => expect(screen.getByText("Undo")).toBeInTheDocument());
    // The row stays in place (struck through), unlike the old page-level banner.
    expect(screen.getByText("Call back")).toBeInTheDocument();
    expect(mockedUpdateTask).toHaveBeenCalledWith("test-token", "t1", { status: "done" });
  });

  it("clicking the inline Undo restores the task and reverses the status", async () => {
    setup();
    mockedListTasks.mockResolvedValue({
      data: [TASK],
      meta: { request_id: "r1", page: 1, page_size: 100, total: 1 },
    });
    mockedUpdateTask.mockResolvedValue({ data: { ...TASK, status: "done" }, meta: { request_id: "r1" } });

    renderTasksPage();
    await waitFor(() => expect(screen.getByText("Call back")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("Complete Call back"));
    await waitFor(() => expect(screen.getByText("Undo")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Undo"));

    await waitFor(() => expect(screen.queryByText("Undo")).not.toBeInTheDocument());
    expect(screen.getByText("Call back")).toBeInTheDocument();
    expect(mockedUpdateTask).toHaveBeenLastCalledWith("test-token", "t1", { status: "open" });
  });

  it("reverts on failure instead of showing Undo", async () => {
    setup();
    mockedListTasks.mockResolvedValue({
      data: [TASK],
      meta: { request_id: "r1", page: 1, page_size: 100, total: 1 },
    });
    mockedUpdateTask.mockRejectedValue(new Error("network error"));

    renderTasksPage();
    await waitFor(() => expect(screen.getByText("Call back")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("Complete Call back"));

    await waitFor(() => expect(screen.getByLabelText("Complete Call back")).not.toBeChecked());
    expect(screen.getByText("Call back")).toBeInTheDocument();
    expect(screen.queryByText("Undo")).not.toBeInTheDocument();
  });
});

describe("TasksPage owner filter", () => {
  // ADMIN_UX_IMPROVEMENTS_PLAN.md Sec5/Sec8 — one control per role, not
  // one control shown/hidden.
  it("shows no Mine/Everyone control for a counselor", async () => {
    setup("counselor");
    mockedListTasks.mockResolvedValue({
      data: [],
      meta: { request_id: "r1", page: 1, page_size: 100, total: 0 },
    });

    renderTasksPage();
    await waitFor(() => expect(mockedListTasks).toHaveBeenCalled());

    expect(screen.queryByText("Mine")).not.toBeInTheDocument();
    expect(screen.queryByText("Everyone")).not.toBeInTheDocument();
    expect(screen.queryByText("My team")).not.toBeInTheDocument();
  });

  it("shows a Mine/My team toggle for a manager, never labeled Everyone", async () => {
    setup("manager");
    mockedListTasks.mockResolvedValue({
      data: [],
      meta: { request_id: "r1", page: 1, page_size: 100, total: 0 },
    });

    renderTasksPage();
    await waitFor(() => expect(screen.getByText("Mine")).toBeInTheDocument());

    expect(screen.queryByText("Everyone")).not.toBeInTheDocument();
  });

  it("shows a Mine button plus an owner dropdown for an admin", async () => {
    setup("admin");
    mockedListTasks.mockResolvedValue({
      data: [],
      meta: { request_id: "r1", page: 1, page_size: 100, total: 0 },
    });

    renderTasksPage();
    await waitFor(() => expect(screen.getByText("Mine")).toBeInTheDocument());

    expect(screen.getByLabelText("Filter by owner")).toBeInTheDocument();
    expect(screen.getByText("Everyone")).toBeInTheDocument();
  });

  it("defaults an admin to Everyone, not Mine", async () => {
    setup("admin");
    mockedListTasks.mockResolvedValue({
      data: [],
      meta: { request_id: "r1", page: 1, page_size: 100, total: 0 },
    });

    renderTasksPage();
    await waitFor(() =>
      expect(screen.getByLabelText<HTMLSelectElement>("Filter by owner").value).toBe("everyone"),
    );
    // The default load should have gone out with no assignee_id filter.
    const lastCall = mockedListTasks.mock.calls.at(-1)!;
    expect(lastCall[1]?.assignee_id).toBeUndefined();
  });
});

describe("TasksPage board view", () => {
  it("fetches and renders done tasks when Board is selected", async () => {
    setup("counselor");
    mockedListTasks.mockImplementation((_token, params) => {
      if (params?.status === "done") {
        return Promise.resolve({
          data: [{ ...TASK, id: "t2", title: "Send welcome email", status: "done" as const }],
          meta: { request_id: "r1", page: 1, page_size: 100, total: 1 },
        });
      }
      return Promise.resolve({
        data: [TASK],
        meta: { request_id: "r1", page: 1, page_size: 100, total: 1 },
      });
    });

    renderTasksPage();
    await waitFor(() => expect(screen.getByText("Call back")).toBeInTheDocument());

    expect(mockedListTasks).not.toHaveBeenCalledWith(
      "test-token",
      expect.objectContaining({ status: "done" }),
    );

    fireEvent.click(screen.getByText("Board"));

    await waitFor(() => expect(screen.getByText("Send welcome email")).toBeInTheDocument());
    expect(mockedListTasks).toHaveBeenCalledWith(
      "test-token",
      expect.objectContaining({ status: "done" }),
    );
  });
});
