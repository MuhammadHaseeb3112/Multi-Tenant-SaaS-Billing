import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2 } from "lucide-react";

import {
  getPublicInvoice,
  payPublicInvoice,
  type PublicInvoice,
} from "../../api/invoices";

import "../auth/auth.css";
import "./PayInvoice.css";

type LoadState =
  | { kind: "loading" }
  | { kind: "invalid"; message: string }
  | { kind: "ready"; invoice: PublicInvoice };

const PAID_CHECKS = 6;
const PAID_CHECK_MS = 2000;

function money(value: string, currency: string) {
  const amount = Number(value);

  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function errorDetail(err: unknown, fallback: string) {
  const detail = (err as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

/**
 * Public page the invoice email links to. The customer sees the invoice
 * and pays it with Stripe Checkout; no account needed.
 */
function PayInvoice() {
  const { token = "" } = useParams();
  const [searchParams] = useSearchParams();
  const returnedFromStripe = searchParams.get("paid") === "1";

  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let checks = 0;
    let timer: number | undefined;

    const load = () => {
      getPublicInvoice(token)
        .then((invoice) => {
          if (cancelled) return;
          setState({ kind: "ready", invoice });

          // Back from Stripe: the webhook marks it paid a moment later.
          checks += 1;
          if (
            returnedFromStripe &&
            invoice.status !== "PAID" &&
            checks < PAID_CHECKS
          ) {
            timer = window.setTimeout(load, PAID_CHECK_MS);
          }
        })
        .catch((err) => {
          if (!cancelled) {
            setState({
              kind: "invalid",
              message: errorDetail(
                err,
                "This payment link is not valid.",
              ),
            });
          }
        });
    };

    load();

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [token, returnedFromStripe]);

  const handlePay = () => {
    setError("");
    setPaying(true);

    payPublicInvoice(token)
      .then(({ checkout_url }) => {
        window.location.assign(checkout_url);
      })
      .catch((err) => {
        setError(errorDetail(err, "Could not start the payment."));
        setPaying(false);
      });
  };

  const renderBody = () => {
    if (state.kind === "loading") {
      return (
        <div className="pay-center">
          <Loader2 className="auth-spinner" size={22} />
          <p>Loading invoice...</p>
        </div>
      );
    }

    if (state.kind === "invalid") {
      return (
        <div className="auth-error" role="alert">
          {state.message} If you need help, please contact the business
          that sent you the invoice.
        </div>
      );
    }

    const { invoice } = state;
    const isPaid = invoice.status === "PAID";
    const waitingForPayment = returnedFromStripe && !isPaid;

    return (
      <>
        <div className="auth-header">
          <h1>Invoice {invoice.invoice_number}</h1>
          <p>
            From <strong>{invoice.organization_name}</strong> to{" "}
            {invoice.billing_email}
          </p>
        </div>

        <div className="pay-summary">
          <div>
            <span>Amount due</span>
            <strong className="pay-total">
              {money(invoice.total, invoice.currency)}
            </strong>
          </div>
          <div>
            <span>Issued</span>
            <strong>{formatDate(invoice.issue_date)}</strong>
          </div>
          <div>
            <span>Due</span>
            <strong>{formatDate(invoice.due_date)}</strong>
          </div>
        </div>

        <table className="pay-items">
          <thead>
            <tr>
              <th>Item</th>
              <th>Qty</th>
              <th>Price</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {invoice.items.map((item, index) => (
              <tr key={index}>
                <td>{item.description}</td>
                <td>{Number(item.quantity)}</td>
                <td>{money(item.unit_price, invoice.currency)}</td>
                <td>{money(item.amount, invoice.currency)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={3}>Subtotal</td>
              <td>{money(invoice.subtotal, invoice.currency)}</td>
            </tr>
            <tr>
              <td colSpan={3}>Tax</td>
              <td>{money(invoice.tax, invoice.currency)}</td>
            </tr>
            <tr className="pay-items-total">
              <td colSpan={3}>Total</td>
              <td>{money(invoice.total, invoice.currency)}</td>
            </tr>
          </tfoot>
        </table>

        {error && (
          <div className="auth-error" role="alert">
            {error}
          </div>
        )}

        {isPaid ? (
          <div className="pay-paid" role="status">
            <CheckCircle2 size={20} />
            {returnedFromStripe
              ? "Payment received. Thank you!"
              : "This invoice has been paid."}
          </div>
        ) : waitingForPayment ? (
          <div className="pay-center" role="status">
            <Loader2 className="auth-spinner" size={20} />
            <p>Confirming your payment...</p>
          </div>
        ) : invoice.payable ? (
          <button
            type="button"
            className="auth-submit"
            onClick={handlePay}
            disabled={paying}
          >
            {paying
              ? "Opening secure checkout..."
              : `Pay ${money(invoice.total, invoice.currency)}`}
          </button>
        ) : (
          <div className="auth-error" role="alert">
            This invoice can't be paid online right now. Please contact{" "}
            {invoice.organization_name}.
          </div>
        )}

        <p className="pay-note">
          Payments are processed securely by Stripe.
        </p>
      </>
    );
  };

  return (
    <div className="auth-page">
      <div className="auth-card pay-card">
        <div className="auth-brand">
          <div className="auth-brand-mark">S</div>
          <span>SaaS Billing</span>
        </div>

        {renderBody()}
      </div>
    </div>
  );
}

export default PayInvoice;
