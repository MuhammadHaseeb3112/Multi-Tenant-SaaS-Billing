import apiClient from "./client";

export interface InvoiceItem {
  id: string;
  description: string;
  quantity: string | number;
  unit_price: string;
  amount: string;
}

export interface Invoice {
  id: string;
  organization: string;
  invoice_number: string;
  status: string;
  issue_date: string;
  due_date: string;
  currency: string;
  subtotal: string;
  tax: string;
  total: string;
  billing_email: string;
  stripe_invoice_id: string | null;
  items: InvoiceItem[];
  sent_count: number;
  last_sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateInvoiceItem {
  description: string;
  quantity: number;
  unit_price: string;
}

export interface CreateInvoiceData {
  issue_date: string;
  due_date: string;
  currency: string;
  tax: string;
  billing_email: string;
  items: CreateInvoiceItem[];
  /** Email the invoice to the customer right after creating it. */
  send_now?: boolean;
}

export interface InvoicePaymentResponse {
  checkout_url: string;
  session_id: string;
}

export const getInvoices = async (
  organizationId: string,
): Promise<Invoice[]> => {
  const response = await apiClient.get<Invoice[]>(
    `/invoices/organizations/${organizationId}/`,
  );

  return response.data;
};

export const getInvoice = async (
  organizationId: string,
  invoiceId: string,
): Promise<Invoice> => {
  const response = await apiClient.get<Invoice>(
    `/invoices/organizations/${organizationId}/${invoiceId}/`,
  );

  return response.data;
};

export const createInvoice = async (
  organizationId: string,
  data: CreateInvoiceData,
): Promise<Invoice> => {
  const response = await apiClient.post<Invoice>(
    `/invoices/organizations/${organizationId}/`,
    data,
  );

  return response.data;
};

export const updateInvoice = async (
  organizationId: string,
  invoiceId: string,
  data: Partial<Invoice>,
): Promise<Invoice> => {
  const response = await apiClient.patch<Invoice>(
    `/invoices/organizations/${organizationId}/${invoiceId}/`,
    data,
  );

  return response.data;
};

/** Only DRAFT invoices can be deleted; sent ones are voided. */
export const deleteInvoice = async (
  organizationId: string,
  invoiceId: string,
): Promise<void> => {
  await apiClient.delete(
    `/invoices/organizations/${organizationId}/${invoiceId}/`,
  );
};

export const downloadInvoicePdf = async (
  organizationId: string,
  invoiceId: string,
): Promise<Blob> => {
  const response = await apiClient.get<Blob>(
    `/invoices/organizations/${organizationId}/${invoiceId}/pdf/`,
    {
      responseType: "blob",
    },
  );

  return response.data;
};

export const sendInvoice = async (
  organizationId: string,
  invoiceId: string,
) => {
  const response = await apiClient.post(
    `/invoices/organizations/${organizationId}/${invoiceId}/send/`,
  );

  return response.data;
};

export const payInvoice = async (
  organizationId: string,
  invoiceId: string,
): Promise<InvoicePaymentResponse> => {
  const response = await apiClient.post<InvoicePaymentResponse>(
    `/invoices/organizations/${organizationId}/${invoiceId}/pay/`,
  );

  return response.data;
};

/* ---------- Public payment link (customer, no login) ---------- */

export interface PublicInvoice {
  invoice_number: string;
  organization_name: string;
  status: string;
  payable: boolean;
  currency: string;
  issue_date: string;
  due_date: string | null;
  subtotal: string;
  tax: string;
  total: string;
  billing_email: string;
  items: Omit<InvoiceItem, "id">[];
}

export const getPublicInvoice = async (
  token: string,
): Promise<PublicInvoice> => {
  const response = await apiClient.get<PublicInvoice>(
    `/invoices/public/${encodeURIComponent(token)}/`,
  );

  return response.data;
};

export const payPublicInvoice = async (
  token: string,
): Promise<{ checkout_url: string }> => {
  const response = await apiClient.post<{ checkout_url: string }>(
    `/invoices/public/${encodeURIComponent(token)}/pay/`,
  );

  return response.data;
};
