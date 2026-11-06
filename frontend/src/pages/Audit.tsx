import { api, type AuditRow } from '../api'
import { Card, ErrorBox, Loading, PageHead, useAsync } from '../components/ui'
import { Icon } from '../components/Icon'
import { useI18n } from '../i18n'

export default function AuditPage() {
  const { t, lang } = useI18n()
  const list = useAsync(() => api<AuditRow[]>('/api/hr/audit?limit=200'), [])
  if (list.error) return <ErrorBox msg={list.error} />
  if (!list.data) return <Loading />
  return (
    <div className="stack reveal">
      <PageHead eyebrow={lang === 'kk' ? 'ЖИ әрекеттері мен шешімдер' : 'Действия ИИ и решения'} title={t('navAudit')} badge={<span className="badge">{list.data.length}</span>}
        actions={<button className="btn" onClick={list.reload} aria-label="refresh"><Icon name="refresh" /></button>} />
      <Card>
        <div className="table-wrap"><table>
          <thead><tr><th>{t('time')}</th><th>{t('actor')}</th><th>{t('action')}</th><th>{t('tool')}</th><th>ID</th><th>{t('details')}</th></tr></thead>
          <tbody>{list.data.map((a) => (
            <tr key={a.id}>
              <td className="small mono" style={{ whiteSpace: 'nowrap' }}>{new Date(a.created_at).toLocaleString()}</td>
              <td>{a.actor}</td><td><span className={`badge ${a.action.startsWith('idp_approved') ? 'ok' : a.action.includes('refused') ? 'warn' : a.tool ? 'sky' : ''}`}>{a.action}</span></td><td>{a.tool || ''}</td><td>{a.employee_id ?? ''}</td>
              <td className="small muted" style={{ maxWidth: 420, wordBreak: 'break-word' }}>{JSON.stringify(a.detail)}{a.input_hash && <div>sha256: {a.input_hash.slice(0, 16)}…</div>}</td>
            </tr>))}</tbody>
        </table></div>
      </Card>
    </div>
  )
}
