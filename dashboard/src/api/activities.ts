import client from './client';

export interface Activity {
  id: number;
  type: string;
  subject: string;
  content?: string;
  customerId?: number;
  opportunityId?: number;
  leadId?: number;
  scheduledAt?: string;
  userId?: number;
  aiSummary?: string;
  createdAt: string;
}

export interface ActivityListResponse {
  items: Activity[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface ActivityCreateData {
  type: string;
  subject: string;
  content?: string;
  customerId?: number;
  opportunityId?: number;
  leadId?: number;
  scheduledAt?: string;
  userId?: number;
}

export async function fetchActivities(
  page: number = 1,
  size: number = 20
): Promise<ActivityListResponse> {
  const res = await client.get('/activities', { params: { page, size } });
  return res.data;
}

export async function createActivity(
  data: ActivityCreateData
): Promise<Activity> {
  const res = await client.post('/activities', data);
  return res.data;
}
