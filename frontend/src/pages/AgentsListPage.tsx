import React, { useState } from 'react'
import { Button, Table, Tag, Space, Modal, Form, Input, Select, Typography, message, Popconfirm } from 'antd'
import { PlusOutlined, PlayCircleOutlined, PauseCircleOutlined, DeleteOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getAgents, createAgent, deleteAgent, activateAgent, deactivateAgent, Agent } from '../api/agents'

const { Title } = Typography

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
        <a onClick={() => navigate(`/agents/${record.id}`)}>{name}</a>
      ),
    },
    { title: 'Тип', dataIndex: 'agent_type', render: (t: string) => <Tag color="blue">{t}</Tag> },
    {
      title: 'Статус',
      dataIndex: 'is_active',
      render: (active: boolean) => <Tag color={active ? 'green' : 'default'}>{active ? 'Активен' : 'Неактивен'}</Tag>,
    },
    {
      title: 'Действия',
      render: (_: unknown, record: Agent) => (
        <Space>
          <Button
            size="small"
            icon={record.is_active ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
            onClick={() => toggleMutation.mutate({ id: record.id, active: record.is_active })}
          >
            {record.is_active ? 'Стоп' : 'Старт'}
          </Button>
          <Popconfirm title="Удалить агента?" onConfirm={() => deleteMutation.mutate(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Агенты</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          Создать агента
        </Button>
      </div>

      <Table dataSource={agents} columns={columns} rowKey="id" loading={isLoading} />

      <Modal
        title="Новый агент"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending}
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
