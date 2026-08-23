import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchMe } from "../api/bff";
import { useAuth } from "../auth/context";
import { MeShell } from "../MeShell";

vi.mock("../auth/context", () => ({
  useAuth: vi.fn(),
}));
vi.mock("../api/bff", () => ({
  fetchMe: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedFetchMe = vi.mocked(fetchMe);

afterEach(() => {
  vi.resetAllMocks();
});

describe("MeShell", () => {
  it("shows the user and tenant once /api/v1/me resolves", async () => {
    mockedUseAuth.mockReturnValue({
      authenticated: true,
      token: "test-token",
      logout: vi.fn(),
    });
    mockedFetchMe.mockResolvedValue({
      data: {
        user: {
          id: "u1",
          email: "counselor.a@example.test",
          full_name: "Asha Rao",
          role: "counselor",
          status: "active",
        },
        tenant: { id: "t1", slug: "tenant-a", name: "Tenant A Academy" },
      },
      meta: { request_id: "r1" },
    });

    render(<MeShell />);

    await waitFor(() => {
      expect(screen.getByText(/Asha Rao/)).toBeInTheDocument();
      expect(screen.getByText(/Tenant A Academy/)).toBeInTheDocument();
    });
    expect(mockedFetchMe).toHaveBeenCalledWith("test-token");
  });

  it("shows an error message when the BFF call fails", async () => {
    mockedUseAuth.mockReturnValue({
      authenticated: true,
      token: "test-token",
      logout: vi.fn(),
    });
    mockedFetchMe.mockRejectedValue(new Error("boom"));

    render(<MeShell />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("boom");
    });
  });
});
