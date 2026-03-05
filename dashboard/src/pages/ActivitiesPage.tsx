import React, { useRef, useState } from 'react';
import {
  ProTable,
  ModalForm,
  ProFormText,
  ProFormSelect,
  ProFormDateTimePicker,
  ProFormTextArea,
} from '@ant-design/pro-components';
import type { ProColumns, ActionType } from '@ant-design/pro-components';
import { Button, Tag, message } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { fetchActivities, createActivity, Activity } from '../api/activities';

const typeOptions = [
  { label: '📞 电话', value: 'call' },
  { label: '🏢 拜访', value: 'visit' },
  { label: '📧 邮件', value: 'email' },
  { label: '🤝 会议', value: 'meeting' },
  { label: '📝 其他', value: 'other' },
];

const typeColorMap: Record<string, string> = {
  call: 'blue',
  visit: 'green',
  email: 'purple',
  meeting: 'orange',
  other: 'default',
};

const ActivitiesPage: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [modalOpen, setModalOpen] = useState(false);

  const columns: ProColumns<Activity>[] = [
    {
      title: '类型',
      dataIndex: 'type',
      width: 100,
      valueType: 'select',
      fieldProps: { options: typeOptions },
      render: (_, r) => (
        <Tag color={typeColorMap[r.type] || 'default'}>
          {typeOptions.find((o) => o.value === r.type)?.label || r.type}
        </Tag>
      ),
    },
    { title: '主题', dataIndex: 'subject', ellipsis: true },
    { title: '内容', dataIndex: 'content', ellipsis: true, hideInSearch: true },
    {
      title: '计划时间',
      dataIndex: 'scheduledAt',
      valueType: 'dateTime',
      width: 160,
      hideInSearch: true,
    },
    {
      title: 'AI 摘要',
      dataIndex: 'aiSummary',
      width: 200,
      ellipsis: true,
      hideInSearch: true,
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      valueType: 'dateTime',
      width: 160,
      hideInSearch: true,
    },
  ];

  return (
    <>
      <ProTable<Activity>
        headerTitle="活动记录"
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
            新建活动
          </Button>,
        ]}
        request={async (params) => {
          const { current = 1, pageSize = 20 } = params;
          const res = await fetchActivities(current, pageSize);
          return { data: res.items, total: res.total, success: true };
        }}
        pagination={{ defaultPageSize: 20, showSizeChanger: true }}
      />

      <ModalForm
        title="新建活动"
        open={modalOpen}
        onOpenChange={setModalOpen}
        modalProps={{ destroyOnClose: true }}
        onFinish={async (values) => {
          try {
            await createActivity(values);
            message.success('创建成功');
            actionRef.current?.reload();
            return true;
          } catch {
            return false;
          }
        }}
      >
        <ProFormSelect
          name="type"
          label="活动类型"
          options={typeOptions}
          rules={[{ required: true, message: '请选择活动类型' }]}
        />
        <ProFormText
          name="subject"
          label="主题"
          rules={[{ required: true, message: '请输入主题' }]}
        />
        <ProFormTextArea name="content" label="内容" />
        <ProFormDateTimePicker name="scheduledAt" label="计划时间" />
      </ModalForm>
    </>
  );
};

export default ActivitiesPage;
