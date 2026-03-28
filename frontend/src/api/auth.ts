import api from './client'

export interface User {
  id: number
  email: string
  display_name: string | null
  is_superadmin: boolean
}

export async function login(email: string, password: string) {
  const { data } = await api.post('/auth/login', { email, password })
  localStorage.setItem('access_token', data.access_token)
  localStorage.setItem('refresh_token', data.refresh_token)
  return data
}

export async function getMe(): Promise<User> {
  const { data } = await api.get('/auth/me')
  return data
}

export function logout() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  window.location.href = '/login'
}
