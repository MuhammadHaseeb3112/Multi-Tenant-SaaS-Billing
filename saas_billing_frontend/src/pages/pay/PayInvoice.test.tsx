import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getPublicInvoice: vi.fn(),
  payPublicInvoice: vi.fn(),
}));

vi.mock("../../api/invoices", () => api);

import PayInvoice from "./PayInvoice";

const invoice = {
  invoice_number: "INV-000001",
  organization_name: "hassanenterprise",
  status: "OPEN",
  payable: true,
  currency: "USD",
  issue_date: "2026-11-07",
  due_date: "2026-11-14",
  subtotal: "70.00",
  tax: "9.98",
  total: "79.98",
  billing_email: "client@example.com",
  items: [
    { description: "Design", quantity: "2.00", unit_price: "35.00", amount: "70.00" },
  ],
};

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/pay/:token" element={<PayInvoice />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Public invoice payment page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the invoice and a pay button", async () => {
    api.getPublicInvoice.mockResolvedValue(invoice);

    renderAt("/pay/tok123");

    expect(await screen.findByText("Invoice INV-000001")).toBeInTheDocument();
    expect(screen.getByText("hassanenterprise")).toBeInTheDocument();
    expect(screen.getByText("Design")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Pay \$79\.98/ }),
    ).toBeInTheDocument();
    expect(api.getPublicInvoice).toHaveBeenCalledWith("tok123");
  });

  it("sends the customer to Stripe checkout", async () => {
    api.getPublicInvoice.mockResolvedValue(invoice);
    api.payPublicInvoice.mockResolvedValue({
      checkout_url: "https://checkout.stripe.com/pay/cs_1",
    });
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });

    renderAt("/pay/tok123");
    fireEvent.click(await screen.findByRole("button", { name: /Pay/ }));

    await waitFor(() =>
      expect(assign).toHaveBeenCalledWith("https://checkout.stripe.com/pay/cs_1"),
    );
    vi.unstubAllGlobals();
  });

  it("shows paid invoices as paid, without a pay button", async () => {
    api.getPublicInvoice.mockResolvedValue({
      ...invoice,
      status: "PAID",
      payable: false,
    });

    renderAt("/pay/tok123");

    expect(
      await screen.findByText("This invoice has been paid."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Pay/ })).not.toBeInTheDocument();
  });

  it("thanks the customer after returning from Stripe", async () => {
    api.getPublicInvoice.mockResolvedValue({
      ...invoice,
      status: "PAID",
      payable: false,
    });

    renderAt("/pay/tok123?paid=1");

    expect(
      await screen.findByText("Payment received. Thank you!"),
    ).toBeInTheDocument();
  });

  it("explains an invalid link", async () => {
    api.getPublicInvoice.mockRejectedValue(new Error("404"));

    renderAt("/pay/bad");

    expect(
      await screen.findByText(/This payment link is not valid/),
    ).toBeInTheDocument();
  });

  it("shows the server reason when payment cannot start", async () => {
    api.getPublicInvoice.mockResolvedValue(invoice);
    api.payPublicInvoice.mockRejectedValue({
      response: { data: { detail: "This invoice has already been paid." } },
    });

    renderAt("/pay/tok123");
    fireEvent.click(await screen.findByRole("button", { name: /Pay/ }));

    expect(
      await screen.findByText("This invoice has already been paid."),
    ).toBeInTheDocument();
  });
});
