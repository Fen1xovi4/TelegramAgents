import React, { useState } from 'react'
import { Button, Table, Tag, Space, Modal, Form, Input, Select, message, Popconfirm } from 'antd'
import { PlusOutlined, PlayCircleOutlined, PauseCircleOutlined, DeleteOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getAgents, createAgent, deleteAgent, activateAgent, deactivateAgent, Agent } from '../api/agents'

export default function AgentsListPage() {
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const { data: agents = [], isLoading } = useQuery({ queryKey: ['agents'], queryFn: getAgents })

  const createMutation = useMutation({
    mutationFn: createAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      setOpen(false)
      form.resetFields()
      message.success('Агент создан')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      message.success('Агент удалён')
    },
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      active ? deactivateAgent(id) : activateAgent(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agents'] }),
  })

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: 'Название',
      dataIndex: 'name',
      render: (name: string, record: Agent) => (
        <a onClick={() => navigate(`/agents/${record.id}`)} style={{ fontWeight: 500, color: '#6366f1' }}>
          {name}
        </a>
      ),
    },
    {
      title: 'Тип',
      dataIndex: 'agent_type',
      render: (t: string) => <Tag className="tag-type">{t}</Tag>,
    },
    {
      title: 'Статус',
      dataIndex: 'is_active',
      render: (active: boolean) => (
        <Tag className={active ? 'tag-active' : 'tag-inactive'}>
          {active ? 'Активен' : 'Неактивен'}
        </Tag>
      ),
    },
    {
      title: 'Действия',
      render: (_: unknown, record: Agent) => (
        <Space>
          <Button
            size="small"
            icon={record.is_active ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
            onClick={() => toggleMutation.mutate({ id: record.id, active: record.is_active })}
            style={{ borderRadius: 8 }}
          >
            {record.is_active ? 'Стоп' : 'Старт'}
          </Button>
          <Popconfirm title="Удалить агента?" onConfirm={() => deleteMutation.mutate(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} style={{ borderRadius: 8 }} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Агенты</h1>
          <div className="page-subtitle">Управление вашими Telegram-ботами</div>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setOpen(true)}
          className="btn-primary"
        >
          Создать агента
        </Button>
      </div>

      <div className="modern-table">
        <Table dataSource={agents} columns={columns} rowKey="id" loading={isLoading} />
      </div>

      <Modal
        title="Новый агент"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending}
        className="modern-modal"
        okText="Создать"
        cancelText="Отмена"
      >
        <Form form={form} layout="vertical" onFinish={(values) => createMutation.mutate(values)}>
          <Form.Item name="name" label="Название" rules={[{ required: true }]}>
            <Input placeholder="Мой книжный магазин" />
          </Form.Item>
          <Form.Item name="agent_type" label="Тип агента" rules={[{ required: true }]}>
            <Select placeholder="Выберите тип">
              <Select.Option value="bookstore">Книжный магазин</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="bot_token" label="Bot Token (Telegram)" rules={[{ required: true }]}>
            <Input placeholder="123456:ABC-DEF..." />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
