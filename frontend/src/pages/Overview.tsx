import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type Employee, type Role } from '../api'
import { Card, Kpi, Loading, PageHead, pct, useAsync } from '../components/ui'
import { roleTitle, useI18n } from '../i18n'

export default function OverviewPage() {
  const { t, lang } = useI18n()
  const emps = useAsync(() => api<Employee[]>('/api/employees'), [])
  const roles = useAsync(() => api<Role[]>('/api/roles'), [])
  if (!emps.data || !roles.data) return <Loading />
  const E = emps.data
  const skills = E.reduce((a, e) => a + (e.skills || 0), 0)
  const conf = E.reduce((a, e) => a + (e.confirmed || 0), 0)
  const covs = E.map((e) => e.target_coverage).filter((x): x is number => typeof x === 'number')
  const avg = covs.reduce((a, b) => a + b, 0) / Math.max(covs.length, 1)
  const bins = Array.from({ length: 10 }, (_, i) => ({ bin: `${i * 10}–${i * 10 + 10}%`, n: 0 }))
  covs.forEach((c) => { bins[Math.min(9, Math.floor(c * 10))].n++ })
  const byRole = roles.data.map((r) => ({ role: r.code, n: E.filter((e) => e.current_role?.id === r.id).length,
    target: E.filter((e) => e.target_role?.id === r.id).length }))
  const idp: Record<string, number> = {}
  E.forEach((e) => { const s = e.idp_status || 'none'; idp[s] = (idp[s] || 0) + 1 })
  return (
    <div className="stack reveal">
      <PageHead eyebrow="HR / L&D" title={t('navOverview')} sub={lang === 'kk' ? 'Ұйымның дағдылар жағдайы, мақсатты рөлдерді қамту және ЖДЖ процесі.' : 'Состояние навыков организации, покрытие целевых ролей и процесс ИПР.'} />
      <div className="grid g4">
        <Kpi icon="users" label={t('kpiEmployees')} value={<span className="num">{E.length}</span>} />
        <Kpi icon="layers" label={t('kpiSkills')} value={<span className="num">{skills}</span>} hint={`≈ ${(skills / Math.max(E.length, 1)).toFixed(1)} / ${t('roleEmployee').toLowerCase()}`} />
        <Kpi icon="check" label={t('kpiConfirmed')} value={<span className="num">{conf}</span>} hint={pct(conf / Math.max(skills, 1))} />
        <Kpi icon="compass" label={t('kpiCoverage')} value={<span className="num">{pct(avg)}</span>} />
      </div>
      <div className="grid g2">
        <Card title={t('coverageDist')} icon="chart">
          <ResponsiveContainer width="100%" height={240}><BarChart data={bins}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} /><XAxis dataKey="bin" fontSize={11} stroke="var(--muted)" /><YAxis allowDecimals={false} stroke="var(--muted)" /><Tooltip cursor={{ fill: 'var(--surface-2)' }} /><Bar dataKey="n" fill="#2a68bb" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer>
        </Card>
        <Card title={`${t('currentRole')} / ${t('targetRole')}`} icon="flag">
          <ResponsiveContainer width="100%" height={240}><BarChart data={byRole}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} /><XAxis dataKey="role" stroke="var(--muted)" /><YAxis allowDecimals={false} stroke="var(--muted)" /><Tooltip cursor={{ fill: 'var(--surface-2)' }} />
            <Bar dataKey="n" name={t('currentRole')} fill="#2a68bb" radius={[6, 6, 0, 0]} /><Bar dataKey="target" name={t('targetRole')} fill="#e3a127" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer>
        </Card>
      </div>
      <Card title={t('navRoles')} icon="puzzle">
        <div className="table-wrap"><table><thead><tr><th>{t('code')}</th><th>{t('title')}</th><th>{t('esco')}</th><th>{t('skills')}</th></tr></thead>
          <tbody>{roles.data.map((r) => <tr key={r.id}><td><b>{r.code}</b></td><td>{roleTitle(r, lang)}</td><td className="small">{r.esco_occupation_label}</td><td>{r.skills_count}</td></tr>)}</tbody></table></div>
        <div className="small muted" style={{ marginTop: 8 }}>{t('idp')}: {Object.entries(idp).map(([k, v]) => `${k} — ${v}`).join(' · ')}</div>
      </Card>
    </div>
  )
}
