import React, { useState } from 'react'
import { Card, Form, Input, Button, Typography, message } from 'antd'
import { UserOutlined, LockOutlined, RobotOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { login } from '../api/auth'

const { Title } = Typography

export default function LoginPage() {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const onFinish = async (values: { email: string; password: string }) => {
    setLoading(true)
    try {
      await login(values.email, values.password)
      navigate('/')
    } catch {
      message.error('Неверный email или пароль')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <Card className="login-card" bordered={false}>
        <div className="login-header">
          <div className="login-logo-icon">
            <RobotOutlined />
          </div>
          <Title level={3} className="login-title">
            TG Agents
          </Title>
          <div className="login-subtitle">Войдите в панель управления</div>
        </div>

        <Form onFinish={onFinish} size="large" layout="vertical">
          <Form.Item name="email" rules={[{ required: true, message: 'Введите email' }]}>
            <Input prefix={<UserOutlined />} placeholder="Email" autoComplete="email" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: 'Введите пароль' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="Пароль" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={loading} block>
              Войти
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
