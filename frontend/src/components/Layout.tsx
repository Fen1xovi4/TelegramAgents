import React from 'react'
import { Layout as AntLayout, Menu, Button, Tooltip } from 'antd'
import { RobotOutlined, LogoutOutlined, DashboardOutlined, SettingOutlined } from '@ant-design/icons'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { logout } from '../api/auth'
import { useAuth } from '../hooks/useAuth'

const { Header, Sider, Content } = AntLayout

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()

  const menuItems = [
    { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
    { key: '/agents', icon: <RobotOutlined />, label: 'Агенты' },
    { key: '/settings', icon: <SettingOutlined />, label: 'Настройки' },
  ]

  const emailInitial = user?.email?.charAt(0).toUpperCase() || '?'

  return (
    <AntLayout className="app-layout">
      <Sider
        className="sidebar"
        width={240}
        breakpoint="lg"
        collapsedWidth={0}
        style={{ position: 'fixed', left: 0, top: 0, bottom: 0, zIndex: 200 }}
      >
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">
            <RobotOutlined />
          </div>
          <div>
            <div className="sidebar-logo-text">TG Agents</div>
            <div className="sidebar-logo-badge">Platform</div>
          </div>
        </div>

        <Menu
          mode="inline"
          selectedKeys={[location.pathname === '/' ? '/' : '/' + location.pathname.split('/')[1]]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />

        <div className="sidebar-footer">
          <div className="sidebar-user" onClick={logout}>
            <div className="sidebar-user-avatar">{emailInitial}</div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-email">{user?.email}</div>
              <div className="sidebar-user-role">Admin</div>
            </div>
            <Tooltip title="Выйти">
              <LogoutOutlined style={{ color: 'rgba(255,255,255,0.35)', fontSize: 14 }} />
            </Tooltip>
          </div>
        </div>
      </Sider>

      <AntLayout style={{ marginLeft: 240, transition: 'margin-left 0.2s' }}>
        <Header className="app-header">
          <Button
            className="header-logout-btn"
            icon={<LogoutOutlined />}
            onClick={logout}
            type="text"
            size="small"
          >
            Выйти
          </Button>
        </Header>
        <Content className="app-content">
          <div className="fade-in">
            <Outlet />
          </div>
        </Content>
      </AntLayout>
    </AntLayout>
  )
}
