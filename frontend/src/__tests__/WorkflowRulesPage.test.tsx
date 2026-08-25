import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { listCourses } from "../api/courses";
import { listPipelineStages } from "../api/pipelineStages";
import { useAuth } from "../auth/context";
import { WorkflowRulesPage } from "../pages/WorkflowRulesPage";
import { useMe } from "../useMe";
import {
  createWorkflowRule,
  decideWorkflowRule,
  listWorkflowRules,
  listWorkflowRuns,
  testRunWorkflowRule,
  type WorkflowRule,
} from "../api/workflowRules";

vi.mock("../auth/context", () => ({ useAuth: vi.fn() }));
vi.mock("../useMe", () => ({ useMe: vi.fn() }));
vi.mock("../api/courses", () => ({ listCourses: vi.fn() }));
vi.mock("../api/pipelineStages", () => ({ listPipelineStages: vi.fn() }));
vi.mock("../api/workflowRules", () => ({
  listWorkflowRules: vi.fn(),
  listWorkflowRuns: vi.fn(),
  createWorkflowRule: vi.fn(),
  updateWorkflowRule: vi.fn(),
  decideWorkflowRule: vi.fn(),
  testRunWorkflowRule: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseMe = vi.mocked(useMe);
const mockedListCourses = vi.mocked(listCourses);
const mockedListStages = vi.mocked(listPipelineStages);
const mockedListRules = vi.mocked(listWorkflowRules);
const mockedListRuns = vi.mocked(listWorkflowRuns);
const mockedCreateRule = vi.mocked(createWorkflowRule);
const mockedDecideRule = vi.mocked(decideWorkflowRule);
const mockedTestRun = vi.mocked(testRunWorkflowRule);

const RULE: WorkflowRule = {
  id: "r1",
  name: "Notify on new lead",
  trigger_type: "lead_created",
  trigger_config: {},
  conditions: [],
  actions: [{ type: "notify_manager", config: { message: "hi" } }],
  status: "active",
  created_by: "u1",
  approved_by: "u1",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

afterEach(() => {
  vi.resetAllMocks();
});

function setup(role: "manager" | "admin" | "counselor" = "admin") {
  mockedUseAuth.mockReturnValue({ authenticated: true, token: "test-token", logout: vi.fn() });
  mockedUseMe.mockReturnValue({
    me: {
      user: { id: "u1", email: "a@example.test", full_name: "Admin", role, status: "active" },
      tenant: { id: "t1", slug: "tenant-a", name: "Tenant A" },
    },
    error: undefined,
  });
  mockedListCourses.mockResolvedValue({ data: [], meta: { request_id: "r1" } });
  mockedListStages.mockResolvedValue({ data: [], meta: { request_id: "r1" } });
  mockedListRuns.mockResolvedValue({
    data: [],
    meta: { request_id: "r1", page: 1, page_size: 100, total: 0 },
  });
}

describe("WorkflowRulesPage", () => {
  it("shows a managers/admins-only message for a counselor", () => {
    setup("counselor");
    mockedListRules.mockResolvedValue({ data: [], meta: { request_id: "r1" } });
    render(<WorkflowRulesPage />);
    expect(screen.getByText("Managers and admins only")).toBeInTheDocument();
  });

  it("renders the rule table with active/paused counts", async () => {
    setup();
    mockedListRules.mockResolvedValue({ data: [RULE], meta: { request_id: "r1" } });

    render(<WorkflowRulesPage />);

    await waitFor(() => expect(screen.getByText("Notify on new lead")).toBeInTheDocument());
    expect(screen.getByText(/01 active/)).toBeInTheDocument();
  });

  it("opens the builder when '+ New rule' is clicked", async () => {
    setup();
    mockedListRules.mockResolvedValue({ data: [], meta: { request_id: "r1" } });

    render(<WorkflowRulesPage />);
    await waitFor(() => expect(mockedListRules).toHaveBeenCalled());

    fireEvent.click(screen.getByText("+ New rule"));

    expect(await screen.findByText("New rule")).toBeInTheDocument();
    expect(screen.getByText("Save rule")).toBeInTheDocument();
  });

  it("opens the run history panel", async () => {
    setup();
    mockedListRules.mockResolvedValue({ data: [RULE], meta: { request_id: "r1" } });

    render(<WorkflowRulesPage />);
    await waitFor(() => expect(screen.getByText("Notify on new lead")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Run history"));

    expect(await screen.findByRole("dialog", { name: "Run history" })).toBeInTheDocument();
  });

  it("saving a new rule as admin creates it as active", async () => {
    setup("admin");
    mockedListRules.mockResolvedValue({ data: [], meta: { request_id: "r1" } });
    mockedCreateRule.mockResolvedValue({ data: RULE, meta: { request_id: "r1" } });

    render(<WorkflowRulesPage />);
    await waitFor(() => expect(mockedListRules).toHaveBeenCalled());

    fireEvent.click(screen.getByText("+ New rule"));
    await screen.findByText("New rule");

    fireEvent.change(screen.getByLabelText("Rule name"), { target: { value: "My new rule" } });
    fireEvent.click(screen.getByText("Save rule"));

    await waitFor(() =>
      expect(mockedCreateRule).toHaveBeenCalledWith(
        "test-token",
        expect.objectContaining({ name: "My new rule", status: "active" }),
      ),
    );
  });

  it("test run shows matching candidates without saving", async () => {
    setup();
    mockedListRules.mockResolvedValue({ data: [], meta: { request_id: "r1" } });
    mockedTestRun.mockResolvedValue({
      data: { candidates_checked: 5, matched: [{ type: "contact", id: "c1", label: "Priya" }] },
      meta: { request_id: "r1" },
    });

    render(<WorkflowRulesPage />);
    await waitFor(() => expect(mockedListRules).toHaveBeenCalled());
    fireEvent.click(screen.getByText("+ New rule"));
    await screen.findByText("New rule");

    fireEvent.click(screen.getByText("Test run"));

    await waitFor(() => expect(mockedTestRun).toHaveBeenCalled());
    expect(await screen.findByText(/Checked 5 recent record/)).toBeInTheDocument();
    expect(mockedCreateRule).not.toHaveBeenCalled();
  });

  it("a manager sees the builder read-only for an existing rule (no Save)", async () => {
    setup("manager");
    mockedListRules.mockResolvedValue({ data: [RULE], meta: { request_id: "r1" } });

    render(<WorkflowRulesPage />);
    await waitFor(() => expect(screen.getByText("Notify on new lead")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Notify on new lead"));

    expect(await screen.findByText("View rule")).toBeInTheDocument();
    expect(screen.queryByText("Save rule")).not.toBeInTheDocument();
  });

  it("admin can approve a pending rule from the row", async () => {
    setup("admin");
    const pending = { ...RULE, status: "pending_approval" as const };
    mockedListRules.mockResolvedValue({ data: [pending], meta: { request_id: "r1" } });
    mockedDecideRule.mockResolvedValue({
      data: { ...pending, status: "active" },
      meta: { request_id: "r1" },
    });

    render(<WorkflowRulesPage />);
    await waitFor(() => expect(screen.getByText("Approve")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Approve"));

    await waitFor(() =>
      expect(mockedDecideRule).toHaveBeenCalledWith("test-token", "r1", "active"),
    );
  });
});
