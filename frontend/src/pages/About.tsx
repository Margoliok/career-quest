import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useAuth } from '../App'
import { Card, PageHead } from '../components/ui'
import { useI18n } from '../i18n'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Results = any

const TXT = {
  kk: {
    title: 'Әдістеме және эксперимент нәтижелері', arch: 'Жүйе архитектурасы', data: 'Деректер',
    e2: 'Э2. Қазақ/орыс профильдерінде дағдыларды анықтау (test, F1)', e3: 'Э3. Karrierewege-де келесі кәсіпті болжау (test)',
    e4: 'Э4. α бойынша абляция (validation, MRR)', e1: 'Э1. SkillSpan (ағылш.) span деңгейіндегі F1',
    note: 'Барлық сандар скрипттермен есептелген (backend/scripts/experiments), ойдан қосылған мән жоқ. Э5 (сарапшылық бағалау) мен SUS сауалнамалары нақты қатысушылармен толтырылады.',
    pipe: 'Конвейер', formulas: 'Формулалар',
  },
  ru: {
    title: 'Методика и результаты экспериментов', arch: 'Архитектура системы', data: 'Данные',
    e2: 'Э2. Извлечение навыков на каз/рус профилях (test, F1)', e3: 'Э3. Предсказание следующей профессии на Karrierewege (test)',
    e4: 'Э4. Абляция по α (validation, MRR)', e1: 'Э1. SkillSpan (англ.) F1 на уровне фрагментов',
    note: 'Все числа рассчитаны скриптами (backend/scripts/experiments), выдуманных значений нет. Э5 (экспертная оценка) и SUS заполняются реальными участниками.',
    pipe: 'Конвейер', formulas: 'Формулы',
  },
}

export default function AboutPage() {
  const { lang } = useI18n()
  const { system } = useAuth()
  const T = TXT[lang]
  const [res, setRes] = useState<Results | null>(null)
  useEffect(() => { fetch(`${import.meta.env.BASE_URL}results.json`).then((r) => (r.ok ? r.json() : null)).then(setRes).catch(() => setRes(null)) }, [])
  const e2 = (res?.e2 || []).filter((r: any) => r.lang === 'all')
  return (
    <div className="stack reveal">
      <PageHead eyebrow="ESCO v1.2.1 · Karrierewege · SkillSpan" title={T.title} sub={T.note} />
      <div className="grid g2">
        <Card title={T.arch} icon="layers">
          <div className="stack small" style={{ gap: 6 }}>
            <div className="row" style={{ gap: 6 }}><span className="badge info">React + Vite</span><span className="muted">→</span><span className="badge info">FastAPI · JWT · RBAC</span><span className="muted">→</span><span className="badge sky">LLM-agent · 7 tools · guardrails</span><span className="muted">→</span><span className="badge">extract · gap · recommend · idp</span></div>
            <div><b>PostgreSQL + pgvector</b> (HNSW, cosine): ESCO, roles, transitions, courses, IDP, audit</div>
            <div className="mono">{T.pipe}: LLM→JSON (evidence, level) → e5 → ESCO top-{system?.top_k ?? 20} → LLM rerank → τ</div>
            <div>Закон РК об ИИ (ст. 8): human-in-the-loop · Закон о ПД: согласие, PII-фильтр, аудит</div>
            <div className="muted">LLM: {system?.llm_enabled ? system.llm_model : 'offline'} · emb: {system?.embedding_model} / {system?.offline_embedding_model} · α = {system?.alpha} · τ_off = {system?.offline_tau}</div>
          </div>
        </Card>
        <Card title={T.formulas} icon="scale">
          <div className="stack" style={{ gap: 6 }}>
            <span className="formula">(2) C(e,r) = Σ w·min(l<sub>e</sub>/l<sub>r</sub>, 1) / Σ w</span>
            <span className="formula">(3) p<sub>s</sub> = w<sub>s</sub>·max(l<sub>r,s</sub> − l<sub>e,s</sub>, 0)</span>
            <span className="formula">(4) P̂(r′|r) = (n(r→r′) + λ) / (n(r) + λ|R|)</span>
            <span className="formula">(5) Score = α·P̃(r′|r) + (1 − α)·C(e, r′)</span>
          </div>
        </Card>
      </div>
      {res && <>
        <div className="grid g2">
          <Card title={T.e2} icon="chart">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={e2} layout="vertical" margin={{ left: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} /><XAxis type="number" domain={[0, 1]} stroke="var(--muted)" /><YAxis type="category" dataKey="method" width={170} fontSize={11} stroke="var(--muted)" />
                <Tooltip cursor={{ fill: 'var(--surface-2)' }} /><Legend /><Bar dataKey="P" fill="#93b8e3" radius={[0, 4, 4, 0]} /><Bar dataKey="R" fill="#e3a127" radius={[0, 4, 4, 0]} /><Bar dataKey="F1" fill="#1b467f" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title={T.e3} icon="compass">
            <div className="table-wrap"><table>
              <thead><tr><th>Method</th><th>R@5</th><th>R@10</th><th>MRR</th><th>NDCG@10</th></tr></thead>
              <tbody>{(res.e3 || []).map((r: any) => <tr key={r.method}><td className="small">{r.method}</td><td className="num">{r['Recall@5'].toFixed(3)}</td><td className="num">{r['Recall@10'].toFixed(3)}</td><td className="num">{r.MRR.toFixed(3)}</td><td className="num">{r['NDCG@10'].toFixed(3)}</td></tr>)}</tbody>
            </table></div>
            <div className="small muted" style={{ marginTop: 8 }}>test: {res.e4?.test_cases} · val: {res.e4?.val_cases} · α* = {res.e4?.alpha_best}, λ* = {res.e4?.lambda_best}</div>
          </Card>
        </div>
        {res.e4 && <Card title={T.e4} icon="scale">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={res.e4.curve}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)" /><XAxis dataKey="alpha" stroke="var(--muted)" /><YAxis domain={['auto', 'auto']} stroke="var(--muted)" /><Tooltip /><Legend />
              <Line dataKey="MRR" stroke="#1b467f" dot={false} strokeWidth={2.5} /><Line dataKey="Recall@10" stroke="#e3a127" dot={false} strokeWidth={2.5} /><Line dataKey="NDCG@10" stroke="#0797ad" dot={false} strokeWidth={2} /></LineChart>
          </ResponsiveContainer>
        </Card>}
        {res.e1 && res.e1.length > 0 && <Card title={T.e1} icon="file">
          <div className="table-wrap"><table><thead><tr><th>Method</th><th>P</th><th>R</th><th>F1 (strict)</th><th>F1 (loose)</th></tr></thead>
            <tbody>{res.e1.map((r: any) => <tr key={r.method}><td>{r.method}</td><td>{r.P.toFixed(3)}</td><td>{r.R.toFixed(3)}</td><td>{r.F1.toFixed(3)}</td><td>{r.F1_loose.toFixed(3)}</td></tr>)}</tbody></table></div>
        </Card>}
      </>}
      <Card title={T.data} icon="layers">
        <div className="small stack" style={{ gap: 4 }}>
          <div>• ESCO v1.2.1 — 13 939 skills, 3 043 occupations, 126 051 relations (verified vs official ESCO API: 25/25)</div>
          <div>• Karrierewege (HuggingFace) — 455 129 train / 56 909 val / 56 850 test trajectories, 99.99% ESCO match</div>
          <div>• O*NET 30.0 Technology Skills (CC BY 4.0) · SkillSpan (MIT) · 48 synthetic kk/ru profiles (template-based gold)</div>
          <div className="muted">{T.note}</div>
        </div>
      </Card>
    </div>
  )
}
