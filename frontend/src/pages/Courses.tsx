import { useState } from 'react'
import { api, type Course } from '../api'
import { useAuth } from '../App'
import { Card, ErrorBox, Loading, PageHead, useAsync } from '../components/ui'
import { Icon } from '../components/Icon'
import { useI18n } from '../i18n'

export default function CoursesPage() {
  const { t } = useI18n()
  const { user } = useAuth()
  const list = useAsync(() => api<Course[]>('/api/hr/courses'), [])
  const [f, setF] = useState({ title: '', provider: '', url: '', lang: 'kk', skill: '' })
  const [found, setFound] = useState<{ esco_id: string; label: string }[]>([])
  const [picked, setPicked] = useState<{ esco_id: string; label: string }[]>([])
  const [err, setErr] = useState<string | null>(null)
  const search = async () => { if (f.skill.trim()) setFound(await api(`/api/skills/search?q=${encodeURIComponent(f.skill)}&k=5`)) }
  const add = async () => {
    setErr(null)
    try {
      await api('/api/hr/courses', { method: 'POST', body: { title: f.title, provider: f.provider, url: f.url, lang: f.lang, esco_ids: picked.map((p) => p.esco_id) } })
      setF({ title: '', provider: '', url: '', lang: 'kk', skill: '' }); setPicked([]); setFound([]); list.reload()
    } catch (e) { setErr((e as Error).message) }
  }
  const del = async (id: number) => { await api(`/api/hr/courses/${id}`, { method: 'DELETE' }); list.reload() }
  if (!list.data) return <Loading />
  return (
    <div className="stack reveal">
      <PageHead eyebrow={`${list.data.length} · Kaggle · Stepik · Coursera · Microsoft Learn · Skills Enbek`} title={t('navCourses')} />
      <Card>
        <div className="table-wrap"><table>
          <thead><tr><th>{t('title')}</th><th>{t('provider')}</th><th>{t('language')}</th><th>{t('skills')} (ESCO)</th><th /></tr></thead>
          <tbody>{list.data.map((c) => (
            <tr key={c.id}>
              <td>{c.url ? <a href={c.url} target="_blank" rel="noreferrer" className="row" style={{ gap: 5, display: 'inline-flex' }}><b>{c.title}</b><Icon name="external" size={13} /></a> : <b>{c.title}</b>}<div className="small muted">{c.description}</div></td>
              <td className="small">{c.provider}{c.is_free && <> · <span className="badge ok">{t('free')}</span></>}</td>
              <td>{c.lang.toUpperCase()}</td>
              <td><div className="chips">{(c.skills || []).slice(0, 6).map((s) => <span key={s} className="badge">{s}</span>)}{(c.skills || []).length > 6 && <span className="badge">+{(c.skills || []).length - 6}</span>}</div></td>
              <td>{user?.role === 'hr' && <button className="btn sm danger" onClick={() => del(c.id)} aria-label={t('remove')}><Icon name="trash" size={14} /></button>}</td>
            </tr>))}</tbody>
        </table></div>
      </Card>
      {user?.role === 'hr' && <Card title={t('add')} icon="plus">
        <div className="grid g2">
          <input placeholder={t('title')} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
          <input placeholder={t('provider')} value={f.provider} onChange={(e) => setF({ ...f, provider: e.target.value })} />
          <input placeholder="URL" value={f.url} onChange={(e) => setF({ ...f, url: e.target.value })} />
          <select value={f.lang} onChange={(e) => setF({ ...f, lang: e.target.value })}><option value="kk">KK</option><option value="ru">RU</option><option value="en">EN</option></select>
        </div>
        <form className="row" style={{ marginTop: 10 }} onSubmit={(e) => { e.preventDefault(); search() }}>
          <input style={{ flex: 1 }} placeholder={t('addSkill')} value={f.skill} onChange={(e) => setF({ ...f, skill: e.target.value })} /><button className="btn">{t('search')}</button></form>
        <div className="chips" style={{ marginTop: 8 }}>{found.map((s) => <button key={s.esco_id} className="chip" onClick={() => !picked.some((p) => p.esco_id === s.esco_id) && setPicked([...picked, s])}>+ {s.label}</button>)}</div>
        <div className="chips" style={{ marginTop: 8 }}>{picked.map((s) => <span key={s.esco_id} className="badge info">{s.label}</span>)}</div>
        <ErrorBox msg={err} />
        <button className="btn primary" style={{ marginTop: 10 }} disabled={!f.title || !f.provider || !picked.length} onClick={add}>{t('add')}</button>
      </Card>}
    </div>
  )
}
