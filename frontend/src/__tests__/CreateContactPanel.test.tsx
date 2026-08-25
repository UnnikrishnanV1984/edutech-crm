import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "../api/client";
import { createContact, getContact } from "../api/contacts";
import { useAuth } from "../auth/context";
import { CreateContactPanel } from "../pages/CreateContactPanel";
import { listUsers } from "../api/users";

vi.mock("../auth/context", () => ({ useAuth: vi.fn() }));
vi.mock("../api/contacts", () => ({ createContact: vi.fn(), getContact: vi.fn() }));
vi.mock("../api/users", () => ({ listUsers: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);
const mockedCreateContact = vi.mocked(createContact);
const mockedGetContact = vi.mocked(getContact);
const mockedListUsers = vi.mocked(listUsers);

afterEach(() => {
  vi.resetAllMocks();
});

function setup() {
  mockedUseAuth.mockReturnValue({ authenticated: true, token: "test-token", logout: vi.fn() });
  mockedListUsers.mockResolvedValue({ data: [], meta: { request_id: "r1" } });
}

describe("CreateContactPanel", () => {
  it("calls onCreated with the new contact on success", async () => {
    setup();
    const newContact = {
      id: "c1",
      full_name: "Alice",
      email: "alice@example.test",
      phone: null,
      lead_source: "web",
      owner_id: "u1",
      status: "active",
      territory: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      stage_id: null,
      stage_name: null,
      sla_state: null,
      has_open_follow_up: false,
    };
    mockedCreateContact.mockResolvedValue({ data: newContact, meta: { request_id: "r1" } });
    const onCreated = vi.fn();

    render(<CreateContactPanel onClose={vi.fn()} onCreated={onCreated} />);

    fireEvent.change(screen.getByLabelText(/Full name/), { target: { value: "Alice" } });
    fireEvent.click(screen.getByText("Create Contact"));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(newContact));
  });

  it("shows the duplicate-contact state on 409 and lets the user open the existing one", async () => {
    setup();
    const existing = {
      id: "existing-1",
      full_name: "Bob",
      email: "bob@example.test",
      phone: null,
      lead_source: "manual",
      owner_id: "u1",
      status: "active",
      territory: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      stage_id: null,
      stage_name: null,
      sla_state: null,
      has_open_follow_up: false,
    };
    mockedCreateContact.mockRejectedValue(
      new ApiRequestError("CONFLICT", "duplicate", [
        { field: "email", issue: "duplicate", existing_contact_id: "existing-1" },
      ]),
    );
    mockedGetContact.mockResolvedValue({ data: existing, meta: { request_id: "r1" } });
    const onCreated = vi.fn();

    render(<CreateContactPanel onClose={vi.fn()} onCreated={onCreated} />);
    fireEvent.change(screen.getByLabelText(/Full name/), { target: { value: "Bob Two" } });
    fireEvent.click(screen.getByText("Create Contact"));

    await waitFor(() => expect(screen.getByText(/possible duplicate/)).toBeInTheDocument());
    expect(screen.getByText("Bob")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Open existing contact"));
    expect(onCreated).toHaveBeenCalledWith(existing);
  });

  it("'Go back' returns to the editable form with values preserved", async () => {
    setup();
    mockedCreateContact.mockRejectedValue(
      new ApiRequestError("CONFLICT", "duplicate", [
        { field: "email", issue: "duplicate", existing_contact_id: "existing-1" },
      ]),
    );
    mockedGetContact.mockResolvedValue({
      data: {
        id: "existing-1",
        full_name: "Bob",
        email: "bob@example.test",
        phone: null,
        lead_source: "manual",
        owner_id: "u1",
        status: "active",
        territory: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        stage_id: null,
        stage_name: null,
        sla_state: null,
        has_open_follow_up: false,
      },
      meta: { request_id: "r1" },
    });

    render(<CreateContactPanel onClose={vi.fn()} onCreated={vi.fn()} />);
    const nameInput = screen.getByLabelText(/Full name/);
    fireEvent.change(nameInput, { target: { value: "Bob Two" } });
    fireEvent.click(screen.getByText("Create Contact"));

    await waitFor(() => expect(screen.getByText("Go back")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Go back"));

    expect(screen.getByLabelText(/Full name/)).toHaveValue("Bob Two");
  });
});
