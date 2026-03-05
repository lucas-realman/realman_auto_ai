import React, { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, List, Typography, Spin } from 'antd';
import {
  UserOutlined,
  TeamOutlined,
  FunnelPlotOutlined,
  ScheduleOutlined,
} from '@ant-design/icons';
import { Funnel } from '@ant-design/charts';
import { fetchLeads } from '../api/leads';
import { fetchCustomers } from '../api/customers';
import { fetchOpportunities } from '../api/opportunities';
import { fetchActivities, Activity } from '../api/activities';
import dayjs from 'dayjs';

const STAGE_LABELS: Record<string, string> = {
  initial_contact: '初步接触',
  needs_confirmed: '需求确认',
  solution_review: '方案评审',
  negotiation: '商务谈判',
  won: '赢单',
  lost: '输单',
};

const STAGE_ORDER = [
  'initial_contact',
  'needs_confirmed',
  'solution_review',
  'negotiation',
  'won',
  'lost',
];

const DashboardHome: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [totalLeads, setTotalLeads] = useState(0);
  const [totalCustomers, setTotalCustomers] = useState(0);
  const [totalOpportunities, setTotalOpportunities] = useState(0);
  const [totalActivities, setTotalActivities] = useState(0);
  const [funnelData, setFunnelData] = useState<
    { stage: string; count: number }[]
  >([]);
  const [recentActivities, setRecentActivities] = useState<Activity[]>([]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [leadsRes, customersRes, oppsRes, activitiesRes] =
          await Promise.all([
            fetchLeads(1, 1),
            fetchCustomers(1, 1),
            fetchOpportunities(1, 1),
            fetchActivities(1, 5),
          ]);

        setTotalLeads(leadsRes.total);
        setTotalCustomers(customersRes.total);
        setTotalOpportunities(oppsRes.total);
        setTotalActivities(activitiesRes.total);
        setRecentActivities(activitiesRes.items);

        // Fetch all opportunities to compute funnel
        const allOpps = await fetchOpportunities(1, 1000);
        const stageCounts: Record<string, number> = {};
        STAGE_ORDER.forEach((s) => (stageCounts[s] = 0));
        allOpps.items.forEach((o) => {
          if (stageCounts[o.stage] !== undefined) {
            stageCounts[o.stage]++;
          } else {
            stageCounts[o.stage] = 1;
          }
        });
        const data = STAGE_ORDER.map((s) => ({
          stage: STAGE_LABELS[s] || s,
          count: stageCounts[s] || 0,
        }));
        setFunnelData(data);
      } catch {
        // errors handled by interceptor
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const activityTypeIcon: Record<string, string> = {
    call: '📞',
    visit: '🏢',
    email: '📧',
    meeting: '🤝',
    other: '📝',
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="线索总数"
              value={totalLeads}
              prefix={<UserOutlined />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="客户总数"
              value={totalCustomers}
              prefix={<TeamOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="商机总数"
              value={totalOpportunities}
              prefix={<FunnelPlotOutlined />}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="活动总数"
              value={totalActivities}
              prefix={<ScheduleOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="商机漏斗">
            {funnelData.length > 0 ? (
              <Funnel
                data={funnelData}
                xField="stage"
                yField="count"
                legend={false}
                label={{
                  text: (d: { stage: string; count: number }) =>
                    `${d.stage} ${d.count}`,
                }}
                style={{ height: 350 }}
              />
            ) : (
              <Typography.Text type="secondary">暂无数据</Typography.Text>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="最近活动">
            <List
              dataSource={recentActivities}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={
                      <span style={{ fontSize: 20 }}>
                        {activityTypeIcon[item.type] || '