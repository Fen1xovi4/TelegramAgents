import React from 'react'
import { Card, Table, Tag, Empty } from 'antd'
import { RobotOutlined, ThunderboltOutlined, PauseCircleOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getAgents, Agent } from '../api/agents'

export default function DashboardPage() {
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: getAgents })
  const navigate = useNavigate()

  const activeCount = agents.filter((a) => a.is_active).length
  const inactiveCount = agents.length - activeCount

  const stats = [
    {
      label: 'Всего агентов',
      value: agents.length,
      icon: <RobotOutlined />,
      color: 'indigo',
    },
    {
      label: 'Активных',
      value: activeCount,
      icon: <ThunderboltOutlined />,
      color: 'emerald',
    },
    {
      label: 'Неактивных',
      value: inactiveCount,
      icon: <PauseCircleOutlined />,
      color: 'rose',
    },
  ]

  const recentColumns = [
    {
      title: 'Название',
      dataIndex: 'name',
      render: (name: string, record: Agent) => (
        <a onClick={() => navigate(`/agents/${record.id}`)} style={{ fontWeight: 500 }}>{name}</a>
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
      title: 'Создан',
      dataIndex: 'created_at',
      render: (v: string) => new Date(v).toLocaleDateString('ru-RU'),
    },
  ]

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <div className="page-subtitle">Обзор ваших Telegram-агентов</div>
        </div>
      </div>

      <div className="stat-grid">
        {stats.map((stat) => (
          <div className="stat-card" key={stat.label}>
            <div className="stat-card-header">
              <div className={`stat-card-icon ${stat.color}`}>
                {stat.icon}
              </div>
            </div>
            <div className="stat-card-label">{stat.label}</div>
            <div className="stat-card-value">{stat.value}</div>
          </div>
        ))}
      </div>

      <Card
        className="modern-card"
        title={<span style={{ fontWeight: 600, fontSize: 15 }}>Агенты</span>}
        styles={{ header: { borderBottom: '1px solid #f1f3f8' } }}
      >
        {agents.length === 0 ? (
          <Empty description="Нет агентов" />
        ) : (
          <div className="modern-table">
            <Table
              dataSource={agents}
              columns={recentColumns}
              rowKey="id"
              size="middle"
              pagination={false}
            />
          </div>
        )}
      </Card>
    </>
  )
}
