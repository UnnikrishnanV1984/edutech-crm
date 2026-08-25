import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { listEscalations, updateEscalation, type Escalation } from "../api/escalations";
import { getEscalationSummary } from "../api/reports";
import { useAuth } from "../auth/context";
import { EscalationsPage } from "../pages/EscalationsPage";
import { useMe } from "../useMe";
import { useUsers } from "../useUsers";

vi.mock("../auth/context", () => ({ useAuth: vi.fn() }));
vi.mock("../useMe", () => ({ useMe: vi.fn() }));
vi.mock("../useUsers", () => ({ useUsers: vi.fn(), userDisplayName: vi.fn(() => "Someone") }));
vi.mock("../api/escalations", () => ({
  listEscalations: vi.fn(),
  updateEscalation: vi.fn(),
  raiseEscalation: vi.fn(),
}));
vi.mock("../api/reports", async () => {
  const actual = await vi.importActual<typeof import("../api/reports")>("../api/reports");
  return { ...actual, getEscalationSummary: vi.fn() };
});

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseMe = vi.mocked(useMe);
const mockedUseUsers = vi.mocked(useUsers);
const mockedListEscalations = vi.mocked(listEscalations);
const mockedUpdateEscalation = vi.mocked(updateEscalation);
const mockedGetEscalationSummary = vi.mocked(getEscalationSummary);

const ESCALATION: Escalation = {
  id: "e1",
  source: "sla_breach",
  deal_id: "d1",
  task_id: null,
  sla_state_id: "s1",
  workflow_run_id: null,
  raised_by: null,
  assigned_to: "u1",
  status: "open",
  reason: null,
  resolution_note: null,
  opened_at: "2026-01-01T00:00:00Z",
  acknowledged_at: null,
  resolved_at: null,
  snoozed_until: null,
  was_reopened: false,
  contact_id: "c1",
  contact_name: "Priya Shah",
  rule_name: "First contact SLA",
  assigned_to_name: "Asha Manager",
};

const SUMMARY = { open: 1, breaching_within_1h: 2, avg_resolve_minutes: 120, reopened: 0 };

afterEach(() => {
  vi.resetAllMocks();
});

function setup(role: "manager" | "admin" | "counselor" = "manager") {
  mockedUseAuth.mockReturnValue({ authenticated: true, token: "test-token", logout: vi.fn() });
  mockedUseMe.mockReturnValue({
    me: {
      user: { id: "u1", email: "a@example.test", full_name: "Asha", role, status: "active" },
      tenant: { id: "t1", slug: "tenant-a", name: "Tenant A" },
    },
    error: undefined,
  });
  mockedUseUsers.mockReturnValue([
    {
      id: "u1",
      email: "a@example.test",
      full_name: "Asha Manager",
      role: "manager",
      manager_id: null,
      status: "active",
      territory: null,
    },
    {
      id: "u2",
      email: "b@example.test",
      full_name: "Beth Manager",
      role: "manager",
      manager_id: null,
      status: "active",
      territory: null,
    },
  ]);
  mockedGetEscalationSummary.mockResolvedValue({
    data: SUMMARY,
    meta: { request_id: "r1", cached_at: "2026-01-01T00:00:00Z" },
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <EscalationsPage />
    </MemoryRouter>,
  );
}

describe("EscalationsPage", () => {
  it("shows a managers/admins-only message for a counselor", () => {
    setup("counselor");
    mockedListEscalations.mockResolvedValue({
      data: [],
      meta: { request_id: "r1" },
    });
    renderPage();
    expect(screen.getByText("Managers and admins only")).toBeInTheDocument();
  });

  it("renders the KPI row and the queue table", async () => {
    setup();
    mockedListEscalations.mockResolvedValue({
      data: [ESCALATION],
      meta: { request_id: "r1" },
    });

    renderPage();

    await waitFor(() => expect(screen.getByText("Priya Shah")).toBeInTheDocument());
    expect(screen.getByText("02")).toBeInTheDocument(); // breaching within 1h
    expect(screen.getByText("2h")).toBeInTheDocument(); // avg resolve minutes -> hours
    expect(screen.getByText("First contact SLA")).toBeInTheDocument();
    expect(screen.getByText("Asha Manager")).toBeInTheDocument();
  });

  it("re-fetches with the selected status filter", async () => {
    setup();
    mockedListEscalations.mockResolvedValue({ data: [], meta: { request_id: "r1" } });
    renderPage();

    await waitFor(() =>
      expect(mockedListEscalations).toHaveBeenCalledWith("test-token", { status: "open" }),
    );

    fireEvent.click(screen.getByText("Resolved"));

    await waitFor(() =>
      expect(mockedListEscalations).toHaveBeenLastCalledWith("test-token", { status: "resolved" }),
    );
  });

  it("opens the resolve drawer and resolves with a note", async () => {
    setup();
    mockedListEscalations.mockResolvedValue({ data: [ESCALATION], meta: { request_id: "r1" } });
    mockedUpdateEscalation.mockResolvedValue({
      data: { ...ESCALATION, status: "resolved" },
      meta: { request_id: "r1" },
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("Priya Shah")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Resolve"));
    expect(await screen.findByRole("dialog", { name: "Resolve escalation" })).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("What happened?"), {
      target: { value: "Called back, all good" },
    });
    fireEvent.click(screen.getAllByText("Resolve").at(-1)!);

    await waitFor(() =>
      expect(mockedUpdateEscalation).toHaveBeenCalledWith("test-token", "e1", {
        status: "resolved",
        resolution_note: "Called back, all good",
      }),
    );
    await waitFor(() => expect(screen.queryByText("Priya Shah")).not.toBeInTheDocument());
  });

  it("snoozing requires a snoozed_until before submitting", async () => {
    setup();
    mockedListEscalations.mockResolvedValue({ data: [ESCALATION], meta: { request_id: "r1" } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Priya Shah")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Resolve"));
    await screen.findByRole("dialog", { name: "Resolve escalation" });

    fireEvent.click(screen.getByText("Snooze until…"));
    fireEvent.click(screen.getByRole("button", { name: "Snooze" }));

    expect(mockedUpdateEscalation).not.toHaveBeenCalled();
  });

  it("reassigns to the selected manager", async () => {
    setup();
    mockedListEscalations.mockResolvedValue({ data: [ESCALATION], meta: { request_id: "r1" } });
    mockedUpdateEscalation.mockResolvedValue({
      data: { ...ESCALATION, status: "open", assigned_to: "u2" },
      meta: { request_id: "r1" },
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("Priya Shah")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Resolve"));
    await screen.findByRole("dialog", { name: "Resolve escalation" });

    fireEvent.click(screen.getByText("Reassign owner"));
    fireEvent.change(screen.getByLabelText(/Reassign to/), { target: { value: "u2" } });
    fireEvent.click(screen.getByRole("button", { name: "Reassign" }));

    await waitFor(() =>
      expect(mockedUpdateEscalation).toHaveBeenCalledWith("test-token", "e1", {
        reassign_to: "u2",
      }),
    );
  });
});
