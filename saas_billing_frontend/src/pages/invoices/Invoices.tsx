import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowDownToLine,
  ChevronDown,
  ChevronUp,
  FileText,
  Mail,
  Plus,
  RefreshCw,
  Search,
  Send,
  Trash2,
  X,
} from "lucide-react";

import { useOrganization } from "../../context/OrganizationContext";
import { useOrgRole } from "../../utils/roles";
import {
  createInvoice,
  downloadInvoicePdf,
  getInvoices,
  sendInvoice,
  payInvoice,
  type Invoice,
  type CreateInvoiceData,
} from "../../api/invoices";

import "./Invoices.css";

interface InvoiceFormItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: string;
}

function InvoicesPage() {
  const { activeOrganization } = useOrganization();
  const organizationId = activeOrganization?.id ?? null;

  // Was the user's FIRST organization, not the active one.
  const organization = activeOrganization;

  // MEMBER can list invoices and download PDFs only.
  const { isFinance } = useOrgRole();

  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [isLoading, setIsLoading] = useState(Boolean(organizationId));
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [expandedInvoice, setExpandedInvoice] = useState<string | null>(null);
  const [sendingInvoice, setSendingInvoice] = useState<string | null>(null);
  const [payingInvoiceId, setPayingInvoiceId] = useState<string | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const [billingEmail, setBillingEmail] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [issueDate, setIssueDate] = useState(
    new Date().toISOString().split("T")[0],
  );
  const [dueDate, setDueDate] = useState(() => {
    const date = new Date();
    date.setDate(date.getDate() + 7);
    return date.toISOString().split("T")[0];
  });
  const [tax, setTax] = useState("0.00");

  const [formItems, setFormItems] = useState<InvoiceFormItem[]>([
    {
      id: crypto.randomUUID(),
      description: "",
      quantity: 1,
      unit_price: "0.00",
    },
  ]);

  // Fetches and stores data; sets no state before the request, so it can
  // run straight from the mount effect.
  const fetchInvoices = useCallback(async () => {
    if (!organizationId) {
      return;
    }

    await getInvoices(organizationId)
      .then((data) => {
        setInvoices(data);
        setError("");
      })
      .catch((err: unknown) => {
        console.error("Failed to load invoices:", err);
        setError("Unable to load invoices. Please try again.");
      })
      .finally(() => {
        setIsLoading(false);
        setIsRefreshing(false);
      });
  }, [organizationId]);

  useEffect(() => {
    void fetchInvoices();
  }, [fetchInvoices]);

  // Refresh button and after create / send / pay.
  const loadInvoices = async (refresh = false) => {
    if (refresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }

    setError("");

    await fetchInvoices();
  };

  const filteredInvoices = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();

    if (!query) {
      return invoices;
    }

    return invoices.filter((invoice) =>
      [
        invoice.invoice_number,
        invoice.status,
        invoice.billing_email,
        invoice.currency,
      ]
        .filter(Boolean)
        .some((value) =>
          String(value).toLowerCase().includes(query),
        ),
    );
  }, [invoices, searchTerm]);

  const stats = useMemo(() => {
    const total = invoices.length;

    const paid = invoices.filter(
      (invoice) => invoice.status.toUpperCase() === "PAID",
    ).length;

    const open = invoices.filter(
      (invoice) => invoice.status.toUpperCase() === "OPEN",
    ).length;

    const draft = invoices.filter(
      (invoice) => invoice.status.toUpperCase() === "DRAFT",
    ).length;

    const totalAmount = invoices.reduce(
      (sum, invoice) => sum + Number(invoice.total || 0),
      0,
    );

    return {
      total,
      paid,
      open,
      draft,
      totalAmount,
    };
  }, [invoices]);

  const formSubtotal = useMemo(() => {
    return formItems.reduce(
      (sum, item) =>
        sum +
        Number(item.quantity || 0) *
          Number(item.unit_price || 0),
      0,
    );
  }, [formItems]);

  const formTotal = formSubtotal + Number(tax || 0);

  const formatAmount = (invoice: Invoice) => {
    return `${invoice.currency} ${Number(invoice.total || 0).toFixed(2)}`;
  };

  const formatDate = (value: string | null) => {
    if (!value) {
      return "—";
    }

    return new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(new Date(value));
  };

  const getStatusClass = (status: string) => {
    switch (status.toUpperCase()) {
      case "PAID":
        return "status-paid";

      case "OPEN":
        return "status-open";

      case "DRAFT":
        return "status-draft";

      case "VOID":
        return "status-void";

      case "UNCOLLECTIBLE":
        return "status-uncollectible";

      default:
        return "status-default";
    }
  };

  const toggleInvoice = (invoiceId: string) => {
    setExpandedInvoice((current) =>
      current === invoiceId ? null : invoiceId,
    );
  };

  const openCreateModal = () => {
    setError("");

    setBillingEmail("");
    setCurrency("USD");

    const today = new Date();

    setIssueDate(today.toISOString().split("T")[0]);

    const due = new Date();
    due.setDate(today.getDate() + 7);
    setDueDate(due.toISOString().split("T")[0]);

    setTax("0.00");

    setFormItems([
      {
        id: crypto.randomUUID(),
        description: "",
        quantity: 1,
        unit_price: "0.00",
      },
    ]);

    setIsCreateOpen(true);
  };

  const closeCreateModal = () => {
    if (isCreating) {
      return;
    }

    setIsCreateOpen(false);
  };

  const addItem = () => {
    setFormItems((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        description: "",
        quantity: 1,
        unit_price: "0.00",
      },
    ]);
  };

  const removeItem = (id: string) => {
    setFormItems((current) => {
      if (current.length === 1) {
        return current;
      }

      return current.filter((item) => item.id !== id);
    });
  };

  const updateItem = (
    id: string,
    field: keyof InvoiceFormItem,
    value: string | number,
  ) => {
    setFormItems((current) =>
      current.map((item) =>
        item.id === id
          ? {
              ...item,
              [field]: value,
            }
          : item,
      ),
    );
  };

  const handleCreateInvoice = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    if (!organizationId) {
      setError("No organization is available.");
      return;
    }

    if (!billingEmail.trim()) {
      setError("Billing email is required.");
      return;
    }

    if (!issueDate || !dueDate) {
      setError("Issue date and due date are required.");
      return;
    }

    if (dueDate < issueDate) {
      setError("Due date cannot be before the issue date.");
      return;
    }


    const invalidItem = formItems.find((item) => {
        const description = item.description.trim();
        const quantity = Number(item.quantity);
        const unitPrice = Number(item.unit_price);

        return (
            !description ||
            !Number.isFinite(quantity) ||
            quantity <= 0 ||
            !Number.isFinite(unitPrice) ||
            unitPrice < 0
        );
        });

        if (invalidItem) {
        setError(
            "Please complete all invoice items with a description, valid quantity, and valid unit price.",
        );
        return;
        }

    const validItems = formItems;

    try {
      setIsCreating(true);
      setError("");

      const data: CreateInvoiceData = {
        issue_date: issueDate,
        due_date: dueDate,
        currency: currency.trim().toUpperCase(),
        tax: Number(tax || 0).toFixed(2),
        billing_email: billingEmail.trim(),
        items: validItems.map((item) => ({
          description: item.description.trim(),
          quantity: Number(item.quantity),
          unit_price: Number(item.unit_price || 0).toFixed(2),
        })),
      };

      const createdInvoice = await createInvoice(
        organizationId,
        data,
      );

      setInvoices((current) => [
        createdInvoice,
        ...current,
      ]);

      setIsCreateOpen(false);

      setExpandedInvoice(createdInvoice.id);
    } catch (err) {
      console.error("Failed to create invoice:", err);
      setError("Unable to create invoice. Please check the form and try again.");
    } finally {
      setIsCreating(false);
    }
  };

  const handleSend = async (invoice: Invoice) => {
    if (!organizationId) {
      return;
    }

    try {
      setSendingInvoice(invoice.id);
      setError("");

      await sendInvoice(organizationId, invoice.id);

      await loadInvoices(true);
    } catch (err) {
      console.error("Failed to send invoice:", err);
      setError("Unable to send invoice. Please try again.");
    } finally {
      setSendingInvoice(null);
    }
  };


  const handlePay = async (invoice: Invoice) => {
    if (!organizationId) {
      setError("No organization is available.");
      return;
    }

    try {
      setPayingInvoiceId(invoice.id);
      setError("");

      const response = await payInvoice(
        organizationId,
        invoice.id,
      );

      window.location.href = response.checkout_url;
    } catch (err: any) {
      console.error("Failed to create payment session:", err);

      setError(
        err?.response?.data?.detail ||
          "Unable to start invoice payment.",
      );
    } finally {
      setPayingInvoiceId(null);
    }
  };

  const handleDownloadPdf = async (invoice: Invoice) => {
    if (!organizationId) {
      return;
    }

    try {
      const blob = await downloadInvoicePdf(
        organizationId,
        invoice.id,
      );

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = `${invoice.invoice_number}.pdf`;

      document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to download invoice PDF:", err);
      setError("Unable to download invoice PDF.");
    }
  };

  if (!organizationId) {
    return (
      <div className="invoices-page">
        <div className="invoices-empty">
          <FileText size={42} />
          <h2>No organization available</h2>
          <p>
            Your account needs an organization before invoices can be
            displayed.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="invoices-page">
      <div className="invoices-header">
        <div>
          <div className="invoices-eyebrow">
            <FileText size={16} />
            INVOICING
          </div>

          <h1>Invoices</h1>

          <p>
            Create, manage, send and track invoices for{" "}
            <strong>{organization?.name ?? "your organization"}</strong>
          </p>
        </div>

        {isFinance && (
          <button
            type="button"
            className="primary-button"
            onClick={openCreateModal}
          >
            <Plus size={18} />
            Create invoice
          </button>
        )}
      </div>

      {!isFinance && (
        <div className="invoice-alert invoice-alert-info">
          You have read-only access to invoices. Owners, admins and
          accountants can create, send and pay invoices.
        </div>
      )}

      {error && <div className="invoice-alert">{error}</div>}

      <div className="invoice-stats">
        <div className="invoice-stat-card">
          <span>Total invoices</span>
          <strong>{stats.total}</strong>
        </div>

        <div className="invoice-stat-card">
          <span>Paid</span>
          <strong>{stats.paid}</strong>
        </div>

        <div className="invoice-stat-card">
          <span>Open</span>
          <strong>{stats.open}</strong>
        </div>

        <div className="invoice-stat-card">
          <span>Draft</span>
          <strong>{stats.draft}</strong>
        </div>

        <div className="invoice-stat-card invoice-stat-highlight">
          <span>Total value</span>
          <strong>{stats.totalAmount.toFixed(2)}</strong>
        </div>
      </div>

      <div className="invoice-toolbar">
        <div className="invoice-search">
          <Search size={18} />

          <input
            type="text"
            placeholder="Search invoices..."
            value={searchTerm}
            onChange={(event) =>
              setSearchTerm(event.target.value)
            }
          />
        </div>

        <button
          type="button"
          className="secondary-button"
          onClick={() => void loadInvoices(true)}
          disabled={isRefreshing}
        >
          <RefreshCw
            size={17}
            className={isRefreshing ? "spin" : ""}
          />
          Refresh
        </button>
      </div>

      <div className="invoice-table-card">
        <div className="invoice-table-header">
          <div>Invoice</div>
          <div>Status</div>
          <div>Issue date</div>
          <div>Due date</div>
          <div>Amount</div>
          <div>Actions</div>
        </div>

        {isLoading ? (
          <div className="invoice-table-message">
            Loading invoices...
          </div>
        ) : filteredInvoices.length === 0 ? (
          <div className="invoice-table-message">
            <FileText size={36} />
            <h3>No invoices found</h3>
            <p>
              {searchTerm
                ? "Try a different search."
                : "There are currently no invoices for this organization."}
            </p>
          </div>
        ) : (
          filteredInvoices.map((invoice) => {
            const isExpanded =
              expandedInvoice === invoice.id;

            return (
              <div
                key={invoice.id}
                className="invoice-row-wrapper"
              >
                <div className="invoice-table-row">
                  <button
                    type="button"
                    className="invoice-number-button"
                    onClick={() =>
                      toggleInvoice(invoice.id)
                    }
                  >
                    {isExpanded ? (
                      <ChevronUp size={17} />
                    ) : (
                      <ChevronDown size={17} />
                    )}

                    <span>
                      {invoice.invoice_number}
                    </span>
                  </button>

                  <div>
                    <span
                      className={`invoice-status ${getStatusClass(
                        invoice.status,
                      )}`}
                    >
                      {invoice.status}
                    </span>
                  </div>

                  <div>
                    {formatDate(invoice.issue_date)}
                  </div>

                  <div>
                    {formatDate(invoice.due_date)}
                  </div>

                  <div className="invoice-amount">
                    {formatAmount(invoice)}
                  </div>

                  <div className="invoice-actions">
                    {isFinance &&
                      invoice.status.toUpperCase() ===
                      "DRAFT" && (
                      <button
                        type="button"
                        className="icon-action"
                        title="Send invoice"
                        disabled={
                          sendingInvoice === invoice.id
                        }
                        onClick={() =>
                          void handleSend(invoice)
                        }
                      >
                        <Send size={17} />
                      </button>
                    )}

                  {isFinance &&
                    invoice.status.toUpperCase() === "OPEN" && (
                    <button
                      type="button"
                      className="icon-action"
                      title="Pay invoice"
                      disabled={payingInvoiceId === invoice.id}
                      onClick={() => void handlePay(invoice)}
                    >
                      {payingInvoiceId === invoice.id ? "..." : "$"}
                    </button>
                  )}

                    <button
                      type="button"
                      className="icon-action"
                      title="Download PDF"
                      onClick={() =>
                        void handleDownloadPdf(invoice)
                      }
                    >
                      <ArrowDownToLine size={17} />
                    </button>

                    {invoice.billing_email && (
                      <button
                        type="button"
                        className="icon-action"
                        title={`Billing email: ${invoice.billing_email}`}
                        onClick={() =>
                          toggleInvoice(invoice.id)
                        }
                      >
                        <Mail size={17} />
                      </button>
                    )}
                  </div>
                </div>

                {isExpanded && (
                  <div className="invoice-details">
                    <div className="invoice-details-grid">
                      <div>
                        <span>Billing email</span>
                        <strong>
                          {invoice.billing_email || "—"}
                        </strong>
                      </div>

                      <div>
                        <span>Currency</span>
                        <strong>{invoice.currency}</strong>
                      </div>

                      <div>
                        <span>Subtotal</span>
                        <strong>
                          {invoice.currency}{" "}
                          {Number(
                            invoice.subtotal || 0,
                          ).toFixed(2)}
                        </strong>
                      </div>

                      <div>
                        <span>Tax</span>
                        <strong>
                          {invoice.currency}{" "}
                          {Number(
                            invoice.tax || 0,
                          ).toFixed(2)}
                        </strong>
                      </div>

                      <div>
                        <span>Total</span>
                        <strong>
                          {invoice.currency}{" "}
                          {Number(
                            invoice.total || 0,
                          ).toFixed(2)}
                        </strong>
                      </div>
                    </div>

                    {invoice.items?.length > 0 && (
                      <div className="invoice-items">
                        <h4>Invoice items</h4>

                        {invoice.items.map((item) => (
                          <div
                            className="invoice-item"
                            key={item.id}
                          >
                            <span>
                              {item.description}
                            </span>

                            <span>
                              {item.quantity} ×{" "}
                              {Number(
                                item.unit_price,
                              ).toFixed(2)}
                            </span>

                            <strong>
                              {Number(
                                item.amount,
                              ).toFixed(2)}
                            </strong>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {isCreateOpen && (
        <div
          className="invoice-modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closeCreateModal();
            }
          }}
        >
          <div className="invoice-modal">
            <div className="invoice-modal-header">
              <div>
                <span>NEW INVOICE</span>
                <h2>Create invoice</h2>
                <p>
                  Create a draft invoice for{" "}
                  <strong>{organization?.name ?? "your organization"}</strong>
                </p>
              </div>

              <button
                type="button"
                className="modal-close-button"
                onClick={closeCreateModal}
                disabled={isCreating}
                title="Close"
              >
                <X size={20} />
              </button>
            </div>

            <form
              className="invoice-create-form"
              onSubmit={handleCreateInvoice}
            >
              <div className="invoice-form-grid">
                <label>
                  <span>Billing email</span>
                  <input
                    type="email"
                    value={billingEmail}
                    onChange={(event) =>
                      setBillingEmail(event.target.value)
                    }
                    placeholder="customer@example.com"
                    required
                  />
                </label>

                <label>
                <span>Currency</span>

                <select
                    value={currency}
                    onChange={(event) => setCurrency(event.target.value)}
                    required
                >
                    <option value="USD">USD — US Dollar</option>
                    <option value="EUR">EUR — Euro</option>
                    <option value="GBP">GBP — British Pound</option>
                    <option value="PKR">PKR — Pakistani Rupee</option>
                </select>
                </label>

                <label>
                  <span>Issue date</span>
                  <input
                    type="date"
                    value={issueDate}
                    onChange={(event) =>
                      setIssueDate(event.target.value)
                    }
                    required
                  />
                </label>

                <label>
                  <span>Due date</span>
                  <input
                    type="date"
                    value={dueDate}
                    onChange={(event) =>
                      setDueDate(event.target.value)
                    }
                    required
                  />
                </label>

                <label>
                  <span>Tax</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={tax}
                    onChange={(event) =>
                      setTax(event.target.value)
                    }
                  />
                </label>
              </div>

              <div className="invoice-form-section">
                <div className="invoice-form-section-header">
                  <div>
                    <h3>Invoice items</h3>
                    <p>Add the products or services being billed.</p>
                  </div>

                  <button
                    type="button"
                    className="secondary-button"
                    onClick={addItem}
                  >
                    <Plus size={16} />
                    Add item
                  </button>
                </div>

                <div className="invoice-form-items">
                  {formItems.map((item, index) => (
                    <div
                      className="invoice-form-item"
                      key={item.id}
                    >
                      <div className="invoice-item-index">
                        {index + 1}
                      </div>

                      <label className="item-description">
                        <span>Description</span>
                        <input
                          type="text"
                          value={item.description}
                          onChange={(event) =>
                            updateItem(
                              item.id,
                              "description",
                              event.target.value,
                            )
                          }
                          placeholder="e.g. Professional subscription"
                          required
                        />
                      </label>

                      <label>
                        <span>Qty</span>
                        <input
                          type="number"
                          min="1"
                          step="1"
                          value={item.quantity}
                          onChange={(event) =>
                            updateItem(
                              item.id,
                              "quantity",
                              Number(event.target.value),
                            )
                          }
                          required
                        />
                      </label>

                      <label>
                        <span>Unit price</span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={item.unit_price}
                          onChange={(event) =>
                            updateItem(
                              item.id,
                              "unit_price",
                              event.target.value,
                            )
                          }
                          required
                        />
                      </label>

                      <div className="invoice-item-line-total">
                        <span>Amount</span>
                        <strong>
                          {currency.toUpperCase()}{" "}
                          {(
                            Number(item.quantity || 0) *
                            Number(item.unit_price || 0)
                          ).toFixed(2)}
                        </strong>
                      </div>

                      <button
                        type="button"
                        className="remove-item-button"
                        onClick={() =>
                          removeItem(item.id)
                        }
                        disabled={formItems.length === 1}
                        title="Remove item"
                      >
                        <Trash2 size={17} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="invoice-form-summary">
                <div>
                  <span>Subtotal</span>
                  <strong>
                    {currency.toUpperCase()}{" "}
                    {formSubtotal.toFixed(2)}
                  </strong>
                </div>

                <div>
                  <span>Tax</span>
                  <strong>
                    {currency.toUpperCase()}{" "}
                    {Number(tax || 0).toFixed(2)}
                  </strong>
                </div>

                <div className="invoice-form-total">
                  <span>Total</span>
                  <strong>
                    {currency.toUpperCase()}{" "}
                    {formTotal.toFixed(2)}
                  </strong>
                </div>
              </div>

              <div className="invoice-modal-footer">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={closeCreateModal}
                  disabled={isCreating}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="primary-button"
                  disabled={isCreating}
                >
                  <Plus size={18} />
                  {isCreating
                    ? "Creating..."
                    : "Create invoice"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// Remount the page when the active organization changes, so every piece
// of state (loading flags, data, errors) starts fresh for the new org and
// a slow response for the previous org can never overwrite the new one.
function Invoices() {
  const { activeOrganizationId } = useOrganization();

  return <InvoicesPage key={activeOrganizationId ?? "none"} />;
}

export default Invoices;