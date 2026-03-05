import React, { useRef, useState } from 'react';
import {
  ProTable,
  ModalForm,
  ProFormText,
  ProFormSelect,
  ProFormDigit,
  ProFormDatePicker,
  ProFormTextArea,
} from '@ant-design/pro-components';
import type { ProColumns, ActionType } from '@ant-design/pro-components';
import { Button, Tag, message, Space } from 'antd';
import { PlusOutlined, EditOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  fetchOpportunities,
  createOpportunity,
  updateOpportunity,
  Opportunity,
} from '../api/opportunities';

const stageOptions = [
  { label: '初步接触', value: 'initial_contact' },
  { label: '需求确认', value: 'needs_confirmed' },
  { label: '方案评审', value: 'solution_review' },
  { label: '商务谈判', value: 'negotiation' },
  { label: '赢单', value: 'won' },
  { label: '输单', value: 'lost' },
];

const stageColorMap: Record<string, string> = {
  initial_contact: 'blue',
  needs_confirmed: 'cyan',
  solution_review: 'geekblue',
  negotiation: 'orange',
  won: 'green',
  lost: 'red',
};

const OpportunitiesPage: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Opportunity | null>(null);

  const columns: ProColumns<Opportunity>[] = [
    { title: '商机名称', dataIndex: 'name', ellipsis: true },
    {
      title: '金额',
      dataIndex: 'amount',
      width: 120,
      hideInSearch: true,
      render: (_, r) =>
        r.amount != null ? `¥${Number(r.amount).toLocaleString()}` : '-',
      sorter: true,
    },
    {
      title: '阶段',
      dataIndex: 'stage',
      width: 110,
      valueType: 'select',
      fieldProps: { options: stageOptions },
      render: (_, r) => (
        <Tag color={stageColorMap[r.stage] || 'default'}>
          {stageOptions.find((o) => o.value === r.stage)?.label || r.stage}
        </Tag>
      ),
    },
    {
      title: '预计成交',
      dataIndex: 'expectedCloseDate',
      width: 120,
      hideInSearch: true,
      render: (_, r) =>
        r.expectedCloseDate ? dayjs(r.expectedCloseDate).format('YYYY-MM-DD') : '-',
    },
    { title: '产品类型', dataIndex: 'productType', width: 100, hideInSearch: true },
    {
      title: '赢率',
      dataIndex: 'winRate',
      width: 80,
      hideInSearch: true,
      render: (_, r) => (r.winRate != null ? `${r.winRate}%` : '-'),
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
      width: 100,
      render: (_, record) => (
        <Space size="small">
          <a
            onClick={() => {
              setEditing(record);
              setModalOpen(true);
            }}
          >
            <EditOutlined /> 编辑
          </a>
        </Space>
      ),
    },
  ];

  return (
    <>
      <ProTable<Opportunity>
        headerTitle="商机管理"
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
              setEditing(null);
              setModalOpen(true);
            }}
          >
            新建商机
          </Button>,
        ]}
        request={async (params) => {
          const { current = 1, pageSize = 20, stage } = params;
          const res = await fetchOpportunities(current, pageSize, stage);
          return { data: res.items, total: res.total, success: true };
        }}
        pagination={{ defaultPageSize: 20, showSizeChanger: true }}
      />

      <ModalForm
        title={editing ? '编辑商机' : '新建商机'}
        open={modalOpen}
        onOpenChange={setModalOpen}
        initialValues={
          editing
            ? {
                ...editing,
                expectedCloseDate: editing.expectedCloseDate
                  ? dayjs(editing.expectedCloseDate)
                  : undefined,
              }
            : {}
        }
        modalProps={{ destroyOnClose: true }}
        onFinish={async (values) => {
          try {
            const payload = {
              ...values,
              expectedCloseDate: values.expectedCloseDate
                ? dayjs(values.expectedCloseDate).format('YYYY-MM-DD')
                : undefined,
            };
            if (editing) {
              await updateOpportunity(editing.id, payload);
              message.success('更新成功');
            } else {
              await createOpportunity(payload);
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
          name="name"
          label="商机名称"
          rules={[{ required: true, message: '请输入商机名称' }]}
        />
        <ProFormDigit name="amount" label="金额" min={0} fieldProps={{ precision: 2 }} />
        <ProFormSelect name="stage" label="阶段" options={stageOptions} />
        <ProFormDatePicker name="expectedCloseDate" label="预计成交日期" />
        <ProFormText name="productType" label="产品类型" />
        <ProFormDigit name="winRate" label="赢率 (%)" min={0} max={100} />
        <ProFormTextArea name="notes" label="备注" />
        {editing && (
          <ProFormTextArea name="lostReason" label="丢单原因" />
        )}
      </ModalForm>
    </>
  );
};

export default OpportunitiesPage;
