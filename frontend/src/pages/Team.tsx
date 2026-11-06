import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Employee } from '../api'
import { Card, ErrorBox, IdpBadge, Loading, PageHead, pct, useAsync } from '../components/ui'
import { Icon } from '../components/Icon'
import { useI18n } from '../i18n'

export default function TeamPage() {
  const { t, lang } = useI18n()
  const nav = useNavigate()
  const list = useAsync(() => api<Employee[]>('/api/employees'), [])
  const [q, setQ] = useState('')
  if (list.error) return <ErrorBox msg={list.error} />
  if (!list.data) return <Loading />
  const rows = list.data.filter((e) => !q || `${e.code} ${e.current_role?.code} ${e.target_role?.code}`.toLowerCase().includes(q.toLowerCase()))
  const pending = list.data.filter((e) => e.idp_status === 'submitted').length
  return (
    <div className="stack reveal">
      <PageHead eyebrow={`${list.data.length} ${t('employees').toLowerCase()}`} title={t('navTeam')}
        badge={pending > 0 ? <span className="badge warn"><span className="d" />{t('idpSubmitted')}: {pending}</span> : undefined}
        actions={<label className="row" style={{ gap: 6, position: 'relative' }}><Icon name="search" className="muted" />
          <input placeholder={t('search')} value={q} onChange={(e) => setQ(e.target.value)} aria-label={t('search')} /></label>} />
      <Card>
        <div className="table-wrap"><table>
          <thead><tr><th>{t('code')}</th><th>{t('department')}</th><th>{t('currentRole')}</th><th>{t('targetRole')}</th><th>{t('coverage')}</th><th>{t('skills')}</th><th>{t('confirmed')}</th><th>{t('idp')}</th><th /></tr></thead>
          <tbody>{rows.map((e) => (
            <tr key={e.id} className="click" onClick={() => nav(`/team/${e.id}`)}>
              <td><b>{e.code}</b></td>
              <td className="small">{lang === 'kk' ? e.department_kk : e.department_ru}</td>
              <td>{e.current_role?.code}</td><td>{e.target_role?.code || '—'}</td>
              <td style={{ minWidth: 120 }}><div className="row" style={{ gap: 6 }}><div className="bar" style={{ flex: 1 }}><span style={{ width: pct(e.target_coverage) }} /></div><span className="small num">{pct(e.target_coverage)}</span></div></td>
              <td>{e.skills}</td><td>{e.confirmed}</td><td><IdpBadge status={e.idp_status} /></td>
              <td><button className="btn sm">{t('open')}<Icon name="next" size={14} /></button></td>
            </tr>))}
          </tbody>
        </table></div>
      </Card>
    </div>
  )
}
