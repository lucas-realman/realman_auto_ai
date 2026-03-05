import client from './client';

export interface Customer {
  id: number;
  companyName: string;
  industry?: string;
  region?: string;
  level?: string;
  address?: string;
  website?: string;
  notes?: string;
  tags?: string[];
  ownerId?: number;
  leadId?: number;
  aiSummary?: string;
  createdAt: string;
  updatedAt: string;
}

export interface CustomerListResponse {
  items: Customer[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface CustomerCreateData {
  companyName: string;
  industry?: string;
  region?: string;
  level?: string;
  address?: string;
  website?: string;
  notes?: string;
  tags?: string[];
  ownerId?: number;
}

export async function fetchCustomers(
  page: number = 1,
  size: number = 20,
  level?: string
): Promise<CustomerListResponse> {
  const params: Record<string, unknown> = { page, size };
  if (level) params.level = level;
  const res = await client.get('/customers', { params });
  return res.data;
}

export async function createCustomer(
  data: CustomerCreateData
): Promise<Customer> {
  const res = await client.post('/customers', data);
  return res.data;
}

export async function getCustomerDetail(id: number): Promise<Customer> {
  const res = await client.get(`/customers/${id}`);
  return res.data;
}
