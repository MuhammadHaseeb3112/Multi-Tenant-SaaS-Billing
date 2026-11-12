import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const logout = vi.fn();

vi.mock("../WorkspaceSwitcher", () => ({
  default: () => <div>workspace</div>,
}));

vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({ logout }),
}));

import AppLayout from "./AppLayout";

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<h1>Dashboard page</h1>} />
          <Route path="/usage" element={<h1>Usage page</h1>} />
          <Route path="/team" element={<h1>Team page</h1>} />
          <Route path="/audit" element={<h1>Audit page</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

describe("AppLayout", () => {
  it("shows the sidebar on every signed-in page", () => {
    renderAt("/usage");

    expect(screen.getByRole("heading", { name: "Usage page" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Usage" })).toHaveClass("active");
  });

  it("switches pages straight from the sidebar", () => {
    renderAt("/usage");

    fireEvent.click(screen.getByRole("button", { name: "Team" }));

    expect(screen.getByRole("heading", { name: "Team page" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Team" })).toHaveClass("active");
  });

  it("links to the activity log", () => {
    renderAt("/usage");

    fireEvent.click(screen.getByRole("button", { name: "Activity log" }));

    expect(screen.getByRole("heading", { name: "Audit page" })).toBeInTheDocument();
  });

  it("has a menu button for small screens except on the dashboard", () => {
    const { unmount } = renderAt("/usage");
    expect(screen.getByRole("button", { name: "Open menu" })).toBeInTheDocument();
    unmount();

    renderAt("/dashboard");
    expect(screen.queryByRole("button", { name: "Open menu" })).toBeNull();
  });

  it("names the page in the small-screen top bar", () => {
    renderAt("/team");

    const bar = screen.getByRole("banner");

    expect(bar).toHaveTextContent("Team");
    expect(bar).toContainElement(
      screen.getByRole("button", { name: "Open menu" }),
    );
  });

  it("signs out from the sidebar", () => {
    renderAt("/team");

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(logout).toHaveBeenCalled();
  });
});
