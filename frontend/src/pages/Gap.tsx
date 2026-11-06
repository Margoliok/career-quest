import { useEffect, useState } from 'react'
import { api, type Employee, type Gap, type Role } from '../api'
import { useAuth } from '../App'
import { Card, ErrorBox, Gauge, LevelDots, Loading, PageHead, RelBadge, useAsync } from '../components/ui'
import { Icon } from '../components/Icon'
import { roleTitle, useI18n } from '../i18n'

export function GapView({ eid, roleId }: { eid: number; roleId: number }) {
  const { t } = useI18n()
  const gap = useAsync(() => api<Gap>(`/api/profiles/${eid}/gap?role=${roleId}`), [eid, roleId])
  const [showAll, setShowAll] = useState(false)
  if (gap.loading && !gap.data) return <Loading />
  if (gap.error) return <ErrorBox msg={gap.error} />
  const g = gap.data!
  const maxP = Math.max(1, ...g.missing.map((m) => m.priority))
  const list = showAll ? g.missing : g.missing.slice(0, 15)
  return (
    <div className="stack reveal">
      <div className="grid g3">
        <div className="card row" style={{ justifyContent: 'center', padding: 24 }}><Gauge value={g.coverage} label="C(e, r)" /></div>
        <div className="card stack" style={{ gap: 6 }}>
          <h3>{t('coverage')}</h3>
          <span className="formula">C(e,r) = Σ w<sub>s</sub>·min(l<sub>e,s</sub>/l<sub>r,s</sub>, 1) / Σ w<sub>s</sub></span>
          <span className="formula">p<sub>s</sub> = w<sub>s</sub>·max(l<sub>r,s</sub> − l<sub>e,s</sub>, 0)</span>
        </div>
        <div className="card kpi stack" style={{ gap: 10 }}>
          <div><div className="l"><Icon name="check" size={15} />{t('matchedSkills')}</div><div className="v num" style={{ color: 'var(--ok)' }}>{g.matched.length}</div></div>
          <div><div className="l"><Icon name="target" size={15} />{t('missingSkills')}</div><div className="v num" style={{ color: 'var(--gold)' }}>{g.missing.length}</div></div>
        </div>
      </div>
      <Card title={t('missingSkills')} icon="target">
        <div className="table-wrap"><table>
          <thead><tr><th>{t('skill')}</th><th /><th>{t('yours')} → {t('required')}</th><th>{t('weight')}</th><th style={{ width: 200 }}>{t('priority')}</th></tr></thead>
          <tbody>{list.map((m) => (
            <tr key={m.esco_id}>
              <td><b>{m.label}</b></td><td><RelBadge rel={m.relation} /></td>
              <td style={{ whiteSpace: 'nowrap' }}><LevelDots level={m.employee_level} required={m.required_level} /> <span className="small muted">{m.employee_level} → {m.required_level}</span></td>
              <td>{m.weight}</td>
              <td><div className="row" style={{ gap: 8 }}><div className="bar" style={{ flex: 1 }}><span style={{ width: `${(m.priority / maxP) * 100}%`, background: 'linear-gradient(90deg, var(--gold-fill), #f2c66d)' }} /></div><b className="num">{m.priority}</b></div></td>
            </tr>))}
          </tbody>
        </table></div>
        {g.missing.length > 15 && <button className="btn sm" style={{ marginTop: 10 }} onClick={() => setShowAll(!showAll)}>{showAll ? '−' : `+${g.missing.length - 15}`}</button>}
      </Card>
      {g.matched.length > 0 && <Card title={t('matchedSkills')} icon="check">
        <div className="chips">{g.matched.map((m) => <span key={m.esco_id} className="badge ok"><Icon name="check" size={13} />{m.label} · {m.employee_level}/{m.required_level}</span>)}</div>
      </Card>}
    </div>
  )
}

export default function GapPage() {
  const { user } = useAuth()
  const { t, lang } = useI18n()
  const eid = user!.employee_id!
  const prof = useAsync(() => api<Employee>(`/api/profiles/${eid}`), [eid])
  const roles = useAsync(() => api<Role[]>('/api/roles'), [])
  const [roleId, setRoleId] = useState<number | null>(null)
  useEffect(() => { if (prof.data && roleId === null) setRoleId(prof.data.target_role?.id ?? roles.data?.[0]?.id ?? null) }, [prof.data, roles.data, roleId])
  const setTarget = async () => { if (roleId) { await api(`/api/profiles/${eid}/target-role`, { method: 'PUT', body: { role_id: roleId } }); prof.reload() } }
  if (!prof.data || !roles.data) return <Loading />
  const role = roles.data.find((r) => r.id === roleId)
  return (
    <div className="stack reveal">
      <PageHead eyebrow="C(e, r) · p_s" title={t('navGap')} sub={lang === 'kk' ? 'Мақсатты рөлдің талаптарымен салыстыру: міндетті дағдылардың салмағы жоғары, басымдық p_s дамыту ретін анықтайды.' : 'Сравнение с требованиями целевой роли: обязательные навыки весят больше, приоритет p_s задаёт порядок развития.'} />
      <div className="card row">
        <span className="small muted" style={{ fontWeight: 600 }}>{t('chooseRole')}</span>
        <select value={roleId ?? ''} onChange={(e) => setRoleId(+e.target.value)}>
          {roles.data.map((r) => <option key={r.id} value={r.id}>{roleTitle(r, lang)}{r.id === prof.data!.current_role?.id ? ' ●' : ''}</option>)}
        </select>
        {roleId !== prof.data.target_role?.id && <button className="btn primary" onClick={setTarget}>{t('setAsTarget')}</button>}
        {roleId === prof.data.target_role?.id && <span className="badge ok"><Icon name="target" size={13} />{t('targetRole')}</span>}
        <div className="spacer" />
        {role && <span className="small muted">{t('esco')}: <a href={role.esco_occupation_id} target="_blank" rel="noreferrer">{role.esco_occupation_label}</a></span>}
      </div>
      {role && <div className="small muted">{lang === 'kk' ? role.description_kk : role.description_ru}</div>}
      {roleId && <GapView eid={eid} roleId={roleId} />}
    </div>
  )
}
