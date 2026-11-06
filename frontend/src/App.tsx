import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { api, DEMO, getToken, setToken, type SystemInfo, type User } from './api'
import { useI18n, type Key } from './i18n'
import { Contours, Icon, type IconName } from './components/Icon'
import LoginPage from './pages/Login'
import ProfilePage from './pages/Profile'
import GapPage from './pages/Gap'
import CareerPage from './pages/Career'
import IdpPage from './pages/Idp'
import ChatPage from './pages/Chat'
import TeamPage from './pages/Team'
import EmployeeDetail from './pages/EmployeeDetail'
import HeatmapPage from './pages/Heatmap'
import OverviewPage from './pages/Overview'
import RolesPage from './pages/Roles'
import CoursesPage from './pages/Courses'
import AuditPage from './pages/Audit'
import AboutPage from './pages/About'

interface AuthCtx { user: User | null; system: SystemInfo | null; setUser: (u: User | null) => void }
const Auth = createContext<AuthCtx>({ user: null, system: null, setUser: () => {} })
export const useAuth = () => useContext(Auth)

const NAV: Record<User['role'], { to: string; k: Key; icon: IconName }[]> = {
  employee: [
    { to: '/profile', k: 'navProfile', icon: 'user' }, { to: '/gap', k: 'navGap', icon: 'target' },
    { to: '/career', k: 'navCareer', icon: 'compass' }, { to: '/idp', k: 'navIdp', icon: 'calendar' }, { to: '/chat', k: 'navChat', icon: 'bot' },
  ],
  manager: [{ to: '/team', k: 'navTeam', icon: 'users' }, { to: '/heatmap', k: 'navHeatmap', icon: 'grid' }],
  hr: [
    { to: '/overview', k: 'navOverview', icon: 'chart' }, { to: '/team', k: 'navTeam', icon: 'users' }, { to: '/heatmap', k: 'navHeatmap', icon: 'grid' },
    { to: '/roles', k: 'navRoles', icon: 'puzzle' }, { to: '/courses', k: 'navCourses', icon: 'book' }, { to: '/audit', k: 'navAudit', icon: 'file' },
  ],
}
const HOME: Record<User['role'], string> = { employee: '/profile', manager: '/team', hr: '/overview' }

export function LangSwitch() {
  const { lang, setLang } = useI18n()
  return (
    <span className="lang-switch">
      <button className={lang === 'kk' ? 'on' : ''} onClick={() => setLang('kk')}>ҚАЗ</button>
      <button className={lang === 'ru' ? 'on' : ''} onClick={() => setLang('ru')}>РУС</button>
    </span>
  )
}

export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 34 34" aria-hidden="true">
      <rect width="34" height="34" rx="10" fill="#e3a127" />
      <path d="M8 24 L14 16 L19 20 L26 10" stroke="#0c2136" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="8" cy="24" r="2.4" fill="#0c2136" /><circle cx="26" cy="10" r="3" fill="#fff" stroke="#0c2136" strokeWidth="2" />
    </svg>
  )
}

function ModeBadge({ system }: { system: SystemInfo | null }) {
  const { t } = useI18n()
  if (DEMO) return <span className="badge accent"><span className="d" />{t('modeDemo')}</span>
  if (!system) return null
  return system.llm_enabled ? <span className="badge ok"><span className="d" />{t('modeLLM')}: {system.llm_model}</span>
    : <span className="badge info"><span className="d" />{t('modeOffline')}</span>
}

function initials(name: string) { return name.split(/\s+/).map((w) => w[0]).filter(Boolean).slice(0, 2).join('').toUpperCase() }

function Shell({ user, system, onLogout }: { user: User; system: SystemInfo | null; onLogout: () => void }) {
  const { t } = useI18n()
  const nav = [...NAV[user.role], { to: '/about', k: 'navAbout' as Key, icon: 'info' as IconName }]
  const roleName = user.role === 'employee' ? t('roleEmployee') : user.role === 'manager' ? t('roleManager') : t('roleHr')
  return (
    <div className="layout">
      <a className="skip" href="#main">Skip to content</a>
      <aside className="sidebar on-ink" aria-label="Navigation">
        <Contours className="contours" opacity={0.22} />
        <div className="brand"><Logo /><div><div className="brand-name">Career Quest</div><div className="brand-sub">AI-бағыттаушы · ESCO</div></div></div>
        <div className="nav-group">{roleName}</div>
        <nav className="nav">{nav.map((n) => <NavLink key={n.to} to={n.to}><Icon name={n.icon} />{t(n.k)}</NavLink>)}</nav>
        <div className="sidebar-foot">
          <div className="who"><span className="avatar">{initials(user.display_name)}</span><div><b>{user.display_name}</b><span>{user.username}</span></div></div>
          <div className="row" style={{ gap: 8 }}><LangSwitch /><div className="spacer" />
            <button className="btn-ghost-ink" onClick={onLogout}><Icon name="logout" size={15} />{t('logout')}</button></div>
        </div>
      </aside>
      <div style={{ minWidth: 0 }}>
        <div className="mobile-bar on-ink"><Logo size={28} /><b style={{ fontFamily: 'var(--font-display)' }}>Career Quest</b><div className="spacer" /><LangSwitch />
          <button className="btn-ghost-ink" onClick={onLogout} aria-label={t('logout')}><Icon name="logout" size={15} /></button></div>
        <nav className="mobile-nav">{nav.map((n) => <NavLink key={n.to} to={n.to}><Icon name={n.icon} size={15} />{t(n.k)}</NavLink>)}</nav>
        <main className="main" id="main">
          <div className="topbar">
            <div className="crumb"><span className="dot" />{t('appTagline')}</div>
            <div className="row" style={{ gap: 8 }}><ModeBadge system={system} /><span className="badge">{roleName}</span></div>
          </div>
          {DEMO && <div className="notice" style={{ marginBottom: 20 }}><Icon name="info" />{t('demoNote')}</div>}
          <Routes>
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/gap" element={<GapPage />} />
            <Route path="/career" element={<CareerPage />} />
            <Route path="/idp" element={<IdpPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/team" element={<TeamPage />} />
            <Route path="/team/:id" element={<EmployeeDetail />} />
            <Route path="/heatmap" element={<HeatmapPage />} />
            <Route path="/overview" element={<OverviewPage />} />
            <Route path="/roles" element={<RolesPage />} />
            <Route path="/courses" element={<CoursesPage />} />
            <Route path="/audit" element={<AuditPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="*" element={<Navigate to={HOME[user.role]} replace />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [system, setSystem] = useState<SystemInfo | null>(null)
  const [ready, setReady] = useState(false)
  const nav = useNavigate()
  useEffect(() => {
    if (!getToken()) { setReady(true); return }
    api<User>('/api/auth/me').then(setUser).catch(() => setToken(null)).finally(() => setReady(true))
  }, [])
  useEffect(() => { if (user) api<SystemInfo>('/api/system').then(setSystem).catch(() => {}) }, [user])
  if (!ready) return null
  const logout = () => { setToken(null); setUser(null); nav('/') }
  return (
    <Auth.Provider value={{ user, system, setUser }}>
      {user ? <Shell user={user} system={system} onLogout={logout} />
        : <LoginPage onLogin={(u) => { setUser(u); nav(HOME[u.role]) }} />}
    </Auth.Provider>
  )
}
