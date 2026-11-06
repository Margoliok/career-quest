import { type EmpSkill } from '../api'
import { useI18n } from '../i18n'
import { LevelDots, StatusBadge } from './ui'
import { Icon } from './Icon'

export function SkillsTable({ skills, mode, onPatch }: {
  skills: EmpSkill[]; mode: 'employee' | 'manager' | 'readonly'
  onPatch?: (esco_id: string, patch: { level?: number; status?: string }) => void
}) {
  const { t } = useI18n()
  if (!skills.length) return <div className="muted">{t('noData')}</div>
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>
          <th>{t('skill')}</th><th>{t('level')}</th><th>{t('evidence')}</th><th>{t('status')}</th><th>{t('similarity')}</th>
          {mode === 'manager' && <th />}
        </tr></thead>
        <tbody>
          {skills.map((s) => (
            <tr key={s.esco_id} style={{ opacity: s.status === 'rejected' ? 0.5 : 1 }}>
              <td style={{ minWidth: 180 }}>
                <b>{s.label}</b>
                <div className="small muted">{s.type} · <a href={s.esco_id} target="_blank" rel="noreferrer">ESCO</a> · {s.source}</div>
              </td>
              <td style={{ whiteSpace: 'nowrap' }}>
                {mode === 'readonly' ? <LevelDots level={s.level} /> : (
                  <select value={s.level} onChange={(e) => onPatch?.(s.esco_id, { level: +e.target.value })} title={mode === 'employee' ? t('selfAssess') : ''}>
                    {[1, 2, 3, 4].map((l) => <option key={l} value={l}>{t(`lvl${l}` as 'lvl1')}</option>)}
                  </select>
                )}
              </td>
              <td><div className="evidence">«{s.evidence}»</div></td>
              <td><StatusBadge status={s.status} /></td>
              <td>{s.similarity ? s.similarity.toFixed(2) : '—'}</td>
              {mode === 'manager' && (
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button className="btn sm ok" disabled={s.status === 'confirmed'} onClick={() => onPatch?.(s.esco_id, { status: 'confirmed' })}><Icon name="check" size={14} />{t('confirm')}</button>{' '}
                  <button className="btn sm danger" disabled={s.status === 'rejected'} onClick={() => onPatch?.(s.esco_id, { status: 'rejected' })} aria-label={t('reject')}><Icon name="x" size={14} /></button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
