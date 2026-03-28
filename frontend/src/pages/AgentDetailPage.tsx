import React from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Descriptions, Tag, Button, Tabs, Space, Typography, Spin, Table, Select, message, Popconfirm } from 'antd'
import { ArrowLeftOutlined, PlayCircleOutlined, PauseCircleOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAgent, getAgentUsers, getAgentLogs, activateAgent, deactivateAgent, updateAgentUser, AgentUser, MessageLog } from '../api/agents'
import { getBooks, Book } from '../api/bookstore'

const { Title } = Typography

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const agentId = Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: agent, isLoading } = useQuery({ queryKey: ['agent', agentId], queryFn: () => getAgent(agentId) })
  const { data: users = [] } = useQuery({ queryKey: ['agent-users', agentId], queryFn: () => getAgentUsers(agentId) })
  const { data: logsData } = useQuery({ queryKey: ['agent-logs', agentId], queryFn: () => getAgentLogs(agentId) })
  const { data: books = [] } = useQuery({
    queryKey: ['books', agentId],
    queryFn: () => getBooks(agentId),
    enabled: agent?.agent_type === 'bookstore',
  })

  const toggleMutation = useMutation({
    mutationFn: () => (agent?.is_active ? deactivateAgent(agentId) : activateAgent(agentId)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agent', agentId] }),
  })

  const updateUserMutation = useMutation({
    mutationFn: ({ userId, body }: { userId: number; body: { role?: string; is_blocked?: boolean } }) =>
      updateAgentUser(agentId, userId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-users', agentId] })
      message.success('Пользователь обновлён')
    },
  })

  if (isLoading) return <Spin size="large" />
  if (!agent) return <div>Агент не найден</div>

  const userColumns = [
    { title: 'Telegram ID', dataIndex: 'telegram_id' },
    { title: 'Username', dataIndex: 'telegram_username' },
    { title: 'Имя', dataIndex: 'display_name' },
    {
      title: 'Роль',
      dataIndex: 'role',
      render: (role: string, record: AgentUser) => (
        <Select
          value={role}
          size="small"
          style={{ width: 120 }}
          onChange={(value) => updateUserMutation.mutate({ userId: record.id, body: { role: value } })}
        >
          <Select.Option value="admin">Admin</Select.Option>
          <Select.Option value="manager">Manager</Select.Option>
          <Select.Option value="user">User</Select.Option>
        </Select>
      ),
    },
    {
      title: 'Заблокирован',
      dataIndex: 'is_blocked',
      render: (blocked: boolean, record: AgentUser) => (
        <Popconfirm
          title={blocked ? 'Разблокировать?' : 'Заблокировать?'}
          onConfirm={() => updateUserMutation.mutate({ userId: record.id, body: { is_blocked: !blocked } })}
        >
          <Tag color={blocked ? 'red' : 'green'} style={{ cursor: 'pointer' }}>
            {blocked ? 'Да' : 'Нет'}
          </Tag>
        </Popconfirm>
      ),
    },
  ]

  const logColumns = [
    { title: 'Время', dataIndex: 'created_at', render: (v: string) => new Date(v).toLocaleString('ru-RU'), width: 170 },
    { title: 'TG ID', dataIndex: 'telegram_id', width: 120 },
    { title: 'Тип', dataIndex: 'message_type', width: 80 },
    { title: 'Сообщение', dataIndex: 'content_text', ellipsis: true },
    { title: 'Интент', dataIndex: 'intent', width: 120 },
    { title: 'Ответ', dataIndex: 'response_text', ellipsis: true },
    { title: 'ms', dataIndex: 'processing_ms', width: 60 },
  ]

  const bookColumns = [
    { title: 'Название', dataIndex: 'title' },
    { title: 'Автор', dataIndex: 'author' },
    { title: 'Жанр', dataIndex: 'genre' },
    { title: 'Кол-во', dataIndex: 'quantity' },
    { title: 'Цена', dataIndex: 'price', render: (p: number | null) => (p ? `${p} руб.` : '—') },
  ]

  const tabs = [
    {
      key: 'info',
      label: 'Информация',
      children: (
        <Descriptions bordered column={1}>
          <Descriptions.Item label="Название">{agent.name}</Descriptions.Item>
          <Descriptions.Item label="Тип">{agent.agent_type}</Descriptions.Item>
          <Descriptions.Item label="Bot Token">{agent.bot_token}</Descriptions.Item>
          <Descriptions.Item label="Статус">
            <Tag color={agent.is_active ? 'green' : 'default'}>{agent.is_active ? 'Активен' : 'Неактивен'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Создан">{new Date(agent.created_at).toLocaleString('ru-RU')}</Descriptions.Item>
        </Descriptions>
      ),
    },
    {
      key: 'users',
      label: `Пользователи (${users.length})`,
      children: <Table dataSource={users} columns={userColumns} rowKey="id" size="small" />,
    },
    {
      key: 'logs',
      label: 'Логи',
      children: <Table dataSource={logsData?.items || []} columns={logColumns} rowKey="id" size="small" />,
    },
  ]

  if (agent.agent_type === 'bookstore') {
    tabs.push({
      key: 'books',
      label: `Книги (${books.length})`,
      children: <Table dataSource={books} columns={bookColumns} rowKey="id" size="small" />,
    })
  }

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/agents')}>Назад</Button>
        <Title level={4} style={{ margin: 0 }}>{agent.name}</Title>
        <Button
          type={agent.is_active ? 'default' : 'primary'}
          icon={agent.is_active ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
          onClick={() => toggleMutation.mutate()}
        >
          {agent.is_active ? 'Остановить' : 'Запустить'}
        </Button>
      </Space>

      <Card>
        <Tabs items={tabs} />
      </Card>
    </>
  )
}
