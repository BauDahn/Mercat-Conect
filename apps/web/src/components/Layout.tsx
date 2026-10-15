import { NavLink, Outlet, Link } from 'react-router-dom'
import { Icon, type IconName } from './Icon'
import { useI18n } from '../i18n'
import { useAuth } from '../state/auth'
import { useServerTime } from '../state/servertime'
import { useLive, useLiveConnected } from '../state/live'
import { useToast } from '../state/toast'
import { useOnline } from '../lib/hooks'
import type { Notification } from '../api/types'

export function Layout() {
  const { t, lang, setLang } = useI18n()
  const { user, points, refreshPoints } = useAuth()
  const { demoMode } = useServerTime()
  const online = useOnline()
  const live = useLiveConnected()
  const toast = useToast()

  useLive('notification.created', (d) => {
    const n = d as Notification
    const p = (n.payload ?? {}) as Record<string, unknown>
    const slot = p.slot ?? p.locker_slot ?? ''
    toast(t(`notif.${n.kind}`, { slot }, t('notif.generic')), 'info')
  })
  useLive('order.updated', () => void refreshPoints())

  const role = user?.role
  const links: { to: string; label: string; icon: IconName; show: boolean }[] = [
    { to: '/', label: t('nav.offers'), icon: 'home', show: true },
    { to: '/pedidos', label: t('nav.orders'), icon: 'bag', show: !!user },
    { to: '/puntos', label: t('nav.points'), icon: 'star', show: !!user },
    { to: '/productor/pedidos', label: t('nav.producer'), icon: 'store', show: role === 'PRODUCER' || role === 'ADMIN' },
    { to: '/admin', label: t('nav.admin'), icon: 'chart', show: role === 'MANAGER' || role === 'ADMIN' },
    { to: '/demo', label: t('nav.demo'), icon: 'flask', show: demoMode },
    { to: user ? '/perfil' : '/entrar', label: user ? t('nav.profile') : t('nav.login'), icon: 'user', show: true },
  ]

  return (
    <div className="mx-auto flex min-h-dvh max-w-3xl flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:p-3">{t('common.skip')}</a>
      <div className="bg-accent px-3 py-1.5 text-center text-sm font-bold tracking-wide text-white" role="note">
        {t('banner.demo')}
      </div>
      {!online && (
        <div role="alert" className="flex items-center justify-center gap-2 bg-ink px-3 py-2 text-sm text-white">
          <Icon name="wifi" className="h-4 w-4" /> {t('offline.banner')}
        </div>
      )}
      <header className="flex items-center justify-between gap-2 px-4 py-3">
        <Link to="/" className="flex min-h-12 items-center gap-2 text-xl font-bold text-brand">
          <Icon name="leaf" className="h-7 w-7" /> Mercat-Conect
        </Link>
        <div className="flex items-center gap-2">
          {user && points && (
            <Link to="/puntos" className="flex min-h-12 items-center gap-1 rounded-full bg-brand-soft px-3 font-bold text-brand-dark" aria-label={t('points.chipLabel', { n: points.left })}>
              <Icon name="star" className="h-5 w-5" /> {t('points.chip', { n: points.left })}
            </Link>
          )}
          {user && (
            <span className="sr-only" aria-live="polite">{live ? t('live.on') : t('live.off')}</span>
          )}
          <button
            className="btn btn-secondary !px-3"
            onClick={() => setLang(lang === 'es' ? 'va' : 'es')}
            aria-label={t('lang.switch')}
            lang={lang === 'es' ? 'ca' : 'es'}
          >
            <Icon name="globe" className="h-5 w-5" /> {lang === 'es' ? 'VA' : 'ES'}
          </button>
        </div>
      </header>
      <main id="main" className="flex-1 px-4 pb-28" tabIndex={-1}>
        <Outlet />
      </main>
      <nav aria-label={t('nav.main')} className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-white">
        <ul className="mx-auto flex max-w-3xl justify-around">
          {links.filter((l) => l.show).map((l) => (
            <li key={l.to} className="flex-1">
              <NavLink
                to={l.to}
                end={l.to === '/'}
                className={({ isActive }) =>
                  `flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 text-xs font-semibold ${isActive ? 'text-brand underline decoration-2 underline-offset-4' : 'text-muted'}`
                }
              >
                <Icon name={l.icon} className="h-6 w-6" />
                {l.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}
