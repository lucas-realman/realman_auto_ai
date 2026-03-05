import React, { useRef, useState } from 'react';
import {
  ProTable,
  ModalForm,
  ProFormText,
  ProFormSelect,
  ProFormTextArea,
} from '@ant-design/pro-components';
import type { ProColumns, ActionType } from '@ant-design/pro-components';
import { Button, Tag, Popconfirm, message, Space } from 'antd';
import { PlusOutlined, SwapOutlined } from '@ant-design/icons';
import { fetchLeads, createLead, updateLead, convertLead, Lead } from '../api/leads';

const statusOptions = [
  { label: '新线索', value: 'new' },
  { label: '跟进中', value: 'following' },
  { label: '已转化', value: 'converted' },
  { label: '已关闭', value: 'closed' },
];

const statusColorMap: Record<string, string> = {
  new: 'blue',
  following: 'orange',
  converted: 'green',
  closed: 'default',
};

const LeadsPage: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingLead, setEditingLead] = useState<Lead | null>(null);

  const columns: ProColumns<Lead>[] = [
    { title: '公司名称', dataIndex: 'companyName', ellipsis: true },
    { title: '联系人', dataIndex: 'contactName', width: 100 },
    { title: '电话', dataIndex: 'phone', width: 130, hideInSearch: true },
    { title: '邮箱', dataIndex: 'email', width: 180, hideInSearch: true },
    { title: '来源', dataIndex: 'source', width: 100, hideInSearch: true },
    { title: '行业', dataIndex: 'industry', width: 100, hideInSearch: true },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      valueType: 'select',
      fieldProps: { options: statusOptions },
      render: (_, r) => (
        <Tag color={statusColorMap[r.status] || 'default'}>
          {statusOptions.find((o) => o.value === r.status)?.label || r.status}
        </Tag>
      ),
    },
    {
      title: 'AI 评分',
      dataIndex: 'aiScore',
      width: 80,
      hideInSearch: true,
      sorter: true,
      render: (_, r) =>
        r.aiScore != null ? (
          <Tag color={r.aiScore >= 70 ? 'green' : r.aiScore >= 40 ? 'orange' : 'red'}>
            {r.aiScore}
          </Tag>
        ) : (
          '-'
        ),
    },
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
      width: 160,
      render: (_, record) => (
        <Space size="small">
          <a
            onClick={() => {
              setEditingLead(record);
              setModalOpen(true);
            }}
          >
            编辑
          </a>
          {record.status !== 'converted' && (
            <Popconfirm
              title="确认将此线索转为客户？"
              onConfirm={async () => {
                try {
                  await convertLead(record.id);
                  message.success('转化成功');
                  actionRef.current?.reload();
                } catch {
                  /* interceptor handles errors */
                }
              }}
            >
              <a>
                <SwapOutlined /> 转化
              </a>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <>
      <ProTable<Lead>
        headerTitle="线索管理"
        actionRef={actionRef}
        rowKey="id"
        columns={columns}
        search={{ labelWidth: 'auto' }}
        toolBarRender={() => [
          <Button
            key="create"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditingLead(null);
              setModalOpen(true);
            }}
          >
            新建线索
          </Button>,
        ]}
        request={async (params) => {
          const { current = 1, pageSize = 20, status } = params;
          const res = await fetchLeads(current, pageSize, status);
          return { data: res.items, total: res.total, success: true };
        }}
        pagination={{ defaultPageSize: 20, showSizeChanger: true }}
      />

      <ModalForm
        title={editingLead ? '编辑线索' : '新建线索'}
        open={modalOpen}
        onOpenChange={setModalOpen}
        initialValues={editingLead || {}}
        modalProps={{ destroyOnClose: true }}
        onFinish={async (values) => {
          try {
            if (editingLead) {
              await updateLead(editingLead.id, values);
              message.success('更新成功');
            } else {
              await createLead(values);
              message.success('创建成功');
            }
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
        <ProFormText name="contactName" label="联系人" rules={[{ required: true }]} />
        <ProFormText name="phone" label="电话" />
        <ProFormText name="email" label="邮箱" />
        <ProFormText name="source" label="来源" />
        <ProFormText name="industry" label="行业" />
        <ProFormSelect name="status" label="状态" options={statusOptions} />
        <ProFormTextArea name="notes" label="备注" />
      </ModalForm>
    </>
  );
};

export default LeadsPage;
