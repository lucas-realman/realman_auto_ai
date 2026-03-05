import client from './client';

export interface Opportunity {
  id: number;
  name: string;
  customerId?: number;
  amount?: number;
  stage: string;
  expectedCloseDate?: string;
  productType?: string;
  notes?: string;
  ownerId?: number;
  winRate?: number;
  lostReason?: string;
  createdAt: string;
  updatedAt: string;
}

export interface OpportunityListResponse {
  items: Opportunity[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface OpportunityCreateData {
  name: string;
  customerId?: number;
  amount?: number;
  stage?: string;
  expectedCloseDate?: string;
  productType?: string;
  notes?: string;
  ownerId?: number;
}

export interface OpportunityUpdateData {
  name?: string;
  customerId?: number;
  amount?: number;
  stage?: string;
  expectedCloseDate?: string;
  productType?: string;
  notes?: string;
  ownerId?: number;
  winRate?: number;
  lostReason?: string;
}

export async function fetchOpportunities(
  page: number = 1,
  size: number = 20,
  stage?: string,
  customerId?: number
): Promise<OpportunityListResponse> {
  const params: Record<string, unknown> = { page, size };
  if (stage) params.stage = stage;
  if (customerId) params.customer_id = customerId;
  const res = await client.get('/opportunities', { params });
  return res.data;
}

export async function createOpportunity(
  data: OpportunityCreateData
): Promise<Opportunity> {
  const res = await client.post('/opportunities', data);
  return res.data;
}

export async function updateOpportunity(
  id: number,
  data: OpportunityUpdateData
): Promise<Opportunity> {
  const res = await client.put(`/opportunities/${id}`, data);
  return res.data;
}
