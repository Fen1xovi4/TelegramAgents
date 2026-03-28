import api from './client'

export interface LLMConnection {
  id: number
  name: string
  provider: string
  masked_key: string
  model: string
  purpose: string
  purpose_label: string
  is_default: boolean
  connected: boolean | null
  error: string | null
  created_at: string
}

export interface ModelOption {
  id: string
  label: string
}

export interface ProviderInfo {
  id: string
  label: string
  models: ModelOption[]
}

export interface SettingsOverview {
  connections: LLMConnection[]
  providers: ProviderInfo[]
  purposes: Record<string, string>
}

export interface CreateConnectionBody {
  name: string
  provider: string
  api_key: string
  model: string
  purpose: string
  is_default: boolean
}

export async function getSettings(): Promise<SettingsOverview> {
  const { data } = await api.get('/settings')
  return data
}

export async function createConnection(body: CreateConnectionBody): Promise<LLMConnection> {
  const { data } = await api.post('/settings/connections', body)
  return data
}

export async function updateConnection(id: number, body: Partial<CreateConnectionBody>): Promise<LLMConnection> {
  const { data } = await api.put(`/settings/connections/${id}`, body)
  return data
}

export async function deleteConnection(id: number): Promise<void> {
  await api.delete(`/settings/connections/${id}`)
}

export async function testConnection(id: number): Promise<LLMConnection> {
  const { data } = await api.post(`/settings/connections/${id}/test`)
  return data
}

export async function testAllConnections(): Promise<LLMConnection[]> {
  const { data } = await api.post('/settings/test-all')
  return data
}
