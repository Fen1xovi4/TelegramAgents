import api from './client'

export interface VideoJob {
  id: number
  agent_id: number
  telegram_id: number
  youtube_url: string
  video_title: string | null
  status: string
  segments: Segment[] | null
  approved_segments: Segment[] | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface Segment {
  id: number
  start: number
  end: number
  title: string
  reason: string
}

export async function getVideoJobs(agentId: number): Promise<VideoJob[]> {
  const { data } = await api.get(`/agents/${agentId}/video-jobs`)
  return data
}

export async function getVideoJob(agentId: number, jobId: number): Promise<VideoJob> {
  const { data } = await api.get(`/agents/${agentId}/video-jobs/${jobId}`)
  return data
}
