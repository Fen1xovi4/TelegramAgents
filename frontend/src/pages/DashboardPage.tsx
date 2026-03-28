import React from 'react'
import { Card, Col, Row, Statistic, Typography } from 'antd'
import { RobotOutlined, TeamOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { getAgents } from '../api/agents'

const { Title } = Typography

export default function DashboardPage() {
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: getAgents })

  const activeCount = agents.filter((a) => a.is_active).length

  return (
    <>
      <Title level={4}>Dashboard</Title>
      <Row gutter={16}>
        <Col span={8}>
          <Card>
            <Statistic title="Всего агентов" value={agents.length} prefix={<RobotOutlined />} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="Активных" value={activeCount} prefix={<TeamOutlined />} valueStyle={{ color: '#3f8600' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="Неактивных" value={agents.length - activeCount} valueStyle={{ color: '#cf1322' }} />
          </Card>
        </Col>
      </Row>
    </>
  )
}
