import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, Link } from 'react-router-dom'
import { Icon, type IconName } from './Icon'
import { useI18n } from '../i18n'
import { useAuth } from '../state/auth'
import { useServerTime } from '../state/servertime'
import { useLive, useLiveConnected } from '../state/live'
import { useToast } from '../state/toast'
import { useOnline } from '../lib/hooks'
import type { Notification } from '../api/types'

interface NavItem { to: string; label: string; icon: IconName }

/** Navegación por rol (§6.1). Las herramientas de demo NO van aquí: van en el botón flotante. */
function navFor(role: string | undefined, t: (k: string) => string): NavItem[] {
  if (!role) return [
    { to: '/', label: t('nav.offers'), icon: 'home' },
    { to: '/entrar', label: t('nav.login'), icon: 'user' },
  ]
  if (role === 'PRODUCER') return [
    { to: '/productor', label: t('nav.panel'), icon: 'home' },
    { to: '/productor/publicar', label: t('nav.publish'), icon: 'plus' },
    { to: '/productor/pedidos', label: t('nav.orders'), icon: 'bag' },
    { to: '/productor/ofertas', label: t('nav.myOffers'), icon: 'box' },
    { to: '/productor/liquidaciones', label: t('nav.payouts'), icon: 'euro' },
  ]
  if (role === 'MANAGER' || role === 'ADMIN') return [
    { to: '/admin', label: t('nav.impact'), icon: 'chart' },
    { to: '/admin/puestos', label: t('nav.stalls'), icon: 'store' },
    { to: '/admin/donaciones', label: t('nav.donations'), icon: 'therm' },
    { to: '/admin/calidad', label: t('nav.quality'), icon: 'check' },
    { to: '/admin/barandillas', label: t('nav.guardrails'), icon: 'lock' },
  ]
  return [
    { to: '/', label: t('nav.offers'), icon: 'home' },
    { to: '/pedidos', label: t('nav.orders'), icon: 'bag' },
    { to: '/puntos', label: t('nav.points'), icon: 'star' },
    { to: '/perfil', label: t('nav.profile'), icon: 'user' },
  ]
}

function NavList({ items, variant }: { items: NavItem[]; variant: 'bottom' | 'side' }) {
  return (
    <ul className={variant === 'bottom' ? 'mx-auto flex max-w-xl justify-around' : 'flex flex-col gap-1'}>
      {items.map((l) => (
        <li key={l.to} className={variant === 'bottom' ? 'flex-1' : ''}>
          <NavLink
            to={l.to}
            end={l.to === '/' || l.to === '/productor' || l.to === '/admin'}
            className={({ isActive }) =>
              variant === 'bottom'
                ? `flex min-h-14 flex-col items-center justify-center gap-0.5 rounded-xl px-1 text-xs font-semibold ${isActive ? 'text-brand-dark' : 'text-muted'}`
                : `flex min-h-12 items-center gap-3 rounded-xl px-3 font-semibold ${isActive ? 'bg-brand-soft text-brand-dark' : 'text-ink hover:bg-paper-2'}`
            }
          >
            {({ isActive }) => (
              <>
                <span className={variant === 'bottom' && isActive ? 'rounded-full bg-brand-soft px-4 py-1' : ''}>
                  <Icon name={l.icon} className={variant === 'bottom' ? 'h-6 w-6' : 'h-5 w-5'} />
                </span>
                <span className={variant === 'bottom' ? 'text-[11px] leading-tight' : ''}>{l.label}</span>
              </>
            )}
          </NavLink>
        </li>
      ))}
    </ul>
  )
}

/** Botón flotante discreto que abre las herramientas de demo (fuera de la navegación principal). */
function DemoTools() {
  const { t } = useI18n()
  const { demoMode } = useServerTime()
  const [open, setOpen] = useState(false)
  const btn = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])
  if (!demoMode) return null
  return (
    <div className="fixed bottom-20 right-4 z-40 lg:bottom-6 lg:right-6">
      {open && (
        <div role="dialog" aria-label={t('demo.tools')} className="card mb-3 w-64 p-3 shadow-[var(--shadow-lift)]">
          <p className="mb-2 px-1 text-sm font-bold text-muted">{t('demo.tools')}</p>
          <Link to="/demo" onClick={() => setOpen(false)} className="flex min-h-12 items-center gap-3 rounded-xl px-3 font-semibold hover:bg-paper-2">
            <Icon name="play" className="h-5 w-5" /> {t('demo.clock')}
          </Link>
          <Link to="/sim/taquillas" onClick={() => setOpen(false)} className="flex min-h-12 items-center gap-3 rounded-xl px-3 font-semibold hover:bg-paper-2">
            <Icon name="box" className="h-5 w-5" /> {t('demo.lockers')}
          </Link>
        </div>
      )}
      <button
        ref={btn}
        aria-label={t('demo.tools')}
        className="btn btn-ghost !min-h-12 border border-line bg-white shadow-[var(--shadow-soft)]"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <Icon name="tool" className="h-5 w-5" /> <span className="hidden sm:inline">{t('demo.tools')}</span>
      </button>
    </div>
  )
}

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

  const items = navFor(user?.role, t)
  const neighbor = !!user && user.role === 'NEIGHBOR'

  return (
    <div className="min-h-dvh">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:p-3">{t('common.skip')}</a>

      {/* Banner DEMO fino */}
      <div className="sticky top-0 z-50 bg-accent px-3 py-1 text-center text-xs font-bold tracking-wide text-white lg:fixed lg:inset-x-0 lg:top-0 lg:z-50" role="note">
        {t('banner.demo')}
      </div>
      {!online && (
        <div role="alert" className="flex items-center justify-center gap-2 bg-ink px-3 py-2 text-sm text-white">
          <Icon name="wifi" className="h-4 w-4" /> {t('offline.banner')}
        </div>
      )}

      {/* Navegación lateral (escritorio) */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col gap-6 border-r border-line bg-white px-4 pb-6 pt-12 lg:flex">
        <Link to="/" className="flex min-h-12 items-center gap-2 whitespace-nowrap px-3 text-xl font-extrabold text-brand-dark">
          <Icon name="leaf" className="h-7 w-7" /> Mercat-Conect
        </Link>
        {neighbor && points && (
          <Link to="/puntos" className="card mx-1 block bg-brand-soft p-4 shadow-none">
            <p className="text-sm font-semibold text-brand-dark">{t('points.label')}</p>
            <p className="text-3xl font-extrabold text-brand-dark tabular-nums">{t('points.chip', { n: points.left })}</p>
          </Link>
        )}
        <nav aria-label={t('nav.main')} className="flex-1">
          <NavList items={items} variant="side" />
        </nav>
        <div className="flex items-center justify-between gap-2 border-t border-line pt-4">
          <button className="btn btn-ghost !px-3" onClick={() => setLang(lang === 'es' ? 'va' : 'es')} aria-label={t('lang.switch')} lang={lang === 'es' ? 'ca' : 'es'}>
            <Icon name="globe" className="h-5 w-5" /> {lang === 'es' ? 'Valencià' : 'Castellano'}
          </button>
          {user && <span className="sr-only" aria-live="polite">{live ? t('live.on') : t('live.off')}</span>}
        </div>
      </aside>

      <div className="flex min-h-dvh flex-col lg:pl-64">
        {/* Cabecera móvil */}
        <header className="flex items-center justify-between gap-2 border-b border-line bg-paper/95 px-4 py-3 backdrop-blur lg:hidden">
          <Link to="/" className="flex min-h-12 items-center gap-2 whitespace-nowrap text-lg font-extrabold text-brand-dark">
            <Icon name="leaf" className="h-7 w-7" /> Mercat-Conect
          </Link>
          <div className="flex items-center gap-2">
            {neighbor && points && (
              <Link to="/puntos" className="flex min-h-11 items-center gap-1 whitespace-nowrap rounded-full bg-brand-soft px-3 font-bold text-brand-dark" aria-label={t('points.chipLabel', { n: points.left })}>
                <Icon name="star" className="h-5 w-5" /> {t('points.chip', { n: points.left })}
              </Link>
            )}
            <button className="btn btn-ghost !min-h-11 !min-w-11 !px-2" onClick={() => setLang(lang === 'es' ? 'va' : 'es')} aria-label={t('lang.switch')} lang={lang === 'es' ? 'ca' : 'es'}>
              <Icon name="globe" className="h-5 w-5" /> <span className="text-sm">{lang === 'es' ? 'VA' : 'ES'}</span>
            </button>
          </div>
        </header>

        <main id="main" tabIndex={-1} className={`mx-auto w-full max-w-[1200px] flex-1 px-4 pt-4 focus:outline-none lg:px-8 lg:pt-14 ${demoMode ? '' : ''} pb-28 lg:pb-12`}>
          <Outlet />
          <p className="mt-10 text-xs text-muted">{t('ui.credits')}</p>
        </main>
      </div>

      {/* Barra inferior (móvil) */}
      <nav aria-label={t('nav.main')} className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-white/95 pb-[env(safe-area-inset-bottom)] shadow-[0_-4px_16px_rgb(30_38_32/0.06)] backdrop-blur lg:hidden">
        <NavList items={items} variant="bottom" />
      </nav>

      <DemoTools />
    </div>
  )
}
