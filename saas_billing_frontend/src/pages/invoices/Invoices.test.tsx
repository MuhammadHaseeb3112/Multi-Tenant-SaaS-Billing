import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithOrg } from "../../test/utils";

const api = vi.hoisted(() => ({
  getInvoices: vi.fn(),
  sendInvoice: vi.fn(),
  createInvoice: vi.fn(),
  updateInvoice: vi.fn(),
  deleteInvoice: vi.fn(),
}));

vi.mock("../../api/invoices", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/invoices")>()),
  getInvoices: api.getInvoices,
  sendInvoice: api.sendInvoice,
  createInvoice: api.createInvoice,
  updateInvoice: api.updateInvoice,
  deleteInvoice: api.deleteInvoice,
}));

import Invoices from "./Invoices";

const invoice = (id: string, status: string) => ({
  id,
  invoice_number: `INV-${id}`,
  status,
  issue_date: "2026-11-01",
  due_date: "2026-11-15",
  currency: "USD",
  subtotal: "100.00",
  tax: "0.00",
  total: "100.00",
  billing_email: "",
  items: [],
  sent_count: status === "OPEN" ? 1 : 0,
  last_sent_at: status === "OPEN" ? "2026-11-07T10:00:00Z" : null,
  stripe_invoice_id: null as string | null,
});

describe("Invoices page roles", () => {
  beforeEach(() => {
    api.getInvoices.mockResolvedValue([
      invoice("1", "DRAFT"),
      invoice("2", "OPEN"),
    ]);
  });

  it("accountants can create, send and pay", async () => {
    renderWithOrg(<Invoices />, { role: "ACCOUNTANT" });

    expect(await screen.findByText("INV-1")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Create invoice/ }),
    ).toBeInTheDocument();
    expect(screen.getByTitle("Send invoice")).toBeInTheDocument();
    expect(screen.getByTitle("Pay invoice")).toBeInTheDocument();
  });

  it("members get a read-only list with PDF download", async () => {
    renderWithOrg(<Invoices />, { role: "MEMBER" });

    expect(await screen.findByText("INV-1")).toBeInTheDocument();
    expect(screen.getByText(/read-only access to invoices/)).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /Create invoice/ }),
    ).not.toBeInTheDocument();
    expect(screen.queryByTitle("Send invoice")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Pay invoice")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Send invoice again" }),
    ).not.toBeInTheDocument();
    expect(screen.getAllByTitle("Download PDF")).toHaveLength(2);
  });
});

describe("Invoice sending", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getInvoices.mockResolvedValue([
      { ...invoice("2", "OPEN"), billing_email: "client@example.com" },
    ]);
  });

  it("open invoices can be sent again after confirming", async () => {
    api.sendInvoice.mockResolvedValue({});
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderWithOrg(<Invoices />, { role: "OWNER" });

    fireEvent.click(
      await screen.findByRole("button", { name: "Send invoice again" }),
    );

    expect(window.confirm).toHaveBeenCalledWith(
      expect.stringMatching(/earlier emails will stop working/),
    );
    await waitFor(() =>
      expect(api.sendInvoice).toHaveBeenCalledWith("org-acme", "2"),
    );
    expect(
      await screen.findByText(/sent again to client@example.com/),
    ).toBeInTheDocument();
  });

  it("does nothing when the resend is cancelled", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);

    renderWithOrg(<Invoices />, { role: "OWNER" });

    fireEvent.click(
      await screen.findByRole("button", { name: "Send invoice again" }),
    );

    expect(api.sendInvoice).not.toHaveBeenCalled();
  });

  it("the create form emails the invoice by default", async () => {
    renderWithOrg(<Invoices />, { role: "OWNER" });

    fireEvent.click(
      await screen.findByRole("button", { name: /Create invoice/ }),
    );

    const checkbox = screen.getByRole("checkbox", {
      name: /Email this invoice to the customer now/,
    });
    expect(checkbox).toBeChecked();
    expect(
      screen.getByRole("button", { name: /Create & send/ }),
    ).toBeInTheDocument();

    fireEvent.click(checkbox);
    expect(
      screen.getByRole("button", { name: /Save as draft/ }),
    ).toBeInTheDocument();
  });
});

describe("Invoice tabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getInvoices.mockResolvedValue([
      { ...invoice("1", "OPEN"), invoice_number: "INV-000001" },
      {
        ...invoice("2", "PAID"),
        invoice_number: "LLKBXYFO-0001",
        stripe_invoice_id: "in_test_1",
      },
    ]);
  });

  it("keeps customer and platform invoices apart", async () => {
    renderWithOrg(<Invoices />, { role: "OWNER" });

    // Customer tab: only the customer's own invoice.
    expect(await screen.findByText("INV-000001")).toBeInTheDocument();
    expect(screen.queryByText("LLKBXYFO-0001")).not.toBeInTheDocument();

    // Platform tab: only the subscription invoice from the platform.
    fireEvent.click(
      screen.getByRole("tab", { name: /Platform billing/ }),
    );
    expect(await screen.findByText("LLKBXYFO-0001")).toBeInTheDocument();
    expect(screen.queryByText("INV-000001")).not.toBeInTheDocument();
    expect(
      screen.getByText(/Your customers never see these/),
    ).toBeInTheDocument();
  });
});

describe("Manual settlement and overdue", () => {
  const open = {
    ...invoice("7", "OPEN"),
    invoice_number: "INV-000007",
    currency: "USD",
    total: "70.00",
    due_date: "2020-01-01",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    api.getInvoices.mockResolvedValue([open]);
    api.updateInvoice.mockResolvedValue({});
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  const expand = async () => {
    fireEvent.click(await screen.findByText("INV-000007"));
  };

  it("flags open invoices past their due date as overdue", async () => {
    renderWithOrg(<Invoices />, { role: "OWNER" });

    expect(await screen.findByText("OVERDUE")).toBeInTheDocument();
  });

  it("marks an invoice as paid after confirming", async () => {
    renderWithOrg(<Invoices />, { role: "OWNER" });
    await expand();

    fireEvent.click(screen.getByRole("button", { name: "Mark as paid" }));

    expect(window.confirm).toHaveBeenCalledWith(
      expect.stringMatching(/outside Stripe/),
    );
    await waitFor(() =>
      expect(api.updateInvoice).toHaveBeenCalledWith("org-acme", "7", {
        status: "PAID",
      }),
    );
    expect(
      await screen.findByText("Invoice INV-000007 marked as paid."),
    ).toBeInTheDocument();
  });

  it("voids an invoice after confirming", async () => {
    renderWithOrg(<Invoices />, { role: "ACCOUNTANT" });
    await expand();

    fireEvent.click(screen.getByRole("button", { name: "Void invoice" }));

    await waitFor(() =>
      expect(api.updateInvoice).toHaveBeenCalledWith("org-acme", "7", {
        status: "VOID",
      }),
    );
  });

  it("does nothing when the confirmation is cancelled", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);

    renderWithOrg(<Invoices />, { role: "OWNER" });
    await expand();
    fireEvent.click(screen.getByRole("button", { name: "Void invoice" }));

    expect(api.updateInvoice).not.toHaveBeenCalled();
  });

  it("members cannot settle invoices by hand", async () => {
    renderWithOrg(<Invoices />, { role: "MEMBER" });
    await expand();

    expect(
      screen.queryByRole("button", { name: "Mark as paid" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Void invoice" }),
    ).not.toBeInTheDocument();
  });
});

describe("Zero invoices", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getInvoices.mockResolvedValue([]);
  });

  it("does not create an invoice whose items add up to zero", async () => {
    const { container } = renderWithOrg(<Invoices />, { role: "OWNER" });

    fireEvent.click(
      await screen.findByRole("button", { name: /Create invoice/ }),
    );

    const form = container.querySelector(".invoice-create-form")!;
    fireEvent.change(form.querySelector('input[type="email"]')!, {
      target: { value: "client@example.com" },
    });
    fireEvent.change(form.querySelector('input[type="text"]')!, {
      target: { value: "Free thing" },
    });
    // Unit price stays 0; tax alone must not make it billable.
    const numbers = form.querySelectorAll('input[type="number"]');
    fireEvent.change(numbers[0], { target: { value: "40" } });
    fireEvent.submit(form);

    // Shown inside the form as well as on the page behind it.
    const messages = await screen.findAllByText(
      /must add up to an amount greater than zero/,
    );
    expect(form).toContainElement(messages[messages.length - 1]);
    expect(api.createInvoice).not.toHaveBeenCalled();

    // Editing the form clears the message about the last attempt.
    fireEvent.change(numbers[2], { target: { value: "20" } });
    expect(
      screen.queryByText(/must add up to an amount greater than zero/),
    ).not.toBeInTheDocument();
  });
});

describe("Deleting a draft", () => {
  const draft = { ...invoice("8", "DRAFT"), invoice_number: "INV-000008" };

  beforeEach(() => {
    vi.clearAllMocks();
    api.getInvoices.mockResolvedValue([
      draft,
      { ...invoice("9", "OPEN"), invoice_number: "INV-000009" },
    ]);
    api.deleteInvoice.mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("deletes a draft after confirming", async () => {
    renderWithOrg(<Invoices />, { role: "OWNER" });
    fireEvent.click(await screen.findByText("INV-000008"));

    fireEvent.click(screen.getByRole("button", { name: "Delete draft" }));

    expect(window.confirm).toHaveBeenCalledWith(
      expect.stringMatching(/never sent to the customer/),
    );
    await waitFor(() =>
      expect(api.deleteInvoice).toHaveBeenCalledWith("org-acme", "8"),
    );
    expect(
      await screen.findByText("Draft invoice INV-000008 was deleted."),
    ).toBeInTheDocument();
  });

  it("offers delete only on drafts, and never to members", async () => {
    const { unmount } = renderWithOrg(<Invoices />, { role: "OWNER" });
    fireEvent.click(await screen.findByText("INV-000009"));
    expect(
      screen.queryByRole("button", { name: "Delete draft" }),
    ).not.toBeInTheDocument();
    unmount();

    renderWithOrg(<Invoices />, { role: "MEMBER" });
    fireEvent.click(await screen.findByText("INV-000008"));
    expect(
      screen.queryByRole("button", { name: "Delete draft" }),
    ).not.toBeInTheDocument();
  });

  it("keeps the draft when the confirmation is cancelled", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);

    renderWithOrg(<Invoices />, { role: "OWNER" });
    fireEvent.click(await screen.findByText("INV-000008"));
    fireEvent.click(screen.getByRole("button", { name: "Delete draft" }));

    expect(api.deleteInvoice).not.toHaveBeenCalled();
  });
});
