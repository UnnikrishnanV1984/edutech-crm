import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { listTasks } from "../api/tasks";
import { useAuth } from "../auth/context";
import { Sidebar } from "../Sidebar";
import { useMe } from "../useMe";

vi.mock("../auth/context", () => ({ useAuth: vi.fn() }));
vi.mock("../useMe", () => ({ useMe: vi.fn() }));
vi.mock("../api/tasks", () => ({ listTasks: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseMe = vi.mocked(useMe);
const mockedListTasks = vi.mocked(listTasks);

afterEach(() => {
  vi.resetAllMocks();
});

function setup(role: "counselor" | "manager" | "admin" = "admin") {
  mockedUseAuth.mockReturnValue({ authenticated: true, token: "test-token", logout: vi.fn() });
  mockedUseMe.mockReturnValue({
    me: {
      user: { id: "u1", email: "a@example.test", full_name: "Asha", role, status: "active" },
      tenant: { id: "t1", slug: "tenant-a", name: "Acme Academy" },
    },
    error: undefined,
  });
  mockedListTasks.mockResolvedValue({
    data: [],
    meta: { request_id: "r1", page: 1, page_size: 100, total: 0 },
  });
}

function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );
}

describe("Sidebar nav", () => {
  it("shows a single Configurations link for an admin, not the three old admin links", async () => {
    setup("admin");
    renderSidebar();

    expect(await screen.findByText("Configurations")).toBeInTheDocument();
    expect(screen.queryByText("SLA policies")).not.toBeInTheDocument();
    expect(screen.queryByText("Integrations")).not.toBeInTheDocument();
  });

  it("hides the Admin group entirely for a manager", async () => {
    setup("manager");
    renderSidebar();

    await waitFor(() => expect(screen.getByText("Escalations")).toBeInTheDocument());
    expect(screen.queryByText("Configurations")).not.toBeInTheDocument();
  });

  it("hides the Team and Admin groups for a counselor", async () => {
    setup("counselor");
    renderSidebar();

    await waitFor(() => expect(screen.getByText("Dashboard")).toBeInTheDocument());
    expect(screen.queryByText("Escalations")).not.toBeInTheDocument();
    expect(screen.queryByText("Configurations")).not.toBeInTheDocument();
  });
});
