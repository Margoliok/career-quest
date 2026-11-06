import { useEffect, useState } from 'react'
import { api, type Employee, type RoleRec } from '../api'
import { useAuth } from '../App'
import { Card, ErrorBox, Loading, PageHead, pct } from '../components/ui'
import { roleTitle, useI18n, type Lang } from '../i18n'

export function CareerGraph({ current, recs, lang }: { current: string; recs: RoleRec[]; lang: Lang }) {
  const W = 760, H = 70 + recs.length * 74
  const cx = 130, cy = H / 2
  const max = Math.max(...recs.map((r) => r.score), 0.0001)
  const wrap = (s: string, n = 26) => {
    const words = s.split(' '); const lines: string[] = []; let cur = ''
    for (const w of words) { if ((cur + ' ' + w).trim().length > n) { lines.push(cur.trim()); cur = w } else cur += ' ' + w }
    if (cur.trim()) lines.push(cur.trim())
    return lines.slice(0, 2)
  }
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: 880, display: "block", margin: "0 auto" }} role="img" aria-label="career graph">
      {recs.map((r, i) => {
        const y = 45 + i * 74 + 18
        const w = 2 + (r.score / max) * 10
        return (
          <g key={r.role_id}>
            <path d={`M ${cx + 90} ${cy} C ${cx + 230} ${cy}, ${430 - 140} ${y}, 440 ${y}`} stroke={i === 0 ? 'var(--gold-fill)' : 'var(--primary-2)'} strokeOpacity={i === 0 ? 0.95 : 0.4} strokeWidth={w} fill="none" strokeLinecap="round" />
            <text x={(cx + 90 + 430) / 2 + 20} y={(cy + y) / 2 - 6} fontSize="12" fill="var(--muted)" textAnchor="middle" fontFamily="JetBrains Mono, monospace">{r.score.toFixed(2)}</text>
            <rect x={440} y={y - 26} width={300} height={52} rx={12} fill={i === 0 ? 'var(--gold-soft)' : 'var(--surface)'} stroke={i === 0 ? 'var(--gold-fill)' : 'var(--border)'} />
            <text x={454} y={y - 6} fontSize="13" fontWeight="600" fill="var(--text)">{i + 1}. {wrap(lang === 'kk' ? r.title_kk : r.title_ru, 36)[0]}</text>
            <text x={454} y={y + 14} fontSize="11.5" fill="var(--muted)">P̂={r.p_transition.toFixed(3)} · C={pct(r.coverage)} · {r.top_missing.length ? r.top_missing[0].label.slice(0, 26) : ''}</text>
          </g>
        )
      })}
      <circle cx={cx - 10} cy={cy} r={92} fill="none" stroke="var(--border-strong)" strokeDasharray="2 7" />
      <rect x={cx - 110} y={cy - 34} width={200} height={68} rx={14} fill="var(--ink)" />
      {wrap(current, 24).map((l, i, a) => <text key={i} x={cx - 10} y={cy + 5 + (i - (a.length - 1) / 2) * 17} fontSize="13.5" fontWeight="700" fill="#fff" textAnchor="middle">{l}</text>)}
    </svg>
  )
}

export function RecList({ eid, current }: { eid: number; current: string }) {
  const { t, lang } = useI18n()
  const [alpha, setAlpha] = useState<number | null>(null)
  const [data, setData] = useState<{ alpha: number; roles: RoleRec[] } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    const q = alpha === null ? '' : `?alpha=${alpha}`
    api<{ alpha: number; roles: RoleRec[] }>(`/api/profiles/${eid}/recommendations${q}`).then((d) => { setData(d); if (alpha === null) setAlpha(d.alpha) }).catch((e) => setErr(e.message))
  }, [eid, alpha])
  if (err) return <ErrorBox msg={err} />
  if (!data) return <Loading />
  return (
    <div className="stack">
      <Card title={t('recommendations')} icon="scale">
        <div className="stack" style={{ gap: 10 }}>
          <span className="formula">{t('hybridFormula')}</span>
          <div className="row">
            <b className="num" style={{ minWidth: 70 }}>α = {alpha?.toFixed(2)}</b>
            <input type="range" min={0} max={1} step={0.05} value={alpha ?? 0.75} onChange={(e) => setAlpha(+e.target.value)} style={{ flex: 1, minWidth: 180 }} />
            <span className="legend"><i style={{ background: 'var(--primary)' }} />{t('transitionPart')}</span>
            <span className="legend"><i style={{ background: 'var(--gold-fill)' }} />{t('skillPart')}</span>
          </div>
          <div className="small muted">{t('alphaHint')}</div>
        </div>
      </Card>
      <Card title={t('careerGraph')} icon="route"><CareerGraph current={current} recs={data.roles.slice(0, 5)} lang={lang} /></Card>
      <div className="grid g2">
        {data.roles.map((r, i) => (
          <div className="card stack" key={r.role_id} style={{ gap: 8 }}>
            <div className="row"><b>{i + 1}. {lang === 'kk' ? r.title_kk : r.title_ru}</b><div className="spacer" /><span className="badge info num">{r.score.toFixed(3)}</span></div>
            <div className="stacked" title={`${r.alpha_part.toFixed(3)} + ${r.skill_part.toFixed(3)}`}>
              <span className="a" style={{ width: `${r.alpha_part * 100}%` }} /><span className="s" style={{ width: `${r.skill_part * 100}%` }} />
            </div>
            <div className="small muted mono">α·P̃ = {r.alpha_part.toFixed(3)} (P̂ = {r.p_transition.toFixed(3)}, n = {r.transition_count}) · (1−α)·C = {r.skill_part.toFixed(3)} (C = {pct(r.coverage)})</div>
            {r.top_missing.length > 0 && <div><div className="small" style={{ fontWeight: 600 }}>{t('topMissing')}:</div>
              <div className="chips" style={{ marginTop: 4 }}>{r.top_missing.map((m) => <span key={m.esco_id} className="badge">{m.label} · p={m.priority}</span>)}</div></div>}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function CareerPage() {
  const { user } = useAuth()
  const { t, lang } = useI18n()
  const eid = user!.employee_id!
  const [prof, setProf] = useState<Employee | null>(null)
  useEffect(() => { api<Employee>(`/api/profiles/${eid}`).then(setProf) }, [eid])
  if (!prof) return <Loading />
  return (
    <div className="stack reveal">
      <PageHead eyebrow={`${t('currentRole')}: ${roleTitle(prof.current_role, lang)}`} title={t('navCareer')} sub={t('hybridFormula')} />
      <RecList eid={eid} current={roleTitle(prof.current_role, lang)} />
    </div>
  )
}
