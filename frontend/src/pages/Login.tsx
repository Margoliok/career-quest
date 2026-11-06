import { useState } from 'react'
import { login, type User } from '../api'
import { LangSwitch, Logo } from '../App'
import { Contours, Icon, type IconName } from '../components/Icon'
import { useI18n } from '../i18n'

const FEATURES: Record<'kk' | 'ru', [IconName, string, string][]> = {
  kk: [
    ['file', 'Түйіндемені талдау', 'Қазақ, орыс, ағылшын мәтінінен дағдылар дәлел-фрагментімен және 1–4 деңгеймен.'],
    ['layers', 'ESCO таксономиясы', '13 939 дағды мен 3 043 кәсіп — көптілді эмбеддингтер арқылы.'],
    ['target', 'Алшақтық', 'Мақсатты рөлді қамту C(e, r) және басымдық p_s.'],
    ['compass', 'Келесі рөл', 'Karrierewege статистикасы + дағдылар ұқсастығы, түсіндірмесімен.'],
    ['calendar', 'ЖДЖ 30/60/90', 'Курстар каталогына сүйенген жоспар және басшымен келісу.'],
    ['shield', 'Адам бақылауы', 'Соңғы шешім — қызметкер мен басшыда, барлық әрекет аудитте.'],
  ],
  ru: [
    ['file', 'Анализ резюме', 'Навыки из текста на каз/рус/англ с доказательством и уровнем 1–4.'],
    ['layers', 'Таксономия ESCO', '13 939 навыков и 3 043 профессии — многоязычные эмбеддинги.'],
    ['target', 'Разрыв навыков', 'Покрытие целевой роли C(e, r) и приоритет p_s.'],
    ['compass', 'Следующая роль', 'Статистика Karrierewege + сходство навыков, с объяснением.'],
    ['calendar', 'ИПР 30/60/90', 'План на основе каталога курсов и согласование с руководителем.'],
    ['shield', 'Контроль человека', 'Решение — за сотрудником и руководителем, всё в журнале аудита.'],
  ],
}

function RouteArt({ lang }: { lang: 'kk' | 'ru' }) {
  const stops = lang === 'kk'
    ? [['Junior', 'Кіші талдаушы'], ['Data Analyst', 'Талдаушы'], ['Senior / DS / BI', 'Келесі қадам']]
    : [['Junior', 'Младший аналитик'], ['Data Analyst', 'Аналитик'], ['Senior / DS / BI', 'Следующий шаг']]
  const pts = [[40, 150], [270, 70], [520, 118]]
  return (
    <svg className="hero-route" viewBox="0 0 600 218" role="img" aria-label="career route">
      <path d="M40 150 C 120 150, 170 70, 270 70 S 440 118, 520 118" fill="none" stroke="#e3a127" strokeWidth="3" strokeDasharray="2 9" strokeLinecap="round" />
      <path d="M520 118 C 560 118, 575 60, 590 40" fill="none" stroke="#7fa3cc" strokeWidth="2" strokeDasharray="2 8" strokeLinecap="round" opacity=".6" />
      {pts.map(([x, y], i) => (
        <g key={i}>
          <circle cx={x} cy={y} r={i === 2 ? 13 : 9} fill={i === 2 ? '#e3a127' : '#0c2136'} stroke="#e3a127" strokeWidth="3" />
          {i === 2 && <path d={`M${x - 4} ${y} l3 3 6-6`} stroke="#0c2136" strokeWidth="2.4" fill="none" strokeLinecap="round" />}
          <text x={x} y={y + (i === 1 ? -24 : 34)} textAnchor={i === 0 ? 'start' : i === 2 ? 'end' : 'middle'} fill="#e9eef5" fontSize="15" fontWeight="600" fontFamily="Unbounded, sans-serif">{stops[i][0]}</text>
          <text x={x} y={y + (i === 1 ? -8 : 52)} textAnchor={i === 0 ? 'start' : i === 2 ? 'end' : 'middle'} fill="#9fb1c6" fontSize="12.5" fontFamily="Golos Text, sans-serif">{stops[i][1]}</text>
        </g>
      ))}
    </svg>
  )
}

export default function LoginPage({ onLogin }: { onLogin: (u: User) => void }) {
  const { t, lang } = useI18n()
  const [username, setU] = useState('employee')
  const [password, setP] = useState('demo123')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const go = async (u = username, p = password) => {
    setBusy(u); setError(null)
    try { onLogin(await login(u, p)) } catch (e) { setError((e as Error).message) } finally { setBusy(null) }
  }
  const accounts: [string, IconName, string, string][] = [
    ['employee', 'user', t('roleEmployee'), 'E-001 · Junior Data Analyst · ҚАЗ'],
    ['employee2', 'user', t('roleEmployee'), 'E-002 · Junior Data Analyst · РУС'],
    ['manager', 'users', t('roleManager'), lang === 'kk' ? 'Деректер талдау бөлімі · ЖДЖ келісу' : 'Отдел анализа данных · согласование ИПР'],
    ['hr', 'chart', t('roleHr'), lang === 'kk' ? 'Дағдылар картасы, рөлдер, курстар, аудит' : 'Карта навыков, роли, курсы, аудит'],
  ]
  return (
    <div className="login-wrap">
      <section className="login-hero on-ink reveal">
        <Contours className="contours" opacity={0.2} />
        <div className="row"><Logo size={40} /><div><div className="brand-name" style={{ fontSize: 19 }}>Career Quest</div><div className="brand-sub">ESCO · Karrierewege · LLM</div></div><div className="spacer" /><LangSwitch /></div>
        <div>
          <div className="eyebrow" style={{ color: '#e3a127' }}>{lang === 'kk' ? 'Кәсіби даму жолы' : 'Путь профессионального развития'}</div>
          <h1>{lang === 'kk' ? <>Дағдыларыңызды талдап, <em>келесі қадамды</em> көрсететін AI-бағыттаушы</> : <>ИИ-помощник, который анализирует навыки и показывает <em>следующий шаг</em></>}</h1>
        </div>
        <RouteArt lang={lang} />
        <div className="features">
          {FEATURES[lang].map(([ic, b, d]) => (
            <div className="feature" key={b}><span className="ic"><Icon name={ic} size={18} /></span><div><b>{b}</b><span>{d}</span></div></div>
          ))}
        </div>
      </section>
      <section className="login-side">
        <div className="login-card reveal">
          <div>
            <div className="eyebrow">{lang === 'kk' ? 'Жүйеге кіру' : 'Вход в систему'}</div>
            <h1 style={{ fontSize: 24 }}>{t('login')}</h1>
          </div>
          <form className="stack" style={{ gap: 12 }} onSubmit={(e) => { e.preventDefault(); go() }}>
            <label className="field"><span>{t('username')}</span><input value={username} onChange={(e) => setU(e.target.value)} autoComplete="username" /></label>
            <label className="field"><span>{t('password')}</span><input value={password} onChange={(e) => setP(e.target.value)} type="password" autoComplete="current-password" /></label>
            <button className="btn primary" disabled={!!busy} style={{ minHeight: 46 }}>{busy === username ? <span className="spin" /> : <Icon name="next" />}{t('login')}</button>
          </form>
          {error && <div className="error" role="alert"><Icon name="info" />{error}</div>}
          <div className="row small muted" style={{ gap: 8 }}><div className="divider" style={{ flex: 1 }} />{t('demoAccounts')}<div className="divider" style={{ flex: 1 }} /></div>
          <div className="stack" style={{ gap: 10 }}>
            {accounts.map(([u, ic, r, d]) => (
              <button key={u} className="acc" onClick={() => go(u, 'demo123')} disabled={!!busy}>
                <span className="ic"><Icon name={ic} /></span>
                <span><b>{r}</b> <span className="muted small mono">{u}</span><div className="small muted">{d}</div></span>
                <span className="go">{busy === u ? <span className="spin" /> : <Icon name="next" />}</span>
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
