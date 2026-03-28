import api from './client'

export interface Book {
  id: number
  agent_id: number
  title: string
  author: string | null
  genre: string | null
  isbn: string | null
  description: string | null
  quantity: number
  price: number | null
  created_at: string
  updated_at: string
}

export interface InventoryLogEntry {
  id: number
  book_id: number
  agent_id: number
  change_type: string
  quantity_change: number
  note: string | null
  performed_by: number | null
  created_at: string
}

export async function getBooks(agentId: number): Promise<Book[]> {
  const { data } = await api.get(`/agents/${agentId}/bookstore/books`)
  return data
}

export async function createBook(agentId: number, body: Partial<Book>): Promise<Book> {
  const { data } = await api.post(`/agents/${agentId}/bookstore/books`, body)
  return data
}

export async function updateBook(agentId: number, bookId: number, body: Partial<Book>): Promise<Book> {
  const { data } = await api.put(`/agents/${agentId}/bookstore/books/${bookId}`, body)
  return data
}

export async function getInventoryLog(agentId: number): Promise<InventoryLogEntry[]> {
  const { data } = await api.get(`/agents/${agentId}/bookstore/inventory-log`)
  return data
}
