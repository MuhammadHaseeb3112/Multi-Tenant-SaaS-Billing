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