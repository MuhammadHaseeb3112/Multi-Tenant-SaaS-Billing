import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../components/WorkspaceSwitcher", () => ({
  default: () => <div>workspace</div>,
}));

import RecentInvoices from "./RecentInvoices";
import RevenueOverview from "./RevenueOverview";
import Sidebar from "../../../components/layout/Sidebar";

function CurrentPath() {
  return <div data-testid="path">{useLocation().pathname}</div>;
}

const renderAt = (ui: React.ReactNode, path = "/dashboard") =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="*" element={<>{ui}<CurrentPath /></>} />
      </Routes>
    </MemoryRouter>,
  );

describe("Sidebar", () => {
  it("marks the current page and navigates", () => {
    const onClose = vi.fn();
    renderAt(<Sidebar open={false} onClose={onClose} onLogout={() => {}} />);

    expect(screen.getByRole("button", { name: "Dashboard" })).toHaveClass(
      "active",
    );

    fireEvent.click(screen.getByRole("button", { name: "Invoices" }));

    expect(screen.getByTestId("path")).toHaveTextContent("/invoices");
    expect(onClose).toHaveBeenCalled();
  });

  it("management links and 'View plans' go somewhere (were dead buttons)", () => {
    renderAt(<Sidebar open={false} onClose={() => {}} onLogout={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(screen.getByTestId("path")).toHaveTextContent("/settings");

    fireEvent.click(screen.getByRole("button", { name: "View plans" }));
    expect(screen.getByTestId("path")).toHaveTextContent("/subscriptions");
  });

  it("signs out", () => {
    const onLogout = vi.fn();
    renderAt(<Sidebar open={false} onClose={() => {}} onLogout={onLogout} />);

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(onLogout).toHaveBeenCalled();
  });
});

describe("RevenueOverview", () => {
  it("period dropdown changes the number of months (was ignored)", () => {
    const { container } = renderAt(<RevenueOverview analytics={null} />);
    const labels = () => container.querySelectorAll("text.chart-label");

    expect(labels()).toHaveLength(6);

    fireEvent.change(screen.getByLabelText("Chart period"), {
      target: { value: "12" },
    });
    expect(labels()).toHaveLength(12);

    fireEvent.change(screen.getByLabelText("Chart period"), {
      target: { value: "3" },
    });
    expect(labels()).toHaveLength(3);
  });
});

describe("RecentInvoices", () => {
  const invoice = (number: string, status: string, due: string) =>
    ({
      id: number,
      invoice_number: number,
      status,
      issue_date: "2020-01-01",
      due_date: due,
      currency: "USD",
      total: "100.00",
    }) as never;

  it("shows an open invoice past its due date as OVERDUE", () => {
    renderAt(
      <RecentInvoices
        invoices={[
          invoice("INV-LATE", "OPEN", "2020-01-05"),
          invoice("INV-OPEN", "OPEN", "2999-01-01"),
          invoice("INV-PAID", "PAID", "2020-01-05"),
        ]}
      />,
    );

    expect(screen.getByText("OVERDUE")).toHaveClass("overdue");
    expect(screen.getByText("OPEN")).not.toHaveClass("overdue");
    expect(screen.getByText("PAID")).toHaveClass("paid");
  });
});
