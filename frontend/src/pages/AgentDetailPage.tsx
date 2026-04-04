import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Descriptions, Tag, Button, Tabs, Space, Spin, Table, Select, message, Popconfirm, Modal, Form, Input, InputNumber } from 'antd'
import { ArrowLeftOutlined, PlayCircleOutlined, PauseCircleOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAgent, getAgentUsers, getAgentLogs, activateAgent, deactivateAgent, updateAgentUser, AgentUser, MessageLog } from '../api/agents'
import { getBooks, updateBook, deleteBook, Book } from '../api/bookstore'
import { getVideoJobs, VideoJob } from '../api/videoShorts'

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const agentId = Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [editingBook, setEditingBook] = useState<Book | null>(null)
  const [editForm] = Form.useForm()

  const { data: agent, isLoading } = useQuery({ queryKey: ['agent', agentId], queryFn: () => getAgent(agentId) })
  const { data: users = [] } = useQuery({ queryKey: ['agent-users', agentId], queryFn: () => getAgentUsers(agentId) })
  const { data: logsData } = useQuery({ queryKey: ['agent-logs', agentId], queryFn: () => getAgentLogs(agentId) })
  const { data: books = [] } = useQuery({
    queryKey: ['books', agentId],
    queryFn: () => getBooks(agentId),
    enabled: agent?.agent_type === 'bookstore',
  })

  const { data: videoJobs = [] } = useQuery({
    queryKey: ['video-jobs', agentId],
    queryFn: () => getVideoJobs(agentId),
    enabled: agent?.agent_type === 'video_shorts',
    refetchInterval: 10000,
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

  const updateBookMutation = useMutation({
    mutationFn: (values: Partial<Book>) => updateBook(agentId, editingBook!.id, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books', agentId] })
      message.success('Книга обновлена')
      setEditingBook(null)
    },
    onError: () => message.error('Ошибка при обновлении книги'),
  })

  const deleteBookMutation = useMutation({
    mutationFn: (bookId: number) => deleteBook(agentId, bookId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books', agentId] })
      message.success('Книга удалена')
    },
    onError: () => message.error('Ошибка при удалении книги'),
  })

  const openEditModal = (book: Book) => {
    setEditingBook(book)
    editForm.setFieldsValue({
      title: book.title,
      author: book.author,
      genre: book.genre,
      quantity: book.quantity,
      price: book.price,
      isbn: book.isbn,
      description: book.description,
    })
  }

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
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
          <Tag className={blocked ? 'tag-inactive' : 'tag-active'} style={{ cursor: 'pointer' }}>
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
    { title: 'Автор', dataIndex: 'author', render: (v: string | null) => v || '—' },
    { title: 'Жанр', dataIndex: 'genre', render: (v: string | null) => v || '—' },
    { title: 'Цена', dataIndex: 'price', width: 110, render: (p: number | null) => (p ? `${p} руб.` : '—') },
    {
      title: '',
      width: 90,
      render: (_: unknown, record: Book) => (
        <Space size={4}>
          <Button
            type="text"
            icon={<EditOutlined />}
            size="small"
            onClick={() => openEditModal(record)}
            style={{ color: '#6366f1' }}
          />
          <Popconfirm
            title={`Удалить «${record.title}»?`}
            onConfirm={() => deleteBookMutation.mutate(record.id)}
            okText="Удалить"
            cancelText="Отмена"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="text"
              icon={<DeleteOutlined />}
              size="small"
              danger
            />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const videoJobStatusMap: Record<string, { color: string; label: string }> = {
    downloading: { color: 'blue', label: 'Скачивание' },
    transcribing: { color: 'blue', label: 'Транскрипция' },
    analyzing: { color: 'blue', label: 'Анализ' },
    awaiting_review: { color: 'orange', label: 'Ожидает подтверждения' },
    cutting: { color: 'purple', label: 'Нарезка' },
    sending: { color: 'purple', label: 'Отправка' },
    completed: { color: 'green', label: 'Готово' },
    failed: { color: 'red', label: 'Ошибка' },
    cancelled: { color: 'default', label: 'Отменено' },
  }

  const videoJobColumns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: 'Видео',
      dataIndex: 'video_title',
      ellipsis: true,
      render: (title: string | null, record: VideoJob) => (
        <a href={record.youtube_url} target="_blank" rel="noopener noreferrer" style={{ color: '#6366f1' }}>
          {title || record.youtube_url}
        </a>
      ),
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      width: 180,
      render: (status: string) => {
        const s = videoJobStatusMap[status] || { color: 'default', label: status }
        return <Tag color={s.color}>{s.label}</Tag>
      },
    },
    {
      title: 'Сегменты',
      width: 100,
      render: (_: unknown, record: VideoJob) => {
        const segs = record.approved_segments || record.segments
        return segs ? segs.length : '—'
      },
    },
    {
      title: 'Ошибка',
      dataIndex: 'error_message',
      ellipsis: true,
      render: (err: string | null) => err ? <span style={{ color: '#ef4444' }}>{err}</span> : '—',
    },
    {
      title: 'Дата',
      dataIndex: 'created_at',
      width: 170,
      render: (v: string) => new Date(v).toLocaleString('ru-RU'),
    },
  ]

  const agentCapabilities = agent.agent_type === 'bookstore' ? [
    {
      group: 'Пользователь (все роли)',
      color: '#10b981',
      items: [
        { action: 'Поиск книг', flow: 'Сообщение пользователя → LLM парсит интент (search_books) → Поиск в БД по title/author/genre → Группировка по жанрам → Ответ', file: 'agents/bookstore/agent.py → _handle_search()' },
        { action: 'Рекомендация', flow: 'Сообщение → LLM парсит интент (recommend) → Загрузка книг из БД → LLM генерирует рекомендацию → Ответ', file: 'agents/bookstore/agent.py → _handle_recommend()' },
        { action: 'Список жанров', flow: 'Сообщение → LLM парсит интент (list_genres) → SELECT DISTINCT genre → Ответ', file: 'agents/bookstore/agent.py → _handle_list_genres()' },
        { action: 'Проверка наличия', flow: 'Сообщение → LLM парсит интент (check_inventory) → Поиск в БД → Ответ с количеством', file: 'agents/bookstore/agent.py → _handle_search()' },
      ],
    },
    {
      group: 'Администратор / Менеджер',
      color: '#6366f1',
      items: [
        { action: 'Добавить книги', flow: 'Сообщение → LLM парсит интент (add_books) → Проверка: книга существует? → Если да: +quantity / Если нет: CREATE → Запись в InventoryLog → Ответ', file: 'agents/bookstore/agent.py → _handle_add()' },
        { action: 'Продажа', flow: 'Сообщение → LLM парсит интент (sell_book) → Поиск книги → Проверка остатка → quantity -= N → Запись в InventoryLog → Ответ', file: 'agents/bookstore/agent.py → _handle_sell()' },
        { action: 'Редактирование', flow: 'Сообщение → LLM парсит интент (edit_book) → Поиск книги по title → Обновление полей (title/author/genre/quantity/price) → Если quantity изменён: InventoryLog → Ответ', file: 'agents/bookstore/agent.py → _handle_edit()' },
        { action: 'Удаление', flow: 'Сообщение → LLM парсит интент (remove_book) → Поиск книг по titles[] → Запись в InventoryLog → DELETE → Ответ', file: 'agents/bookstore/agent.py → _handle_remove()' },
      ],
    },
    {
      group: 'Системные',
      color: '#f59e0b',
      items: [
        { action: 'Приветствие', flow: 'Сообщение → LLM парсит интент (greeting) → welcome_message из конфига → Быстрые кнопки', file: 'agents/bookstore/agent.py → handle_message()' },
        { action: 'Помощь', flow: 'Сообщение → LLM парсит интент (help) → Текст помощи по роли пользователя → Ответ', file: 'agents/bookstore/agent.py → _help_text()' },
        { action: 'Быстрые кнопки', flow: 'Нажатие кнопки → Прямой вызов без LLM → "Список книг" → _handle_search() / "Поиск книги" → ожидание ввода', file: 'agents/bookstore/agent.py → handle_message()' },
      ],
    },
  ] : agent.agent_type === 'video_shorts' ? [
    {
      group: 'Основной flow',
      color: '#6366f1',
      items: [
        { action: 'Отправка видео', flow: 'YouTube URL → Валидация длительности → Создание VideoJob → ARQ задача download_and_analyze → Прогресс-сообщения в Telegram', file: 'agents/video_shorts/agent.py → _handle_submit_video()' },
        { action: 'Скачивание + Транскрипция', flow: 'yt-dlp скачивает видео → Берёт субтитры или Whisper → Транскрипт с таймкодами', file: 'agents/video_shorts/jobs.py → download_and_analyze()' },
        { action: 'Анализ сегментов', flow: 'Транскрипт → LLM находит интересные моменты → JSON сегментов → Inline-кнопки в Telegram', file: 'agents/video_shorts/jobs.py → download_and_analyze()' },
        { action: 'Нарезка шортсов', flow: 'Подтверждение → ARQ задача cut_and_send → ffmpeg нарезает → Отправка видео в Telegram', file: 'agents/video_shorts/jobs.py → cut_and_send()' },
      ],
    },
    {
      group: 'Управление',
      color: '#10b981',
      items: [
        { action: 'Подтверждение', flow: 'Кнопка "Подтвердить" или текст → Запуск нарезки', file: 'agents/video_shorts/agent.py → handle_callback_query()' },
        { action: 'Удаление сегмента', flow: 'Кнопка "Убрать N" → Обновление списка → Пере-отправка разметки', file: 'agents/video_shorts/agent.py → handle_callback_query()' },
        { action: 'Отмена', flow: 'Кнопка "Отмена" или текст → Остановка задачи → Очистка файлов', file: 'agents/video_shorts/agent.py → _handle_cancel()' },
        { action: 'Проверка статуса', flow: 'Текст "статус" → Поиск активного VideoJob → Текущий этап обработки', file: 'agents/video_shorts/agent.py → _handle_status()' },
      ],
    },
  ] : []

  const tabs = [
    {
      key: 'info',
      label: 'Информация',
      children: (
        <div>
          <div className="modern-descriptions">
            <Descriptions bordered column={1}>
              <Descriptions.Item label="Название">{agent.name}</Descriptions.Item>
              <Descriptions.Item label="Тип"><Tag className="tag-type">{agent.agent_type}</Tag></Descriptions.Item>
              <Descriptions.Item label="Bot Token">{agent.bot_token}</Descriptions.Item>
              <Descriptions.Item label="Статус">
                <Tag className={agent.is_active ? 'tag-active' : 'tag-inactive'}>
                  {agent.is_active ? 'Активен' : 'Неактивен'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Создан">{new Date(agent.created_at).toLocaleString('ru-RU')}</Descriptions.Item>
            </Descriptions>
          </div>

          {agentCapabilities.length > 0 && (
            <div className="agent-capabilities">
              <h3 className="capabilities-title">Возможности агента</h3>
              <p className="capabilities-subtitle">Цепочка обработки каждого действия. Файлы указаны для быстрого поиска в коде.</p>
              {agentCapabilities.map((group) => (
                <div key={group.group} className="capability-group">
                  <div className="capability-group-header" style={{ borderLeftColor: group.color }}>
                    <span className="capability-group-dot" style={{ background: group.color }} />
                    {group.group}
                  </div>
                  {group.items.map((item) => (
                    <div key={item.action} className="capability-item">
                      <div className="capability-action">{item.action}</div>
                      <div className="capability-flow">
                        {item.flow.split(' → ').map((step, i, arr) => (
                          <React.Fragment key={i}>
                            <span className="flow-step">{step}</span>
                            {i < arr.length - 1 && <span className="flow-arrow">→</span>}
                          </React.Fragment>
                        ))}
                      </div>
                      <div className="capability-file">{item.file}</div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'users',
      label: `Пользователи (${users.length})`,
      children: (
        <div className="modern-table">
          <Table dataSource={users} columns={userColumns} rowKey="id" size="small" />
        </div>
      ),
    },
    {
      key: 'logs',
      label: 'Логи',
      children: (
        <div className="modern-table">
          <Table dataSource={logsData?.items || []} columns={logColumns} rowKey="id" size="small" />
        </div>
      ),
    },
  ]

  if (agent.agent_type === 'bookstore') {
    const saleBooks = books.filter(b => b.category !== 'rental')
    const rentalBooks = books.filter(b => b.category === 'rental')
    tabs.push({
      key: 'books-sale',
      label: `Книги на продажу (${saleBooks.length})`,
      children: (
        <div className="modern-table">
          <Table dataSource={saleBooks} columns={bookColumns} rowKey="id" size="small" />
        </div>
      ),
    })
    tabs.push({
      key: 'books-rental',
      label: `Арендный шкаф (${rentalBooks.length})`,
      children: (
        <div className="modern-table">
          <Table dataSource={rentalBooks} columns={bookColumns} rowKey="id" size="small" />
        </div>
      ),
    })
  }

  if (agent.agent_type === 'video_shorts') {
    tabs.push({
      key: 'video-jobs',
      label: `Видео задания (${videoJobs.length})`,
      children: (
        <div className="modern-table">
          <Table dataSource={videoJobs} columns={videoJobColumns} rowKey="id" size="small" />
        </div>
      ),
    })
  }

  return (
    <>
      <div className="agent-detail-header">
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/agents')}
          style={{ borderRadius: 10 }}
        >
          Назад
        </Button>
        <h1 className="page-title">{agent.name}</h1>
        <Button
          type={agent.is_active ? 'default' : 'primary'}
          icon={agent.is_active ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
          onClick={() => toggleMutation.mutate()}
          className={agent.is_active ? undefined : 'btn-primary'}
          style={{ borderRadius: 10 }}
        >
          {agent.is_active ? 'Остановить' : 'Запустить'}
        </Button>
      </div>

      <Card className="modern-card">
        <div className="modern-tabs">
          <Tabs items={tabs} />
        </div>
      </Card>

      <Modal
        title="Редактирование книги"
        open={!!editingBook}
        onCancel={() => setEditingBook(null)}
        onOk={() => editForm.submit()}
        okText="Сохранить"
        cancelText="Отмена"
        confirmLoading={updateBookMutation.isPending}
        className="modern-modal"
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={(values) => updateBookMutation.mutate(values)}
        >
          <Form.Item name="title" label="Название" rules={[{ required: true, message: 'Введите название' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="author" label="Автор">
            <Input />
          </Form.Item>
          <Form.Item name="genre" label="Жанр">
            <Input />
          </Form.Item>
          <Form.Item name="price" label="Цена (руб.)">
            <InputNumber min={0} step={0.01} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="isbn" label="ISBN">
            <Input />
          </Form.Item>
          <Form.Item name="description" label="Описание">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
