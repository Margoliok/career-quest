// GitHub Pages үшін статикалық демо: нақты backend-тен экспортталған snapshot.json + браузердегі есептеулер.
// Формулалар backend-тегімен бірдей: (2) C(e,r), (3) p_s, (4) P̂(r′|r), (5) гибридті балл.
/* eslint-disable @typescript-eslint/no-explicit-any */

type Any = any
let snap: Any = null
let loading: Promise<Any> | null = null
let idpSeq = 1000
let auditSeq = 100000

async function load(): Promise<Any> {
  if (snap) return snap
  if (!loading) loading = fetch(`${import.meta.env.BASE_URL}demo/snapshot.json`).then((r) => r.json()).then((j) => { snap = j; return j })
  return loading
}

function err(status: number, msg: string): never { const e: Any = new Error(msg); e.status = status; throw e }

function userByToken(token: string | null) {
  const u = snap.users.find((x: Any) => x.username === token)
  if (!u) err(401, 'Invalid token')
  return u
}

function canView(u: Any, e: Any) {
  if (u.role === 'hr') return true
  if (u.role === 'manager') return u.department_id === e.department_id
  return u.employee_id === e.id
}

function emp(u: Any, id: number) {
  const e = snap.employees.find((x: Any) => x.id === id)
  if (!e) err(404, 'Employee not found')
  if (!canView(u, e)) err(403, 'No access to this employee')
  return e
}

function logAudit(actor: string, action: string, tool: string | null, employee_id: number | null, detail: Any = {}) {
  snap.audit.unshift({ id: auditSeq++, actor, action, tool, employee_id, input_hash: null, detail: { ...detail, demo: true }, created_at: new Date().toISOString() })
}

function levels(eid: number): Record<string, number> {
  const out: Record<string, number> = {}
  for (const s of snap.skills[eid] || []) if (s.status === 'auto' || s.status === 'confirmed') out[s.esco_id] = s.level
  return out
}

function role(id: number) { return snap.roles.find((r: Any) => r.id === id) }

export function computeGap(lv: Record<string, number>, reqs: Any[], imp: Record<string, number>) {
  const total = reqs.reduce((a, r) => a + r.weight, 0)
  let acc = 0
  const matched: Any[] = []; const missing: Any[] = []
  for (const r of reqs) {
    const le = lv[r.esco_id] || 0
    acc += r.weight * Math.min(le / Math.max(r.required_level, 1), 1)
    const item = { esco_id: r.esco_id, label: r.label, weight: r.weight, required_level: r.required_level, employee_level: le,
      priority: r.weight * Math.max(r.required_level - le, 0), relation: r.relation }
    ;(item.priority > 0 ? missing : matched).push(item)
  }
  const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0)
  missing.sort((a, b) => b.priority - a.priority || b.weight - a.weight || (imp[b.esco_id] || 0) - (imp[a.esco_id] || 0) || cmp(a.label, b.label))
  return { coverage: total > 0 ? acc / total : 0, total_weight: total, matched, missing }
}

function gapFor(eid: number, rid: number) { return computeGap(levels(eid), role(rid).requirements, snap.importance) }

function recommendations(e: Any, alpha: number, top: number) {
  const lam = snap.system.lambda
  const cur = e.current_role?.id
  const cands = snap.roles.map((r: Any) => r.id).filter((id: number) => id !== cur)
  const counts: Record<number, number> = {}
  for (const t of snap.transitions) if (t.from === cur) counts[t.to] = t.count
  const nR = cands.reduce((a: number, c: number) => a + (counts[c] || 0), 0)
  const denom = nR + lam * cands.length
  const p: Record<number, number> = {}
  for (const c of cands) p[c] = (( counts[c] || 0) + lam) / denom
  const pmax = Math.max(...cands.map((c: number) => p[c])) || 1
  const lv = levels(e.id)
  const rows = cands.map((c: number) => {
    const g = computeGap(lv, role(c).requirements, snap.importance)
    const pn = p[c] / pmax
    const a = alpha * pn, s = (1 - alpha) * g.coverage
    const r = role(c)
    return { role_id: c, code: r.code, title_kk: r.title_kk, title_ru: r.title_ru, score: a + s, p_transition: p[c], p_normalized: pn,
      coverage: g.coverage, alpha_part: a, skill_part: s, transition_count: counts[c] || 0,
      top_missing: g.missing.slice(0, 5).map((m: Any) => ({ esco_id: m.esco_id, label: m.label, priority: m.priority })) }
  })
  rows.sort((x: Any, y: Any) => y.score - x.score || (String(x.role_id) < String(y.role_id) ? -1 : 1))
  return rows.slice(0, top)
}

function heatmap(u: Any, deptId: number | null, top = 20) {
  if (u.role === 'manager') deptId = u.department_id
  const emps = snap.employees.filter((e: Any) => !deptId || e.department_id === deptId)
  const roleIds = new Set<number>()
  emps.forEach((e: Any) => { if (e.current_role) roleIds.add(e.current_role.id); if (e.target_role) roleIds.add(e.target_role.id) })
  const roleW: Record<string, number> = {}
  const labels: Record<string, string> = {}
  for (const r of snap.roles) if (roleIds.has(r.id)) for (const q of r.requirements) { roleW[q.esco_id] = (roleW[q.esco_id] || 0) + q.weight; labels[q.esco_id] = q.label }
  const holders: Record<string, number> = {}
  for (const e of emps) for (const s of snap.skills[e.id] || []) if (s.status === 'auto' || s.status === 'confirmed') { holders[s.esco_id] = (holders[s.esco_id] || 0) + 1; labels[s.esco_id] = s.label }
  const ids = Array.from(new Set([...Object.keys(holders), ...Object.keys(roleW)]))
  ids.sort((a, b) => (holders[b] || 0) - (holders[a] || 0) || (roleW[b] || 0) - (roleW[a] || 0) || (a < b ? -1 : 1))
  const skills = ids.slice(0, top)
  const rows = emps.map((e: Any) => {
    const lv = levels(e.id)
    return { employee_id: e.id, code: e.code, role: e.current_role?.code, levels: skills.map((s) => lv[s] || 0),
      target_coverage: e.target_role ? Math.round(gapFor(e.id, e.target_role.id).coverage * 1000) / 1000 : null }
  })
  const avg = skills.map((_, i) => Math.round((rows.reduce((a: number, r: Any) => a + r.levels[i], 0) / Math.max(rows.length, 1)) * 100) / 100)
  return { skills: skills.map((s) => ({ esco_id: s, label: labels[s] })), rows, avg }
}

function chatAnswer(e: Any, message: string, lang: string) {
  const forb = /жалақ|зарплат|оклад|сыйақы|преми|бонус|жұмыстан шығар|уволь|сокращ|қысқарт|жұмысқа ал|найм|salary|fire|hire/i
  if (forb.test(message)) return { answer: snap.chat.refusal[lang] || snap.chat.refusal.kk, tool_calls: [], mode: 'guardrail' }
  const qa = (snap.chat.qa[e.id]?.[lang] || snap.chat.qa[e.id]?.kk || []) as Any[]
  const norm = (s: string) => s.toLowerCase().replace(/[^\p{L}\p{N} ]/gu, '')
  const exact = qa.find((x) => norm(x.q) === norm(message))
  if (exact) return exact.a
  const low = message.toLowerCase()
  const pick = (re: RegExp) => qa.find((x) => re.test(x.q.toLowerCase()))
  const byIntent = /неге|почему|ұсынылд|рекоменд/.test(low) ? pick(/неге|почему/)
    : /жоспар|план|ждж|ипр/.test(low) ? pick(/жоспар|план/)
    : /курс|оқу|обуч/.test(low) ? pick(/курс/)
    : /жетіспей|не хватает|алшақ|разрыв/.test(low) ? pick(/жетіспей|не хватает/) : null
  if (byIntent) return byIntent.a
  return { answer: snap.chat.fallback[lang] || snap.chat.fallback.kk, tool_calls: [], mode: 'offline' }
}

function q(path: string) {
  const [p, qs] = path.split('?')
  return { p, params: new URLSearchParams(qs || '') }
}

export async function demoRequest(path: string, method: string, body: Any, token: string | null): Promise<Any> {
  await load()
  const { p, params } = q(path)
  let m: RegExpMatchArray | null
  if (p === '/api/auth/login') {
    const f = body as URLSearchParams
    const u = snap.users.find((x: Any) => x.username === f.get('username'))
    if (!u || f.get('password') !== 'demo123') err(401, 'Логин немесе құпиясөз қате / Неверный логин или пароль')
    logAudit(u.username, 'login', null, null)
    return { access_token: u.username, token_type: 'bearer', user: u }
  }
  const u = userByToken(token)
  if (p === '/api/auth/me') return u
  if (p === '/api/system') return { ...snap.system, demo: true }
  if (p === '/api/roles') return snap.roles.map((r: Any) => ({ ...r, requirements: undefined, skills_count: r.requirements.length }))
  if ((m = p.match(/^\/api\/roles\/(\d+)$/))) return role(+m[1])
  if (p === '/api/transitions') return snap.transitions
  if (p === '/api/skills/search') {
    const s = (params.get('q') || '').toLowerCase()
    return snap.catalog.filter((x: Any) => x.label.toLowerCase().includes(s)).slice(0, 10).map((x: Any) => ({ ...x, matched_label: x.label, similarity: 1 }))
  }
  if (p === '/api/employees') {
    const list = snap.employees.filter((e: Any) => canView(u, e))
    return list.map((e: Any) => {
      const sk = snap.skills[e.id] || []
      const idps = snap.idp_list.filter((i: Any) => i.employee_id === e.id).sort((a: Any, b: Any) => a.version - b.version)
      return { ...e, latest_text: undefined, skills: sk.length, confirmed: sk.filter((s: Any) => s.status === 'confirmed').length,
        idp_status: idps.length ? idps[idps.length - 1].status : null,
        target_coverage: e.target_role ? Math.round(gapFor(e.id, e.target_role.id).coverage * 10000) / 10000 : undefined }
    })
  }
  if ((m = p.match(/^\/api\/profiles\/(\d+)$/))) return emp(u, +m[1])
  if ((m = p.match(/^\/api\/profiles\/(\d+)\/analyze$/))) {
    const e = emp(u, +m[1])
    logAudit(u.username, 'analyze_profile', 'extract_skills', e.id, { method: 'demo' })
    return { ...(snap.analysis[e.id] || { found: (snap.skills[e.id] || []).length, added: 0, updated: 0, kept: 0, lang: 'kk' }), method: 'demo' }
  }
  if ((m = p.match(/^\/api\/profiles\/(\d+)\/skills$/))) {
    const e = emp(u, +m[1])
    if (method === 'GET') return [...(snap.skills[e.id] || [])].sort((a: Any, b: Any) => b.level - a.level || (a.label < b.label ? -1 : 1))
    const row = (snap.skills[e.id] || []).find((s: Any) => s.esco_id === body.esco_id)
    if (!row) err(404, 'skill not found')
    if (u.role === 'manager') {
      if (body.level) row.level = body.level
      if (body.status === 'confirmed' || body.status === 'rejected') row.status = body.status
    } else if (u.role === 'employee') {
      if (body.status) err(403, 'Дағдыны тек басшы растай алады / Подтверждать навык может только руководитель')
      if (body.level) { row.level = body.level; row.source = 'self'; if (row.status === 'confirmed') row.status = 'auto' }
    } else err(403, 'HR cannot edit individual skills')
    logAudit(u.username, 'edit_skill', null, e.id, body)
    return { ok: true, level: row.level, status: row.status }
  }
  if ((m = p.match(/^\/api\/profiles\/(\d+)\/target-role$/))) {
    const e = emp(u, +m[1])
    e.target_role = { ...role(body.role_id), requirements: undefined }
    logAudit(u.username, 'set_target_role', null, e.id, { role_id: body.role_id })
    return e
  }
  if ((m = p.match(/^\/api\/profiles\/(\d+)\/gap$/))) {
    const e = emp(u, +m[1])
    const rid = +(params.get('role') || e.target_role?.id || 0)
    if (!rid) err(400, 'Мақсатты рөл таңдалмаған / Целевая роль не выбрана')
    return { role_id: rid, ...gapFor(e.id, rid) }
  }
  if ((m = p.match(/^\/api\/profiles\/(\d+)\/recommendations$/))) {
    const e = emp(u, +m[1])
    const alpha = params.has('alpha') ? +params.get('alpha')! : snap.system.alpha
    return { alpha, current_role_id: e.current_role?.id, roles: recommendations(e, alpha, +(params.get('top') || 6)) }
  }
  if (p === '/api/idp' && method === 'GET') {
    const e = emp(u, +(params.get('employee_id') || 0))
    return snap.idp_list.filter((i: Any) => i.employee_id === e.id).sort((a: Any, b: Any) => b.version - a.version)
  }
  if (p === '/api/idp' && method === 'POST') {
    const e = emp(u, body.employee_id)
    const rid = body.role_id || e.target_role?.id
    const plan = snap.idps[e.id]?.[rid]?.[body.lang] || snap.idps[e.id]?.[rid]?.kk
    if (!plan) err(400, 'Демо: бұл рөл үшін ЖДЖ алдын ала есептелмеген / Демо: ИПР для этой роли не рассчитан')
    const ver = Math.max(0, ...snap.idp_list.filter((i: Any) => i.employee_id === e.id).map((i: Any) => i.version)) + 1
    const now = new Date().toISOString()
    const idp = { id: idpSeq++, employee_id: e.id, target_role_id: rid, version: ver, status: 'draft', plan, generator: plan.generator, manager_comment: '', created_at: now, updated_at: now }
    snap.idp_list.push(idp)
    logAudit(u.username, 'create_idp', 'save_idp', e.id, { version: ver })
    return idp
  }
  if ((m = p.match(/^\/api\/idp\/(\d+)(\/submit|\/approve)?$/))) {
    const idp = snap.idp_list.find((i: Any) => i.id === +m![1])
    if (!idp) err(404, 'IDP not found')
    emp(u, idp.employee_id)
    if (m[2] === '/submit') { idp.status = 'submitted'; logAudit(u.username, 'submit_idp', null, idp.employee_id); return idp }
    if (m[2] === '/approve') {
      if (u.role !== 'manager') err(403, 'Forbidden for this role')
      if (idp.status !== 'submitted') err(400, 'Тек жіберілген ЖДЖ келісіледі / Согласовать можно только отправленный ИПР')
      idp.status = body.decision; idp.manager_comment = body.comment || ''
      logAudit(u.username, `idp_${body.decision}`, null, idp.employee_id, { comment: body.comment })
      return idp
    }
    return idp
  }
  if (p === '/api/chat') {
    const e = emp(u, body.employee_id || u.employee_id)
    const a = chatAnswer(e, body.message, body.lang || 'kk')
    logAudit(u.username, a.mode === 'guardrail' ? 'chat_refused' : 'chat_answer', null, e.id, { mode: 'demo' })
    return a
  }
  if (p === '/api/hr/departments') return snap.departments
  if (p === '/api/hr/courses' && method === 'GET') return snap.courses
  if (p === '/api/hr/courses' && method === 'POST') {
    if (u.role !== 'hr') err(403, 'Forbidden')
    const c = { ...body, id: 9000 + snap.courses.length, skills: (body.esco_ids || []).map((x: string) => snap.catalog.find((s: Any) => s.esco_id === x)?.label || x) }
    snap.courses.push(c); logAudit(u.username, 'add_course', null, null, { title: body.title }); return c
  }
  if ((m = p.match(/^\/api\/hr\/courses\/(\d+)$/))) { snap.courses = snap.courses.filter((c: Any) => c.id !== +m![1]); return { ok: true } }
  if ((m = p.match(/^\/api\/hr\/roles\/(\d+)\/skills$/))) {
    if (u.role !== 'hr') err(403, 'Forbidden')
    const r = role(+m[1])
    r.requirements = body.map((it: Any) => ({ ...it, label: snap.catalog.find((s: Any) => s.esco_id === it.esco_id)?.label || it.esco_id }))
    logAudit(u.username, 'edit_role_profile', null, null, { role: r.code, skills: body.length })
    return { ok: true, skills: body.length }
  }
  if (p === '/api/hr/heatmap') { if (u.role === 'employee') err(403, 'Forbidden'); return heatmap(u, params.get('department_id') ? +params.get('department_id')! : null) }
  if (p === '/api/hr/audit') { if (u.role !== 'hr') err(403, 'Forbidden'); return snap.audit.slice(0, +(params.get('limit') || 100)) }
  err(404, `demo: ${method} ${p} is not available`)
}

export function demoExportCsv(): string {
  const lines = ['employee;current_role;target_role;esco_id;skill;level;status;source']
  for (const e of snap?.employees || []) for (const s of snap.skills[e.id] || [])
    lines.push([e.code, e.current_role?.code || '', e.target_role?.code || '', s.esco_id, s.label, s.level, s.status, s.source].join(';'))
  return '﻿' + lines.join('\n')
}
