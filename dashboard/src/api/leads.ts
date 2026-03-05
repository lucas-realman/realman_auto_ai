import client from './client';

export interface Lead {
  id: number;
  companyName: string;
  contactName: string;
  phone?: string;
  email?: string;
  source?: string;
  industry?: string;
  notes?: string;
  tags?: string[];
  status: string;
  ownerId?: number;
  aiScore?: number;
  createdAt: string;
  updatedAt: string;
}

export interface LeadListResponse {
  items: Lead[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface LeadCreateData {
  companyName: string;
  contactName: string;
  phone?: string;
  email?: string;
  source?: string;
  industry?: string;
  notes?: string;
  tags?: string[];
  status?: string;
  ownerId?: number;
}

export interface LeadUpdateData {
  companyName?: string;
  contactName?: string;
  phone?: string;
  email?: string;
  source?: string;
  industry?: string;
  notes?: string;
  tags?: string[];
  status?: string;
  ownerId?: number;
}

export async function fetchLeads(
  page: number = 1,
  size: number = 20,
  status?: string
): Promise<LeadListResponse> {
  const params: Record<string, unknown> = { page, size };
  if (status) params.status = status;
  const res = await client.get('/leads', { params });
  return res.data;
}

export async function createLead(data: LeadCreateData): Promise<Lead> {
  const res = await client.post('/leads', data);
  return res.data;
}

export async function updateLead(
  id: number,
  data: LeadUpdateData
): Promise<Lead> {
  const res = await client.put(`/leads/${id}`, data);
  return res.data;
}

export async function convertLead(id: number): Promise<unknown> {
  const res = await client.post(`/leads/${id}/convert`);
  return res.data;
}
