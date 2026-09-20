import { read, write } from './index'

export type UpgradeStatus = 'queued' | 'downloading' | 'ready' | 'restarting' | 'backing_up' | 'installing' | 'verifying' | 'succeeded' | 'failed'
export interface UpgradeJob {
  id: number
  target: string
  status: UpgradeStatus
  need_restart: boolean
  execution: 'container' | 'host'
  detail: string
  backup: string
  created_at: string
  updated_at: string
}
export interface UpgradeState {
  current: string
  configured: boolean
  execution: 'container' | 'host'
  runner: { execution: 'container' | 'host'; mode: 'native' | 'docker'; platform: string } | null
  job: UpgradeJob | null
  release?: { version: string; notes: string; published_at: string; url: string }
  available?: boolean
  checked_at?: number
  cached?: boolean
  check_error?: string
}

export async function getUpgrade(check = false, force = false): Promise<UpgradeState> {
  return read('/core/upgrade/', check ? { check: '1', ...(force ? { force: '1' } : {}) } : {})
}
export async function prepareUpgrade(target: string, key: string): Promise<UpgradeJob> {
  return write('/core/upgrade/', { target, confirmed: true }, key)
}
export async function restartUpgrade(id: number, key: string): Promise<UpgradeJob> {
  return write('/core/upgrade/restart/', { id, confirmed: true }, key)
}
