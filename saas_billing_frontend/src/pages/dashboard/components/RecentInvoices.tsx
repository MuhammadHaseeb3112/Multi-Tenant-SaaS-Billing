import { useNavigate } from "react-router-dom";

import type { Invoice } from "../../../api/invoices";
import { invoiceStatusLabel } from "../../../utils/invoiceStatus";
import { IconArrowRight, IconInvoice } from "../icons";

interface RecentInvoicesProps {
  invoices: Invoice[];
  limit?: number;
}

const emptyStyle = { padding: "20px 0", color: "#64748b", fontSize: "11px" };

function InvoiceStatus({ invoice }: { invoice: Invoice }) {
  const label = invoiceStatusLabel(invoice);

  const className =
    label.toLowerCase() === "paid"
      ? "paid"
      : label === "OVERDUE"
        ? "invoice-status overdue"
        : "invoice-status";

  return <div className={className}>{label}</div>;
}

export default function RecentInvoices({
  invoices,
  limit = 3,
}: RecentInvoicesProps) {
  const navigate = useNavigate();

  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">Recent invoices</div>
          <div className="panel-subtitle">Your latest billing activity</div>
        </div>

        <button
          className="view-all"
          type="button"
          onClick={() => navigate("/invoices")}
        >
          View all
          <IconArrowRight size={13} />
        </button>
      </div>

      <div className="invoice-list">
        {invoices.slice(0, limit).map((invoice) => (
          <div className="invoice-row" key={invoice.id}>
            <div className="invoice-left">
              <div className="invoice-icon">
                <IconInvoice size={16} />
              </div>

              <div>
                <div className="invoice-number">{invoice.invoice_number}</div>
                <div className="invoice-date">
                  {new Date(invoice.issue_date).toLocaleDateString("en-US", {
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                  })}
                </div>
              </div>
            </div>

            <div className="invoice-right">
              <div className="invoice-amount">
                {invoice.currency} {Number(invoice.total).toFixed(2)}
              </div>
              <InvoiceStatus invoice={invoice} />
            </div>
          </div>
        ))}

        {invoices.length === 0 && <div style={emptyStyle}>No invoices yet.</div>}
      </div>
    </article>
  );
}
