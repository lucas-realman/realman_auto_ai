import React, { useRef, useState } from 'react';
import {
  ProTable,
  ModalForm,
  ProFormText,
  ProFormSelect,
  ProFormTextArea,
} from '@ant-design/pro-components';
import type { ProColumns, ActionType } from '@ant-design/pro-components';
import { Button, Tag, Drawer, Descriptions, message, Space } from 'antd';
import { PlusOutlined, EyeOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  fetchCustomers,
  createCustomer,
  getCustomerDetail,
  Customer,
} from '../api/customers';

const levelOptions = [
  { label: 'A-大客户', value: 'A' },
  { label: 'B-重要', value: 'B' },
  { label: 'C-普通', value: 'C' },
  { label: 'D-潜在', value: 'D' },
];

const levelColorMap: Record<string, string> = {
  A: 'red',
  B: 'orange',
  C: 'blue',
  D: 'default',
};

const CustomersPage: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [modalOpen, setModalOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detail, setDetail] = useState<Customer | null>(null);

  const columns: ProColumns<Customer>[] = [
    { title: '公司名称', dataIndex: 'companyName', ellipsis: true },
    {
      title: '级别',
      dataIndex: 'level',
      valueType: 'select',
      fieldProps: { options: levelOptions },
      width: 100,
      render: (_, r) => (
        <Tag color={levelColorMap[r.level || ''] || 'default'}>{r.level || '-'}</Tag>
      ),
    },
    { title: '行业', dataIndex: 'industry', ellipsis: true, hideInSearch: true },
    { title: '区域', dataIndex: 'region', ellipsis: true, hideInSearch: true },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      valueType: 'dateTime',
      width: 160,
      hideInSearch: true,
    },
    {
      title: '操作',
      valueType: 'option',
      width: 120,
      render: (_, record) => (
        <Space size="small">
          <a
            onClick={async () => {
              try {
                const d = await getCustomerDetail(record.id);
                setDetail(d);
                setDrawerOpen(true);
              } catch {
                /* interceptor */
              }
            }}
          >
            <EyeOutlined /> 详情
          </a>
        </Space>
      ),
    },
  ];

  return (
    <>
      <ProTable<Customer>
        headerTitle="客户管理"
        actionRef={actionRef}
        rowKey="id"
        columns={columns}
        search={{ labelWidth: 'auto' }}
        toolBarRender={() => [
          <Button
            key="create"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setModalOpen(true)}
          >
            新建客户
          </Button>,
        ]}
        request={async (params) => {
          const { current = 1, pageSize = 20, level } = params;
          const res = await fetchCustomers(current, pageSize, level);
          return { data: res.items, total: res.total, success: true };
        }}
        pagination={{ defaultPageSize: 20, showSizeChanger: true }}
      />

      <ModalForm
        title="新建客户"
        open={modalOpen}
        onOpenChange={setModalOpen}
        modalProps={{ destroyOnClose: true }}
        onFinish={async (values) => {
          try {
            await createCustomer(values);
            message.success('创建成功');
            actionRef.current?.reload();
            return true;
          } catch {
            return false;
          }
        }}
      >
        <ProFormText
          name="companyName"
          label="公司名称"
          rules={[{ required: true, message: '请输入公司名称' }]}
        />
        <ProFormSelect name="level" label="客户级别" options={levelOptions} />
        <ProFormText name="industry" label="行业" />
        <ProFormText name="region" label="区域" />
        <ProFormText name="address" label="地址" />
        <ProFormText name="website" label="网站" />
        <ProFormTextArea name="notes" label="备注" />
      </ModalForm>

      <Drawer
        title="客户详情"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={600}
      >
        {detail && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="公司名称">{detail.companyName}</Descriptions.Item>
            <Descriptions.Item label="级别">
              <Tag color={levelColorMap[detail.level || ''] || 'default'}>
                {detail.level || '-'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="行业">{detail.industry || '-'}</Descriptions.Item>
            <Descriptions.Item label="区域">{detail.region || '-'}</Descriptions.Item>
            <Descriptions.Item label="地址">{detail.address || '-'}</Descriptions.Item>
            <Descriptions.Item label="网站">{detail.website || '-'}</Descriptions.Item>
            <Descriptions.Item label="标签">
              {detail.tags?.map((t) => (
                <Tag key={t}>{t}</Tag>
              )) || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="AI 摘要">{detail.aiSummary || '-'}</Descriptions.Item>
            <Descriptions.Item label="备注">{detail.notes || '-'}</Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {dayjs(detail.createdAt).format('YYYY-MM-DD HH:mm')}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </>
  );
};

export default CustomersPage;
