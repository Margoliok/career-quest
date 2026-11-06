import { useState } from 'react'
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Legend, Tooltip } from 'recharts'
import { api, DEMO, type EmpSkill, type Employee, type Gap } from '../api'
import { useAuth } from '../App'
import { SkillsTable } from '../components/SkillsTable'
import { Card, ErrorBox, Kpi, Loading, PageHead, pct, useAsync } from '../components/ui'
import { Icon } from '../components/Icon'
import { roleTitle, useI18n } from '../i18n'

export function SkillRadar({ gap }: { gap: Gap }) {
  const { t } = useI18n()
  // қызметкерде бар дағдылар (ең көбі 5) + басымдығы жоғары жетіспейтін дағдылар → 8 ось
  const has = [...gap.matched, ...gap.missing].filter((x) => x.employee_level > 0).sort((a, b) => b.weight - a.weight).slice(0, 5)
  const lacking = gap.missing.filter((x) => x.employee_level === 0).slice(0, 8 - has.length)
  const pick = [...has, ...lacking].map((x) => ({ skill: x.label.length > 22 ? x.label.slice(0, 21) + '…' : x.label, req: x.required_level, emp: x.employee_level }))
  if (pick.length < 3) return null
  return (
    <ResponsiveContainer width="100%" height={300}>
      <RadarChart data={pick} outerRadius="70%">
        <PolarGrid />
        <PolarAngleAxis dataKey="skill" tick={{ fontSize: 11, fill: 'var(--muted)' }} />
        <PolarRadiusAxis domain={[0, 4]} tickCount={5} tick={{ fontSize: 10 }} />
        <Radar name={t('required')} dataKey="req" stroke="#e3a127" fill="#e3a127" fillOpacity={0.18} strokeWidth={2} />
        <Radar name={t('yours')} dataKey="emp" stroke="#1d4f8f" fill="#2a68bb" fillOpacity={0.45} strokeWidth={2} />
        <Legend /><Tooltip />
      </RadarChart>
    </ResponsiveContainer>
  )
}

export default function ProfilePage() {
  const { user } = useAuth()
  const { t, lang } = useI18n()
  const eid = user!.employee_id!
  const prof = useAsync(() => api<Employee>(`/api/profiles/${eid}`), [eid])
  const skills = useAsync(() => api<EmpSkill[]>(`/api/profiles/${eid}/skills`), [eid])
  const gap = useAsync(() => prof.data?.target_role ? api<Gap>(`/api/profiles/${eid}/gap`) : Promise.resolve(null), [prof.data?.target_role?.id, skills.data])
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [consent, setConsent] = useState(true)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [showText, setShowText] = useState(false)

  const analyze = async () => {
    setBusy(true); setErr(null); setResult(null)
    try {
      const fd = new FormData()
      if (file) fd.append('file', file); else fd.append('text', text || prof.data?.latest_text || '')
      fd.append('use_llm', 'true')
      const r = await api<{ found: number; added: number; updated: number; kept: number; method: string; lang: string }>(`/api/profiles/${eid}/analyze`, { method: 'POST', form: fd })
      setResult(`${t('analysisDone')}: ${r.found} ${t('found')} (+${r.added}, ↻${r.updated}) · ${t('method')}: ${r.method} · ${r.lang}`)
      skills.reload(); prof.reload()
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const patch = async (esco_id: string, p: { level?: number }) => {
    await api(`/api/profiles/${eid}/skills`, { method: 'PATCH', body: { esco_id, ...p } }); skills.reload()
  }
  if (prof.loading && !prof.data) return <Loading />
  const e = prof.data
  const sk = skills.data || []
  return (
    <div className="stack reveal">
      <PageHead eyebrow={e?.code} title={t('navProfile')} sub={lang === 'kk' ? 'Түйіндемеден анықталған дағдылар, олардың дәлелі мен деңгейі. Деңгейді өзіңіз түзете аласыз — басшы растайды.' : 'Навыки, найденные в резюме, с доказательствами и уровнями. Уровень можно скорректировать — подтверждает руководитель.'} />
      <div className="grid g4">
        <Kpi icon="flag" label={t('currentRole')} text={roleTitle(e?.current_role, lang)} />
        <Kpi icon="target" label={t('targetRole')} text={roleTitle(e?.target_role, lang)} />
        <Kpi icon="layers" label={t('skills')} value={<span className="num">{sk.length}</span>} hint={`${sk.filter((s) => s.status === 'confirmed').length} ${t('confirmed').toLowerCase()}`} />
        <Kpi icon="compass" label={t('coverage')} value={<span className="num">{pct(gap.data?.coverage)}</span>} />
      </div>
      <div className="grid g-side">
        <Card title={t('uploadResume')} icon="upload">
          <div className="stack" style={{ gap: 10 }}>
            <label className="dropzone">
              <input type="file" accept=".pdf,.docx,.txt" onChange={(ev) => setFile(ev.target.files?.[0] || null)} disabled={DEMO} />
              <span className="ic"><Icon name="upload" size={20} /></span>
              <span><b>{file ? file.name : 'PDF · DOCX · TXT'}</b><div className="small muted">{file ? `${Math.round(file.size / 1024)} KB` : t('uploadHint')}</div></span>
            </label>
            <textarea rows={5} value={text} onChange={(ev) => setText(ev.target.value)} placeholder={e?.latest_text?.slice(0, 160) + '…'} disabled={DEMO} />
            <label className="check small"><input type="checkbox" checked={consent} onChange={(ev) => setConsent(ev.target.checked)} />{t('consent')}</label>
            <div className="row">
              <button className="btn primary" disabled={!consent || busy} onClick={analyze}>{busy ? <span className="spin" /> : <Icon name="sparkles" />}{busy ? t('analyzing') : t('analyze')}</button>
              {e?.latest_text && <button className="btn" onClick={() => setShowText(!showText)}>{t('details')}</button>}
            </div>
            {result && <div className="notice" style={{ background: 'var(--ok-soft)', borderColor: 'transparent' }}><Icon name="check" />{result}</div>}
            <ErrorBox msg={err} />
            {showText && e?.latest_text && <pre className="resume">{e.latest_text}</pre>}
          </div>
        </Card>
        <Card title={t('radarTitle')} icon="target">
          {gap.data ? <SkillRadar gap={gap.data} /> : <div className="muted">{t('chooseRole')}</div>}
        </Card>
      </div>
      <Card title={t('skillMap')} icon="layers" right={<span className="small muted">{t('selfAssess')}: {t('level').toLowerCase()} → {t('stAuto')}</span>}>
        {skills.loading && !skills.data ? <Loading /> : <SkillsTable skills={sk} mode="employee" onPatch={patch} />}
      </Card>
    </div>
  )
}
