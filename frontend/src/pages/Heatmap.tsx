import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, DEMO, getToken, type Heatmap } from '../api'
import { useAuth } from '../App'
import { Card, ErrorBox, Loading, PageHead, pct, useAsync } from '../components/ui'
import { Icon } from '../components/Icon'
import { demoExportCsv } from '../demo'
import { useI18n } from '../i18n'

const COLORS = ['transparent', '#d9e6f5', '#93b8e3', '#4a80c6', '#1b467f']

export function HeatTable({ hm }: { hm: Heatmap }) {
  const { t } = useI18n()
  return (
    <div className="table-wrap heat"><table>
      <thead><tr><th>{t('code')}</th><th>C</th>{hm.skills.map((s) => <th key={s.esco_id} className="v" title={s.label}>{s.label.length > 28 ? s.label.slice(0, 27) + '…' : s.label}</th>)}</tr></thead>
      <tbody>
        {hm.rows.map((r) => (
          <tr key={r.employee_id}>
            <td style={{ whiteSpace: 'nowrap' }}><Link to={`/team/${r.employee_id}`}><b>{r.code}</b></Link> <span className="small muted">{r.role}</span></td>
            <td className="small num">{pct(r.target_coverage)}</td>
            {r.levels.map((l, i) => <td key={i} className="c" style={{ background: COLORS[l], color: l >= 3 ? '#fff' : 'var(--text)' }}>{l || ''}</td>)}
          </tr>))}
        <tr style={{ background: 'var(--surface-2)' }}><td><b>{t('avg')}</b></td><td />{hm.avg.map((a, i) => <td key={i} className="c">{a.toFixed(1)}</td>)}</tr>
      </tbody>
    </table></div>
  )
}

export default function HeatmapPage() {
  const { user } = useAuth()
  const { t, lang } = useI18n()
  const depts = useAsync(() => api<{ id: number; name_kk: string; name_ru: string }[]>('/api/hr/departments'), [])
  const [dept, setDept] = useState<number | ''>(user?.role === 'manager' ? user.department_id ?? '' : '')
  const hm = useAsync(() => api<Heatmap>(`/api/hr/heatmap${dept ? `?department_id=${dept}` : ''}`), [dept])
  const exportCsv = async () => {
    let csv: string
    if (DEMO) csv = demoExportCsv()
    else { const r = await fetch('/api/hr/export.csv', { headers: { Authorization: `Bearer ${getToken()}` } }); csv = await r.text() }
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' })); a.download = 'career_quest_skills.csv'; a.click()
  }
  return (
    <div className="stack reveal">
      <PageHead eyebrow={lang === 'kk' ? 'Бөлімнің жиынтық бейнесі' : 'Сводная картина отдела'} title={t('navHeatmap')} actions={<>
        {user?.role === 'hr' && <select value={dept} onChange={(e) => setDept(e.target.value ? +e.target.value : '')}>
          <option value="">{t('allDepartments')}</option>
          {depts.data?.map((d) => <option key={d.id} value={d.id}>{lang === 'kk' ? d.name_kk : d.name_ru}</option>)}
        </select>}
        {user?.role === 'hr' && <button className="btn" onClick={exportCsv}><Icon name="download" />{t('export')}</button>}
      </>} />
      <div className="row small muted">{[1, 2, 3, 4].map((l) => <span key={l} className="legend"><i style={{ background: COLORS[l] }} />{t(`lvl${l}` as 'lvl1')}</span>)}</div>
      <ErrorBox msg={hm.error} />
      <Card>{hm.data ? <HeatTable hm={hm.data} /> : <Loading />}</Card>
    </div>
  )
}
