import { useEffect, useRef, useState } from 'react'
import { api, type ChatReply } from '../api'
import { useAuth } from '../App'
import { useI18n } from '../i18n'
import { Icon } from '../components/Icon'
import { PageHead } from '../components/ui'

export const SUGGEST = {
  kk: ['Data Analyst рөліне өту үшін маған не жетіспейді?', 'Неге маған бұл рөлдер ұсынылды?', 'SQL бойынша курстар ұсын',
    '30/60/90 күндік даму жоспарын құр', 'Менің жалақым қанша болуы керек?'],
  ru: ['Чего мне не хватает для роли Data Analyst?', 'Почему мне рекомендованы эти роли?', 'Подбери курсы по SQL',
    'Составь план развития на 30/60/90 дней', 'Какая у меня должна быть зарплата?'],
}

interface Msg { role: 'user' | 'assistant'; content: string; tools?: string[]; mode?: string }

export default function ChatPage() {
  const { user } = useAuth()
  const { t, lang } = useI18n()
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs])
  const send = async (m: string) => {
    if (!m.trim() || busy) return
    const hist = msgs.map((x) => ({ role: x.role, content: x.content }))
    setMsgs((x) => [...x, { role: 'user', content: m }]); setText(''); setBusy(true)
    try {
      const r = await api<ChatReply>('/api/chat', { method: 'POST', body: { message: m, employee_id: user!.employee_id, history: hist, lang } })
      setMsgs((x) => [...x, { role: 'assistant', content: r.answer, tools: r.tool_calls.map((c) => c.name), mode: r.mode }])
    } catch (e) { setMsgs((x) => [...x, { role: 'assistant', content: '⚠️ ' + (e as Error).message }]) } finally { setBusy(false) }
  }
  return (
    <div className="stack reveal">
      <PageHead eyebrow="RAG · tools · guardrails" title={t('navChat')} />
      <div className="card chat">
        <div className="chat-log" aria-live="polite">
          {msgs.length === 0 && <div className="chat-empty">
            <div className="orb"><Icon name="bot" size={30} /></div>
            <h2>{lang === 'kk' ? 'Сізге қалай көмектесе аламын?' : 'Чем могу помочь?'}</h2>
            <div className="small muted">{t('aiDisclaimer')}</div>
            <div className="chips" style={{ justifyContent: 'center' }}>{SUGGEST[lang].map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}</div>
          </div>}
          {msgs.map((m, i) => (
            <div key={i} className={`msg ${m.role === 'user' ? 'user' : 'bot'}`}>
              {m.content}
              {((m.tools && m.tools.length > 0) || m.mode === 'guardrail') && <div className="msg-meta">
                {m.tools?.map((x) => <span key={x} className="badge sky mono"><Icon name="tool" size={12} />{x}</span>)}
                {m.mode === 'guardrail' && <span className="badge warn"><Icon name="shield" size={12} />guardrail</span>}</div>}
            </div>
          ))}
          {busy && <div className="msg bot muted"><span className="spin" /></div>}
          <div ref={end} />
        </div>
        {msgs.length > 0 && <div className="chips" style={{ padding: '0 14px 10px' }}>{SUGGEST[lang].slice(0, 4).map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}</div>}
        <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(text) }}>
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t('chatPlaceholder')} aria-label={t('chatPlaceholder')} />
          <button className="btn primary" disabled={busy || !text.trim()} style={{ minHeight: 46 }}><Icon name="send" />{t('send')}</button>
        </form>
      </div>
    </div>
  )
}
