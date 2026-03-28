import api from './client'

export interface Agent {
  id: number
  name: string
  agent_type: string
  bot_token: string
  bot_username: string | null
  config: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AgentUser {
  id: number
  agent_id: number
  telegram_id: number
  telegram_username: string | null
  display_name: string | null
  role: string
  is_blocked: boolean
}

export interface MessageLog {
  id: number
  agent_id: number
  telegram_id: number
  direction: string
  message_type: string
  content_text: string | null
  intent: string | null
  intent_data: Record<string, unknown> | null
  response_text: string | null
  processing_ms: number | null
  created_at: string
}

export async function getAgents(): Promise<Agent[]> {
  const { data } = await api.get('/agents')
  return data
}

export async function getAgent(id: number): Promise<Agent> {
  const { data } = await api.get(`/agents/${id}`)
  return data
}

export async function createAgent(body: { name: string; agent_type: string; bot_token: string; config?: Record<string, unknown> }): Promise<Agent> {
  const { data } = await api.post('/agents', body)
  return data
}

export async function updateAgent(id: number, body: Partial<Agent>): Promise<Agent> {
  const { data } = await api.put(`/agents/${id}`, body)
  return data
}

export async function deleteAgent(id: number): Promise<void> {
  await api.delete(`/agents/${id}`)
}

export async function activateAgent(id: number): Promise<Agent> {
  const { data } = await api.post(`/agents/${id}/activate`)
  return data
}

export async function deactivateAgent(id: number): Promise<Agent> {
  const { data } = await api.post(`/agents/${id}/deactivate`)
  return data
}

export async function getAgentUsers(agentId: number): Promise<AgentUser[]> {
  const { data } = await api.get(`/agents/${agentId}/users`)
  return data
}

export async function updateAgentUser(agentId: number, userId: number, body: { role?: string; is_blocked?: boolean }): Promise<AgentUser> {
  const { data } = await api.put(`/agents/${agentId}/users/${userId}`, body)
  return data
}

export async function getAgentLogs(agentId: number, page = 1, perPage = 50): Promise<{ items: MessageLog[]; total: number; page: number; per_page: number }> {
  const { data } = await api.get(`/agents/${agentId}/logs`, { params: { page, per_page: perPage } })
  return data
}
