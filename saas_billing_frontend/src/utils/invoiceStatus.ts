// An open invoice whose due date has passed is shown as OVERDUE.
// Dates are compared as YYYY-MM-DD strings in the viewer's local day.

interface DueInvoice {
  status: string;
  due_date?: string | null;
}

export function isInvoiceOverdue(invoice: DueInvoice, now = new Date()) {
  if (invoice.status.toUpperCase() !== "OPEN" || !invoice.due_date) {
    return false;
  }

  const today = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");

  return invoice.due_date < today;
}

/** Status label to display: OVERDUE replaces OPEN once the due date passed. */
export function invoiceStatusLabel(invoice: DueInvoice, now = new Date()) {
  return isInvoiceOverdue(invoice, now) ? "OVERDUE" : invoice.status;
}
