import React, { useState } from 'react'
import {
  Card, Typography, Button, Input, Space, Tag, Spin, message,
  Modal, Select, Form, Table, Popconfirm, Switch, Empty,
} from 'antd'
import {
  PlusOutlined, CheckCircleOutlined, CloseCircleOutlined,
  SyncOutlined, ExclamationCircleOutlined, DeleteOutlined,
  EditOutlined, ThunderboltOutlined, StarFilled, StarOutlined,
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getSettings, createConnection, updateConnection, deleteConnection,
  testConnection, testAllConnections, LLMConnection, CreateConnectionBody, SettingsOverview,
} from '../api/settings'

const { Text, Paragraph } = Typography

function ProviderTag({ provider }: { provider: string }) {
  const colors: Record<string, string> = { openai: 'green', anthropic: 'purple' }
  return <Tag color={colors[provider] || 'default'} style={{ borderRadius: 6 }}>{provider}</Tag>
}

function PurposeTag({ purpose, label }: { purpose: string; label: string }) {
  const colors: Record<string, string> = { chat: 'blue', stt: 'orange' }
  return <Tag color={colors[purpose] || 'default'} style={{ borderRadius: 6 }}>{label}</Tag>
}

function StatusIcon({ conn }: { conn: LLMConnection }) {
  if (conn.connected === null) return <Tag style={{ borderRadius: 6 }}>Не проверен</Tag>
  if (conn.connected) return <Tag icon={<CheckCircleOutlined />} color="success" style={{ borderRadius: 6 }}>OK</Tag>
  return (
    <Tag icon={<CloseCircleOutlined />} color="error" style={{ borderRadius: 6 }}>
      {conn.error || 'Ошибка'}
    </Tag>
  )
}

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form] = Form.useForm()

  const { data, isLoading } = useQuery({ queryKey: ['settings'], queryFn: getSettings })

  const createMut = useMutation({
    mutationFn: createConnection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      setModalOpen(false)
      form.resetFields()
      message.success('Подключение добавлено')
    },
    onError: () => message.error('Ошибка при создании'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<CreateConnectionBody> }) => updateConnection(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      setModalOpen(false)
      setEditingId(null)
      form.resetFields()
      message.success('Подключение обновлено')
    },
    onError: () => message.error('Ошибка при обновлении'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteConnection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      message.success('Подключение удалено')
    },
  })

  const testOneMut = useMutation({
    mutationFn: testConnection,
    onSuccess: (result) => {
      queryClient.setQueryData<SettingsOverview>(['settings'], (old) => {
        if (!old) return old
        return {
          ...old,
          connections: old.connections.map((c) => c.id === result.id ? result : c),
        }
      })
      if (result.connected) message.success(`${result.name}: подключение работает`)
      else message.error(`${result.name}: ${result.error}`)
    },
  })

  const testAllMut = useMutation({
    mutationFn: testAllConnections,
    onSuccess: (results) => {
      queryClient.setQueryData<SettingsOverview>(['settings'], (old) => {
        if (!old) return old
        return { ...old, connections: results }
      })
      const ok = results.filter((r) => r.connected).length
      const fail = results.filter((r) => r.connected === false).length
      if (fail === 0 && ok > 0) message.success(`Все подключения работают (${ok})`)
      else if (ok > 0) message.warning(`Работает: ${ok}, ошибки: ${fail}`)
      else if (results.length === 0) message.info('Нет подключений для проверки')
      else message.error(`Все подключения с ошибками (${fail})`)
    },
  })

  const selectedProvider = Form.useWatch('provider', form)
  const providerModels = data?.providers.find((p) => p.id === selectedProvider)?.models || []

  const openCreate = () => {
    setEditingId(null)
    form.resetFields()
    form.setFieldsValue({ purpose: 'chat', is_default: true })
    setModalOpen(true)
  }

  const openEdit = (conn: LLMConnection) => {
    setEditingId(conn.id)
    form.setFieldsValue({
      name: conn.name,
      provider: conn.provider,
      model: conn.model,
      purpose: conn.purpose,
      is_default: conn.is_default,
      api_key: '',
    })
    setModalOpen(true)
  }

  const handleSubmit = (values: any) => {
    if (editingId) {
      const body: any = { ...values }
      if (!body.api_key) delete body.api_key
      updateMut.mutate({ id: editingId, body })
    } else {
      createMut.mutate(values as CreateConnectionBody)
    }
  }

  const columns = [
    {
      title: '',
      dataIndex: 'is_default',
      width: 40,
      render: (def: boolean, record: LLMConnection) => (
        <Button
          type="text"
          size="small"
          icon={def ? <StarFilled style={{ color: '#f59e0b' }} /> : <StarOutlined style={{ color: '#d1d5db' }} />}
          onClick={() => updateMut.mutate({ id: record.id, body: { is_default: true } })}
          title={def ? 'По умолчанию' : 'Сделать по умолчанию'}
        />
      ),
    },
    { title: 'Название', dataIndex: 'name', ellipsis: true },
    {
      title: 'Провайдер',
      dataIndex: 'provider',
      width: 120,
      render: (p: string) => <ProviderTag provider={p} />,
    },
    { title: 'Модель', dataIndex: 'model', width: 200 },
    {
      title: 'Назначение',
      dataIndex: 'purpose',
      width: 180,
      render: (p: string, record: LLMConnection) => <PurposeTag purpose={p} label={record.purpose_label} />,
    },
    { title: 'Ключ', dataIndex: 'masked_key', width: 160, render: (k: string) => <Text code>{k}</Text> },
    {
      title: 'Статус',
      width: 150,
      render: (_: unknown, record: LLMConnection) => <StatusIcon conn={record} />,
    },
    {
      title: 'Действия',
      width: 160,
      render: (_: unknown, record: LLMConnection) => (
        <Space>
          <Button
            size="small"
            icon={<ThunderboltOutlined />}
            onClick={() => testOneMut.mutate(record.id)}
            loading={testOneMut.isPending}
            title="Проверить"
            style={{ borderRadius: 8 }}
          />
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} title="Редактировать" style={{ borderRadius: 8 }} />
          <Popconfirm title="Удалить подключение?" onConfirm={() => deleteMut.mutate(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} title="Удалить" style={{ borderRadius: 8 }} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

  const chatConns = data?.connections.filter((c) => c.purpose === 'chat') || []
  const hasDefaultChat = chatConns.some((c) => c.is_default)

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Настройки LLM</h1>
          <div className="page-subtitle">Управление подключениями к языковым моделям</div>
        </div>
        <Space>
          <Button
            icon={<SyncOutlined spin={testAllMut.isPending} />}
            onClick={() => testAllMut.mutate()}
            loading={testAllMut.isPending}
            style={{ borderRadius: 10 }}
          >
            Проверить все
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} className="btn-primary">
            Добавить LLM
          </Button>
        </Space>
      </div>

      {!hasDefaultChat && data && data.connections.length > 0 && (
        <Card className="warning-banner" styles={{ body: { padding: '12px 16px' } }} style={{ marginBottom: 20 }}>
          <Space>
            <ExclamationCircleOutlined style={{ color: '#f59e0b' }} />
            <Text style={{ color: '#92400e' }}>Нет подключения по умолчанию для чата. Нажмите звёздочку, чтобы назначить.</Text>
          </Space>
        </Card>
      )}

      {data?.connections.length === 0 ? (
        <div className="empty-state">
          <Empty description="Нет подключений к LLM">
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} className="btn-primary">
              Добавить первое подключение
            </Button>
          </Empty>
        </div>
      ) : (
        <div className="modern-table">
          <Table
            dataSource={data?.connections}
            columns={columns}
            rowKey="id"
            size="middle"
            pagination={false}
          />
        </div>
      )}

      <Card className="info-card">
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, color: '#1a1d2e' }}>Как это работает</h3>
        <Paragraph style={{ color: '#64748b', marginBottom: 8 }}>
          Каждое подключение — это комбинация провайдера, API-ключа, модели и назначения.
        </Paragraph>
        <Paragraph style={{ color: '#64748b', marginBottom: 8 }}>
          <Text strong style={{ color: '#475569' }}>Чат / ответы</Text> — модель для обработки сообщений пользователей (парсинг интентов, рекомендации).
          <br />
          <Text strong style={{ color: '#475569' }}>STT (речь → текст)</Text> — модель для распознавания голосовых сообщений (Whisper).
        </Paragraph>
        <Paragraph style={{ color: '#64748b', marginBottom: 0 }}>
          Подключение со звёздочкой — используется по умолчанию. Можно добавить несколько подключений
          с разными ключами и моделями для разных целей.
        </Paragraph>
      </Card>

      <Modal
        title={editingId ? 'Редактировать подключение' : 'Добавить LLM-подключение'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingId(null); form.resetFields() }}
        onOk={() => form.submit()}
        okText={editingId ? 'Сохранить' : 'Добавить'}
        cancelText="Отмена"
        confirmLoading={createMut.isPending || updateMut.isPending}
        width={520}
        className="modern-modal"
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="name" label="Название" rules={[{ required: !editingId }]}>
            <Input placeholder="Например: GPT-4o Mini для ответов" />
          </Form.Item>

          <Form.Item name="provider" label="Провайдер" rules={[{ required: !editingId }]}>
            <Select
              placeholder="Выберите провайдера"
              onChange={() => form.setFieldValue('model', undefined)}
            >
              {data?.providers.map((p) => (
                <Select.Option key={p.id} value={p.id}>{p.label}</Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item name="model" label="Модель" rules={[{ required: !editingId }]}>
            <Select placeholder="Выберите модель" disabled={!selectedProvider}>
              {providerModels.map((m) => (
                <Select.Option key={m.id} value={m.id}>{m.label}</Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item name="purpose" label="Назначение" rules={[{ required: !editingId }]}>
            <Select placeholder="Для чего используется">
              {data && Object.entries(data.purposes).map(([key, label]) => (
                <Select.Option key={key} value={key}>{label}</Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="api_key"
            label="API-ключ"
            rules={[{ required: !editingId }]}
            extra={editingId ? 'Оставьте пустым, чтобы не менять' : undefined}
          >
            <Input.Password placeholder="sk-..." />
          </Form.Item>

          <Form.Item name="is_default" label="По умолчанию" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
