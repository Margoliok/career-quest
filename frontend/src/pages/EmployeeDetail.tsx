import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type EmpSkill, type Employee, type Idp } from '../api'
import { useAuth } from '../App'
import { SkillsTable } from '../components/SkillsTable'
import { Card, Empty, ErrorBox, IdpBadge, Loading, PageHead, Tabs, useAsync } from '../components/ui'
import { Icon } from '../components/Icon'
import { roleTitle, useI18n } from '../i18n'
import { GapView } from './Gap'
import { IdpView } from './Idp'
import { RecList } from './Career'

export default function EmployeeDetail() {
  const { id } = useParams()
  const eid = +(id || 0)
  const { user } = useAuth()
  const { t, lang } = useI18n()
  const prof = useAsync(() => api<Employee>(`/api/profiles/${eid}`), [eid])
  const skills = useAsync(() => api<EmpSkill[]>(`/api/profiles/${eid}/skills`), [eid])
  const idps = useAsync(() => api<Idp[]>(`/api/idp?employee_id=${eid}`), [eid])
  const [tab, setTab] = useState<'skills' | 'gap' | 'career' | 'idp'>('skills')
  const [comment, setComment] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [gapKey, setGapKey] = useState(0)
  const isManager = user?.role === 'manager'
  const patch = async (esco_id: string, p: { level?: number; status?: string }) => {
    try { await api(`/api/profiles/${eid}/skills`, { method: 'PATCH', body: { esco_id, ...p } }); skills.reload(); setGapKey((k) => k + 1) }
    catch (e) { setErr((e as Error).message) }
  }
  const decide = async (idpId: number, decision: 'approved' | 'returned') => {
    try { await api(`/api/idp/${idpId}/approve`, { method: 'PATCH', body: { decision, comment } }); setComment(''); idps.reload() }
    catch (e) { setErr((e as Error).message) }
  }
  if (prof.error) return <ErrorBox msg={prof.error} />
  if (!prof.data) return <Loading />
  const e = prof.data
  // басшыға алдымен келісуге жіберілген нұсқа көрсетіледі
  const latest = idps.data?.find((i) => i.status === 'submitted') || idps.data?.[0]
  return (
    <div className="stack reveal">
      <Link to="/team" className="row small" style={{ gap: 4, textDecoration: 'none' }}><Icon name="back" size={16} />{t('back').replace('← ', '')}</Link>
      <PageHead eyebrow={lang === 'kk' ? e.department_kk : e.department_ru} title={e.code}
        badge={<>{latest && <IdpBadge status={latest.status} />}</>}
        sub={<span className="row" style={{ gap: 8 }}><span className="badge"><Icon name="flag" size={13} />{roleTitle(e.current_role, lang)}</span><Icon name="next" size={14} /><span className="badge info"><Icon name="target" size={13} />{roleTitle(e.target_role, lang)}</span></span>} />
      <ErrorBox msg={err} />
      <Tabs value={tab} onChange={setTab} items={[
        { id: 'skills', label: t('skillMap'), icon: 'layers' }, { id: 'gap', label: t('navGap'), icon: 'target' },
        { id: 'career', label: t('navCareer'), icon: 'compass' }, { id: 'idp', label: t('navIdp'), icon: 'calendar' }]} />
      {tab === 'skills' && <Card title={t('skillMap')} icon="layers">{skills.data ? <SkillsTable skills={skills.data} mode={isManager ? 'manager' : 'readonly'} onPatch={patch} /> : <Loading />}</Card>}
      {tab === 'gap' && (e.target_role ? <GapView key={gapKey} eid={eid} roleId={e.target_role.id} /> : <Empty icon="target" text={t('chooseRole')} />)}
      {tab === 'career' && <RecList eid={eid} current={roleTitle(e.current_role, lang)} />}
      {tab === 'idp' && (latest ? <div className="stack">
        {isManager && latest.status === 'submitted' && <div className="card row" style={{ borderColor: 'color-mix(in srgb, var(--gold-fill) 55%, var(--border))', background: 'var(--gold-soft)' }}>
          <Icon name="mail" /><b>{t('idpSubmitted')}</b>
          <input style={{ flex: 1, minWidth: 220 }} placeholder={t('commentPh')} value={comment} onChange={(ev) => setComment(ev.target.value)} aria-label={t('commentPh')} />
          <button className="btn ok" onClick={() => decide(latest.id, 'approved')}><Icon name="check" />{t('approve')}</button>
          <button className="btn danger" onClick={() => decide(latest.id, 'returned')}><Icon name="back" />{t('returnIdp')}</button>
        </div>}
        <IdpView idp={latest} />
      </div> : <div className="card"><Empty icon="calendar" text={t('noData')} /></div>)}
    </div>
  )
}
