import { useState } from 'react'
import { api, type Employee, type Idp } from '../api'
import { useAuth } from '../App'
import { Card, Empty, ErrorBox, IdpBadge, LevelDots, Loading, PageHead, RelBadge, pct, useAsync } from '../components/ui'
import { Icon } from '../components/Icon'
import { roleTitle, useI18n } from '../i18n'

export function IdpView({ idp }: { idp: Idp }) {
  const { t, lang } = useI18n()
  const p = idp.plan
  return (
    <div className="stack reveal">
      <div className="card stack" style={{ gap: 10 }}>
        <div className="row">
          <h2>{t('idpTitle')}</h2><div className="spacer" />
          <IdpBadge status={idp.status} /><span className="badge">{t('version')} {idp.version}</span>
          <span className="badge sky"><Icon name="sparkles" size={13} />{p.generator === 'llm' ? 'LLM + RAG' : 'offline'}</span>
        </div>
        <div className="row" style={{ gap: 8 }}><span className="badge info"><Icon name="target" size={13} />{roleTitle(p.target_role, lang)}</span><span className="badge num">C(e,r) = {pct(p.coverage_before)}</span></div>
        <div>{p.summary}</div>
        <div className="small"><b>{t('explanation')}:</b> {p.explanation}</div>
        {idp.manager_comment && <div className="notice"><Icon name="chat" /><span><b>{t('managerComment')}:</b> {idp.manager_comment}</span></div>}
      </div>
      <div className="timeline">
        {p.phases.map((ph) => (
          <div className="phase" key={ph.period}>
            <div className="phase-head"><span className="phase-num">{ph.period}<small>{t('days')}</small></span><div className="spacer" /><span className="badge">{ph.items.length}</span></div>
            {ph.items.map((it) => (
              <div className="phase-item" key={it.esco_id}>
                <div className="row" style={{ gap: 6 }}><b>{it.skill}</b><RelBadge rel={it.relation} /></div>
                <div className="row small muted" style={{ gap: 6 }}><LevelDots level={it.from_level} required={it.to_level} />{it.from_level} → {it.to_level} · p<sub>s</sub> = {it.priority}</div>
                {it.skill_description && <div className="small muted">{it.skill_description.slice(0, 140)}{it.skill_description.length > 140 ? '…' : ''}</div>}
                <div className="lbl"><Icon name="book" size={13} />{t('courses')}</div>
                {it.courses.length ? it.courses.map((c) => (
                  <div className="course" key={c.id}><Icon name={c.url ? 'external' : 'users'} size={14} />
                    <span>{c.url ? <a href={c.url} target="_blank" rel="noreferrer">{c.title}</a> : <span>{c.title}</span>}
                      <div className="meta">{c.provider} · {c.lang.toUpperCase()}{c.is_free ? ` · ${t('free').toLowerCase()}` : ''}</div></span></div>
                )) : <div className="small muted">{t('noCourse')}</div>}
                <div className="lbl"><Icon name="tool" size={13} />{t('practice')}</div><div className="small">{it.practice}</div>
                <div className="lbl"><Icon name="check" size={13} />{t('success')}</div><div className="small">{it.success_criteria}</div>
              </div>
            ))}
          </div>
        ))}
      </div>
      {p.later.length > 0 && <Card title={t('later')} icon="flag"><div className="chips">{p.later.map((l) => <span key={l.esco_id} className="badge">{l.skill} · p={l.priority}</span>)}</div></Card>}
      <div className="notice"><Icon name="scale" />{p.disclaimer}</div>
    </div>
  )
}

export default function IdpPage() {
  const { user } = useAuth()
  const { t, lang } = useI18n()
  const eid = user!.employee_id!
  const prof = useAsync(() => api<Employee>(`/api/profiles/${eid}`), [eid])
  const list = useAsync(() => api<Idp[]>(`/api/idp?employee_id=${eid}`), [eid])
  const [sel, setSel] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const gen = async () => {
    setBusy(true); setErr(null)
    try { const i = await api<Idp>('/api/idp', { method: 'POST', body: { employee_id: eid, lang } }); await list.reload(); setSel(i.id) }
    catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const submit = async (id: number) => { await api(`/api/idp/${id}/submit`, { method: 'POST' }); list.reload() }
  if (!list.data || !prof.data) return <Loading />
  const cur = list.data.find((i) => i.id === sel) || list.data.find((i) => i.plan.lang === lang) || list.data[0]
  return (
    <div className="stack reveal">
      <PageHead eyebrow="30 / 60 / 90" title={t('navIdp')} sub={`${t('targetRole')}: ${roleTitle(prof.data.target_role, lang)}`}
        actions={<button className="btn gold" onClick={gen} disabled={busy || !prof.data.target_role}>{busy ? <span className="spin" /> : <Icon name="sparkles" />}{t('generateIdp')} · {lang.toUpperCase()}</button>} />
      <ErrorBox msg={err} />
      {list.data.length > 1 && <div className="chips">{list.data.map((i) => (
        <button key={i.id} className={`chip ${i.id === cur?.id ? 'on' : ''}`} onClick={() => setSel(i.id)}>
          v{i.version} · {i.plan.lang.toUpperCase()} · {t(i.status === 'approved' ? 'idpApproved' : i.status === 'submitted' ? 'idpSubmitted' : i.status === 'returned' ? 'idpReturned' : 'idpDraft')}</button>))}</div>}
      {cur ? <>
        {(cur.status === 'draft' || cur.status === 'returned') && <div className="card row" style={{ borderColor: 'color-mix(in srgb, var(--ok) 35%, var(--border))' }}>
          <Icon name="mail" /><span>{t('idpDraft')} · {t('version')} {cur.version}</span><div className="spacer" />
          <button className="btn ok" onClick={() => submit(cur.id)}><Icon name="send" />{t('sendToManager')}</button></div>}
        <IdpView idp={cur} />
      </> : <div className="card"><Empty icon="calendar" text={t('noData')} /></div>}
    </div>
  )
}
