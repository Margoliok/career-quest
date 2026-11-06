import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { useI18n, type Key } from '../i18n'
import { Icon, type IconName } from './Icon'

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const run = useCallback(() => {
    setLoading(true)
    setError(null)
    fn().then(setData).catch((e) => setError(e.message || String(e))).finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { run() }, [run])
  return { data, error, loading, reload: run, setData }
}

export function Loading({ rows = 3 }: { rows?: number }) {
  const { t } = useI18n()
  return (
    <div className="stack" style={{ gap: 12 }} aria-busy="true" aria-label={t('loading')}>
      <div className="skeleton" style={{ height: 34, width: '38%' }} />
      {Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton" style={{ height: 88 }} />)}
    </div>
  )
}

export function ErrorBox({ msg }: { msg: string | null }) {
  return msg ? <div className="error" role="alert"><Icon name="info" />{msg}</div> : null
}

export function Empty({ icon = 'layers', text, action }: { icon?: IconName; text: string; action?: ReactNode }) {
  return <div className="empty"><div className="ic"><Icon name={icon} size={24} /></div><div>{text}</div>{action}</div>
}

export function PageHead({ eyebrow, title, sub, actions, badge }: { eyebrow?: string; title: ReactNode; sub?: ReactNode; actions?: ReactNode; badge?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <div className="row" style={{ gap: 12 }}><h1>{title}</h1>{badge}</div>
        {sub && <div className="page-sub">{sub}</div>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </div>
  )
}

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { id: T; label: string; icon?: IconName }[] }) {
  return (
    <div className="tabs" role="tablist">
      {items.map((it) => (
        <button key={it.id} role="tab" aria-selected={value === it.id} className={value === it.id ? 'on' : ''} onClick={() => onChange(it.id)}>
          {it.icon && <Icon name={it.icon} size={16} />}{it.label}
        </button>
      ))}
    </div>
  )
}

const ST: Record<string, [string, Key]> = {
  auto: ['info', 'stAuto'], unverified: ['warn', 'stUnverified'], confirmed: ['ok', 'stConfirmed'], rejected: ['bad', 'stRejected'],
}
export function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n()
  const [cls, k] = ST[status] || ['', 'stAuto']
  return <span className={`badge ${cls}`}><span className="d" />{t(k)}</span>
}

const IDP_ST: Record<string, [string, Key]> = {
  draft: ['', 'idpDraft'], submitted: ['warn', 'idpSubmitted'], approved: ['ok', 'idpApproved'], returned: ['bad', 'idpReturned'],
}
export function IdpBadge({ status }: { status: string | null | undefined }) {
  const { t } = useI18n()
  if (!status) return <span className="muted">—</span>
  const [cls, k] = IDP_ST[status] || ['', 'idpDraft']
  return <span className={`badge ${cls}`}><span className="d" />{t(k)}</span>
}

export function RelBadge({ rel }: { rel: string }) {
  const { t } = useI18n()
  const m: Record<string, [string, Key]> = { essential: ['info', 'relEssential'], optional: ['', 'relOptional'], expert: ['accent', 'relExpert'] }
  const [cls, k] = m[rel] || ['', 'relOptional']
  return <span className={`badge ${cls}`}>{t(k)}</span>
}

export function LevelDots({ level, max = 4, required }: { level: number; max?: number; required?: number }) {
  return (
    <span style={{ display: 'inline-flex', gap: 3, verticalAlign: 'middle' }} title={`${level}/${max}`} aria-label={`${level}/${max}`}>
      {Array.from({ length: max }, (_, i) => {
        const filled = i < level
        const req = required !== undefined && i < required
        return <i key={i} style={{ width: 11, height: 11, borderRadius: 3, display: 'inline-block',
          background: filled ? 'var(--primary)' : req ? 'var(--gold-soft)' : 'var(--surface-3)',
          boxShadow: req && !filled ? 'inset 0 0 0 1.5px var(--gold-fill)' : 'none' }} />
      })}
    </span>
  )
}

/** Компас-шкала: қамту көрсеткіші */
export function Gauge({ value, size = 150, label }: { value: number; size?: number; label?: string }) {
  const r = size / 2 - 14
  const c = 2 * Math.PI * r
  const v = Math.max(0, Math.min(1, value))
  const color = v >= 0.7 ? 'var(--ok)' : v >= 0.4 ? 'var(--gold-fill)' : 'var(--primary)'
  const ticks = Array.from({ length: 24 }, (_, i) => i)
  return (
    <div className="gauge" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {ticks.map((i) => {
          const a = (i / 24) * 2 * Math.PI - Math.PI / 2
          const r1 = size / 2 - 3, r2 = size / 2 - (i % 6 === 0 ? 9 : 6)
          return <line key={i} x1={size / 2 + r1 * Math.cos(a)} y1={size / 2 + r1 * Math.sin(a)} x2={size / 2 + r2 * Math.cos(a)} y2={size / 2 + r2 * Math.sin(a)} stroke="var(--border-strong)" strokeWidth={1.2} />
        })}
        <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--surface-3)" strokeWidth={10} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={10} fill="none" strokeLinecap="round"
          strokeDasharray={`${c * v} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: 'stroke-dasharray .6s cubic-bezier(.2,.8,.2,1)' }} />
      </svg>
      <div className="val"><div><b>{Math.round(v * 100)}%</b>{label && <div className="small muted mono" style={{ marginTop: 4 }}>{label}</div>}</div></div>
    </div>
  )
}

export function Card({ title, icon, children, right, className }: { title?: ReactNode; icon?: IconName; children: ReactNode; right?: ReactNode; className?: string }) {
  return (
    <section className={`card ${className || ''}`}>
      {(title || right) && <div className="card-head">{icon && <span className="ic"><Icon name={icon} size={17} /></span>}<h2>{title}</h2><div className="spacer" />{right}</div>}
      {children}
    </section>
  )
}

export function Kpi({ label, value, hint, icon, text }: { label: string; value?: ReactNode; hint?: ReactNode; icon?: IconName; text?: ReactNode }) {
  return (
    <div className="card kpi">
      {icon && <span className="ic"><Icon name={icon} size={22} /></span>}
      <div className="l">{label}</div>
      {value !== undefined && <div className="v">{value}</div>}
      {text && <div className="t">{text}</div>}
      {hint && <div className="small muted" style={{ marginTop: 4 }}>{hint}</div>}
    </div>
  )
}

export function pct(v: number | null | undefined) { return v === null || v === undefined ? '—' : `${Math.round(v * 100)}%` }
