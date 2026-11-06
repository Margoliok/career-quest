import { useEffect, useState } from 'react'
import { api, type Role } from '../api'
import { Card, ErrorBox, Loading, PageHead, RelBadge, useAsync } from '../components/ui'
import { Icon } from '../components/Icon'
import { roleTitle, useI18n } from '../i18n'

interface Req { esco_id: string; label: string; weight: number; required_level: number; relation: string }
interface RoleDetail extends Role { requirements: Req[]; sources: Record<string, string> }

export default function RolesPage() {
  const { t, lang } = useI18n()
  const roles = useAsync(() => api<Role[]>('/api/roles'), [])
  const [rid, setRid] = useState<number | null>(null)
  const [detail, setDetail] = useState<RoleDetail | null>(null)
  const [reqs, setReqs] = useState<Req[]>([])
  const [q, setQ] = useState('')
  const [found, setFound] = useState<{ esco_id: string; label: string; similarity: number }[]>([])
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { if (roles.data && rid === null) setRid(roles.data[0].id) }, [roles.data, rid])
  useEffect(() => { if (rid) api<RoleDetail>(`/api/roles/${rid}`).then((d) => { setDetail(d); setReqs(d.requirements) }) }, [rid])
  const search = async () => { if (q.trim()) setFound(await api(`/api/skills/search?q=${encodeURIComponent(q)}`)) }
  const save = async () => {
    setErr(null)
    try { await api(`/api/hr/roles/${rid}/skills`, { method: 'PUT', body: reqs.map(({ esco_id, weight, required_level, relation }) => ({ esco_id, weight, required_level, relation })) }); setMsg(t('saved')) }
    catch (e) { setErr((e as Error).message) }
  }
  const upd = (i: number, k: 'weight' | 'required_level', v: number) => setReqs(reqs.map((r, j) => (j === i ? { ...r, [k]: v } : r)))
  if (!roles.data) return <Loading />
  return (
    <div className="stack reveal">
      <PageHead eyebrow="ESCO + O*NET + expert" title={t('navRoles')}
        actions={<select value={rid ?? ''} onChange={(e) => { setRid(+e.target.value); setMsg(null) }} aria-label={t('chooseRole')}>{roles.data.map((r) => <option key={r.id} value={r.id}>{roleTitle(r, lang)}</option>)}</select>} />
      {detail && <div className="card stack" style={{ gap: 4 }}>
        <div><b>{t('esco')}:</b> <a href={detail.esco_occupation_id} target="_blank" rel="noreferrer">{detail.esco_occupation_label}</a> · <b>grade</b> {detail.grade}</div>
        <div className="small muted">{lang === 'kk' ? detail.description_kk : detail.description_ru}</div>
        <div className="small"><b>{t('profStd')}:</b> {detail.prof_standard_ref || <span className="muted">— ({t('toFill')})</span>}</div>
      </div>}
      <Card title={`${t('requirements')} (${reqs.length})`} icon="puzzle" right={<div className="row">{msg && <span className="badge ok"><Icon name="check" size={13} />{msg}</span>}<button className="btn primary" onClick={save}><Icon name="check" />{t('save')}</button></div>}>
        <ErrorBox msg={err} />
        <div className="table-wrap"><table>
          <thead><tr><th>{t('skill')}</th><th /><th>{t('source')}</th><th>{t('weight')}</th><th>{t('required')}</th><th /></tr></thead>
          <tbody>{reqs.map((r, i) => (
            <tr key={r.esco_id}>
              <td><b>{r.label}</b></td><td><RelBadge rel={r.relation} /></td><td className="small">{detail?.sources[r.esco_id] || 'expert'}</td>
              <td><select value={r.weight} onChange={(e) => upd(i, 'weight', +e.target.value)}>{[0.25, 0.5, 1, 1.5, 2].map((w) => <option key={w} value={w}>{w}</option>)}</select></td>
              <td><select value={r.required_level} onChange={(e) => upd(i, 'required_level', +e.target.value)}>{[1, 2, 3, 4].map((l) => <option key={l} value={l}>{l}</option>)}</select></td>
              <td><button className="btn sm danger" onClick={() => setReqs(reqs.filter((_, j) => j !== i))} aria-label={t('remove')}><Icon name="trash" size={14} /></button></td>
            </tr>))}</tbody>
        </table></div>
      </Card>
      <Card title={t('addSkill')} icon="plus">
        <form className="row" onSubmit={(e) => { e.preventDefault(); search() }}><input style={{ flex: 1 }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="data quality, SQL, деректерді визуализациялау…" /><button className="btn"><Icon name="search" />{t('search')}</button></form>
        <div className="stack" style={{ gap: 6, marginTop: 10 }}>{found.map((f) => (
          <div key={f.esco_id} className="row"><span>{f.label}</span><span className="small muted">{f.similarity.toFixed(2)}</span><div className="spacer" />
            <button className="btn sm" disabled={reqs.some((r) => r.esco_id === f.esco_id)} onClick={() => setReqs([...reqs, { esco_id: f.esco_id, label: f.label, weight: 0.5, required_level: 2, relation: 'expert' }])}>{t('add')}</button></div>))}
        </div>
      </Card>
    </div>
  )
}
