import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  OrganizationContext,
  type OrganizationContextType,
} from "../context/OrganizationContext";
import { orgContext } from "../test/utils";

const api = vi.hoisted(() => ({ createOrganization: vi.fn() }));
const auth = vi.hoisted(() => ({ refreshUser: vi.fn() }));

vi.mock("../api/tenants", () => ({
  createOrganization: api.createOrganization,
}));

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({ refreshUser: auth.refreshUser }),
}));

import WorkspaceSwitcher from "./WorkspaceSwitcher";

function renderSwitcher(context: OrganizationContextType) {
  return render(
    <OrganizationContext.Provider value={context}>
      <WorkspaceSwitcher />
    </OrganizationContext.Provider>,
  );
}

function openAddForm() {
  fireEvent.click(screen.getByRole("button", { name: /Workspace/ }));
  fireEvent.click(screen.getByRole("button", { name: /Add workspace/ }));
}

describe("WorkspaceSwitcher - Add workspace", () => {
  beforeEach(() => {
    api.createOrganization.mockReset();
    auth.refreshUser.mockReset().mockResolvedValue(null);
  });

  it("creates a workspace and switches to it", async () => {
    const context = { ...orgContext(), selectNewOrganization: vi.fn() };
    api.createOrganization.mockResolvedValue({
      id: "org-new",
      name: "Hassan Labs",
      slug: "hassan-labs",
      role: "OWNER",
    });

    renderSwitcher(context);
    openAddForm();

    fireEvent.change(screen.getByLabelText("New workspace name"), {
      target: { value: "  Hassan Labs " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(context.selectNewOrganization).toHaveBeenCalledWith("org-new"),
    );
    expect(api.createOrganization).toHaveBeenCalledWith({
      name: "Hassan Labs",
    });
    expect(auth.refreshUser).toHaveBeenCalled();
  });

  it("asks for a name before calling the API", () => {
    renderSwitcher(orgContext());
    openAddForm();

    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(
      screen.getByText("Please enter a workspace name."),
    ).toBeInTheDocument();
    expect(api.createOrganization).not.toHaveBeenCalled();
  });

  it("shows the server's reason when creation fails", async () => {
    api.createOrganization.mockRejectedValue({
      response: { data: { detail: "You can own at most 10 workspaces." } },
    });

    renderSwitcher(orgContext());
    openAddForm();

    fireEvent.change(screen.getByLabelText("New workspace name"), {
      target: { value: "One more" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(
      await screen.findByText("You can own at most 10 workspaces."),
    ).toBeInTheDocument();
  });

  it("cancel closes the form", () => {
    renderSwitcher(orgContext());
    openAddForm();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByLabelText("New workspace name")).toBeNull();
    expect(
      screen.getByRole("button", { name: /Add workspace/ }),
    ).toBeInTheDocument();
  });
});
