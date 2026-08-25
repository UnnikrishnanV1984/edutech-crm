import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  listFollowUpFlags,
  resolveFollowUpFlag,
  snoozeFollowUpFlag,
  type FollowUpFlag,
} from "../api/followUpFlags";
import { useAuth } from "../auth/context";
import { FollowUpFlagsPage } from "../pages/FollowUpFlagsPage";
import { useMe } from "../useMe";
import { userDisplayName, useUsers } from "../useUsers";

vi.mock("../auth/context", () => ({ useAuth: vi.fn() }));
vi.mock("../useMe", () => ({ useMe: vi.fn() }));
vi.mock("../useUsers", () => ({ useUsers: vi.fn(), userDisplayName: vi.fn() }));
vi.mock("../api/followUpFlags", () => ({
  listFollowUpFlags: vi.fn(),
  resolveFollowUpFlag: vi.fn(),
  snoozeFollowUpFlag: vi.fn(),
  createFollowUpFlag: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseMe = vi.mocked(useMe);
const mockedUseUsers = vi.mocked(useUsers);
const mockedUserDisplayName = vi.mocked(userDisplayName);
const mockedListFlags = vi.mocked(listFollowUpFlags);
const mockedResolveFlag = vi.mocked(resolveFollowUpFlag);
const mockedSnoozeFlag = vi.mocked(snoozeFollowUpFlag);

function isoDate(daysFromToday: number): string {
  const date = new Date();
  date.setDate(date.getDate() + daysFromToday);
  return date.toISOString().slice(0, 10);
}

function makeFlag(overrides: Partial<FollowUpFlag>): FollowUpFlag {
  return {
    id: "f1",
    manager_id: "u1",
    deal_id: null,
    contact_id: "c1",
    note: "check in",
    remind_on: isoDate(0),
    resolved_at: null,
    created_at: "2026-01-01T00:00:00Z",
    resolved_contact_id: "c1",
    contact_name: "Priya Shah",
    manager_name: "Asha Manager",
    ...overrides,
  };
}

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
  mockedUseUsers.mockReturnValue([]);
  mockedUserDisplayName.mockReturnValue("Someone");
}

function renderPage() {
  return render(
    <MemoryRouter>
      <FollowUpFlagsPage />
    </MemoryRouter>,
  );
}

describe("FollowUpFlagsPage", () => {
  it("shows a managers/admins-only message for a counselor", () => {
    setup("counselor");
    mockedListFlags.mockResolvedValue({ data: [], meta: { request_id: "r1" } });
    renderPage();
    expect(screen.getByText("Managers and admins only")).toBeInTheDocument();
  });

  it("buckets flags into Overdue/Due today/This week/Snoozed columns", async () => {
    setup();
    mockedListFlags.mockResolvedValue({
      data: [
        makeFlag({ id: "overdue", remind_on: isoDate(-2), contact_name: "Overdue Contact" }),
        makeFlag({ id: "today", remind_on: isoDate(0), contact_name: "Today Contact" }),
        makeFlag({ id: "week", remind_on: isoDate(3), contact_name: "This Week Contact" }),
        makeFlag({ id: "later", remind_on: isoDate(30), contact_name: "Later Contact" }),
      ],
      meta: { request_id: "r1" },
    });

    renderPage();

    await waitFor(() => expect(screen.getAllByText("Overdue Contact").length).toBeGreaterThan(0));
    expect(screen.getAllByText("Today Contact").length).toBeGreaterThan(0);
    expect(screen.getAllByText("This Week Contact").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Later Contact").length).toBeGreaterThan(0);
  });

  it("shows the Mine control and resource-list dropdown for an admin", async () => {
    setup("admin");
    mockedListFlags.mockResolvedValue({ data: [], meta: { request_id: "r1" } });

    renderPage();

    await waitFor(() => expect(screen.getByText("Mine")).toBeInTheDocument());
    expect(screen.getByLabelText("Filter by owner")).toBeInTheDocument();
    expect(screen.getByText("Everyone")).toBeInTheDocument();
  });

  it("shows the same Mine + Everyone + resource-list control for a manager, not a Mine/My-team toggle", async () => {
    // REQUIREMENTS.md §4.3 (revised) — Follow-ups is team-wide visibility
    // for any Manager or Admin, unlike the shared OwnerFilter's manager
    // branch used elsewhere in the app.
    setup("manager");
    mockedListFlags.mockResolvedValue({ data: [], meta: { request_id: "r1" } });

    renderPage();

    await waitFor(() => expect(screen.getByText("Mine")).toBeInTheDocument());
    expect(screen.getByLabelText("Filter by owner")).toBeInTheDocument();
    expect(screen.getByText("Everyone")).toBeInTheDocument();
    expect(screen.queryByText("My team")).not.toBeInTheDocument();
  });

  it("re-fetches with the selected resource when the dropdown changes", async () => {
    setup("admin");
    mockedListFlags.mockResolvedValue({ data: [], meta: { request_id: "r1" } });
    mockedUseUsers.mockReturnValue([
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
    mockedUserDisplayName.mockReturnValue("Beth Manager");

    renderPage();
    await waitFor(() =>
      expect(mockedListFlags).toHaveBeenCalledWith("test-token", { manager_id: undefined }),
    );

    fireEvent.change(screen.getByLabelText("Filter by owner"), { target: { value: "u2" } });

    await waitFor(() =>
      expect(mockedListFlags).toHaveBeenLastCalledWith("test-token", { manager_id: "u2" }),
    );
  });

  it("resolving a flag via Done removes it from the queue", async () => {
    setup();
    const flag = makeFlag({});
    mockedListFlags.mockResolvedValue({ data: [flag], meta: { request_id: "r1" } });
    mockedResolveFlag.mockResolvedValue({
      data: { ...flag, resolved_at: "2026-01-02T00:00:00Z" },
      meta: { request_id: "r1" },
    });

    renderPage();
    await waitFor(() => expect(screen.getAllByText("Priya Shah").length).toBeGreaterThan(0));

    fireEvent.click(screen.getAllByText("Done").at(0)!);

    await waitFor(() => expect(mockedResolveFlag).toHaveBeenCalledWith("test-token", "f1"));
    await waitFor(() => expect(screen.queryByText("Priya Shah")).not.toBeInTheDocument());
  });

  it("snoozing a flag confirms a new remind_on date", async () => {
    setup();
    const flag = makeFlag({ remind_on: isoDate(-1) }); // overdue -> has Snooze action
    mockedListFlags.mockResolvedValue({ data: [flag], meta: { request_id: "r1" } });
    mockedSnoozeFlag.mockResolvedValue({
      data: { ...flag, remind_on: isoDate(14) },
      meta: { request_id: "r1" },
    });

    renderPage();
    await waitFor(() => expect(screen.getAllByText("Priya Shah").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByText("Snooze"));
    fireEvent.click(screen.getByText("Confirm"));

    await waitFor(() =>
      expect(mockedSnoozeFlag).toHaveBeenCalledWith("test-token", "f1", expect.any(String)),
    );
  });
});
