// API клиенті: нақты backend (/api) немесе GitHub Pages үшін статикалық демо (VITE_DEMO=1)
import { demoRequest } from './demo'

export const DEMO = import.meta.env.VITE_DEMO === '1'

export interface Role {
  id: number; code: string; title_kk: string; title_ru: string; title_en: string; grade: number; family: string
  esco_occupation_id: string; esco_occupation_label: string; description_kk: string; description_ru: string
  prof_standard_ref: string; skills_count?: number
}
export interface User { id: number; username: string; role: 'employee' | 'manager' | 'hr'; display_name: string; department_id: number | null; employee_id: number | null }
export interface Employee {
  id: number; code: string; department_id: number; department_kk: string; department_ru: string
  current_role: Role | null; target_role: Role | null; consent_at: string | null
  skills?: number; confirmed?: number; idp_status?: string | null; target_coverage?: number
  documents?: { id: number; type: string; lang: string; filename: string | null; uploaded_at: string; chars: number }[]
  latest_text?: string | null
}
export interface EmpSkill {
  esco_id: string; label: string; type: string; description: string; level: number; evidence: string; phrase: string
  source: string; status: 'auto' | 'unverified' | 'confirmed' | 'rejected'; confidence: number; similarity: number
}
export interface GapItem { esco_id: string; label: string; weight: number; required_level: number; employee_level: number; priority: number; relation: string }
export interface Gap { role_id: number; coverage: number; total_weight: number; matched: GapItem[]; missing: GapItem[] }
export interface RoleRec {
  role_id: number; code: string; title_kk: string; title_ru: string; score: number; p_transition: number; p_normalized: number
  coverage: number; alpha_part: number; skill_part: number; transition_count: number; top_missing: { esco_id: string; label: string; priority: number }[]
}
export interface Course { id: number; title: string; provider: string; url: string; lang: string; level: string; duration_h: number | null; is_free: boolean; esco_ids: string[]; description: string; skills?: string[] }
export interface IdpItem {
  esco_id: string; skill: string; skill_description: string; priority: number; weight: number; relation: string
  from_level: number; to_level: number; period: number; courses: Course[]; practice: string; success_criteria: string
}
export interface IdpPlan {
  target_role: { id: number; code: string; title_kk: string; title_ru: string }; lang: string; coverage_before: number
  summary: string; explanation: string; phases: { period: number; items: IdpItem[] }[]
  later: { esco_id: string; skill: string; priority: number }[]; generator: string; disclaimer: string
}
export interface Idp { id: number; employee_id: number; target_role_id: number; version: number; status: string; plan: IdpPlan; generator: string; manager_comment: string; created_at: string; updated_at: string }
export interface SystemInfo { llm_enabled: boolean; llm_model: string | null; embedding_model: string; offline_embedding_model: string; alpha: number; lambda: number; tau: number; offline_tau: number; top_k: number; esco_version: string; demo?: boolean }
export interface ChatReply { answer: string; tool_calls: { name: string; args: Record<string, unknown> }[]; mode: string }
export interface Heatmap { skills: { esco_id: string; label: string }[]; rows: { employee_id: number; code: string; role: string; levels: number[]; target_coverage: number | null }[]; avg: number[] }
export interface AuditRow { id: number; actor: string; action: string; tool: string | null; employee_id: number | null; input_hash: string | null; detail: Record<string, unknown>; created_at: string }

let token: string | null = (() => { try { return localStorage.getItem('cq_token') } catch { return null } })()
export function setToken(t: string | null) {
  token = t
  try { if (t) localStorage.setItem('cq_token', t); else localStorage.removeItem('cq_token') } catch { /* ignore */ }
}
export const getToken = () => token

export class ApiError extends Error { constructor(public status: number, msg: string) { super(msg) } }

export async function api<T>(path: string, opts: { method?: string; body?: unknown; form?: FormData | URLSearchParams } = {}): Promise<T> {
  const method = opts.method || 'GET'
  if (DEMO) return demoRequest(path, method, opts.body ?? opts.form, token) as Promise<T>
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`
  let body: BodyInit | undefined
  if (opts.form) body = opts.form
  else if (opts.body !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(opts.body) }
  const r = await fetch(path, { method, headers, body })
  if (!r.ok) {
    let msg = r.statusText
    try { const j = await r.json(); msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail) } catch { /* ignore */ }
    throw new ApiError(r.status, msg)
  }
  const ct = r.headers.get('content-type') || ''
  return (ct.includes('application/json') ? r.json() : r.text()) as Promise<T>
}

export async function login(username: string, password: string): Promise<User> {
  const form = new URLSearchParams({ username, password })
  const res = await api<{ access_token: string; user: User }>('/api/auth/login', { method: 'POST', form })
  setToken(res.access_token)
  return res.user
}
