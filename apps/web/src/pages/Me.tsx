import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { ErrorBox, Notice, PageTitle, Spinner } from '../components/ui'
import { Icon } from '../components/Icon'
import { useI18n } from '../i18n'
import { useAuth } from '../state/auth'
import { useLive } from '../state/live'
import { useAsync } from '../lib/hooks'
import { dateLong, dateTime } from '../lib/format'

export function PointsPage() {
  const { t, lang } = useI18n()
  const { points, refreshPoints } = useAuth()
  useLive('order.updated', () => void refreshPoints())
  if (!points) return <Spinner />
  const pct = points.allowance ? Math.round((points.left / points.allowance) * 100) : 0
  return (
    <div className="space-y-4">
      <PageTitle>{t('points.title')}</PageTitle>
      <div className="card space-y-3 p-5">
        <p className="text-4xl font-bold text-brand-dark">{t('points.leftOf', { left: points.left, total: points.allowance })}</p>
        <div className="h-4 overflow-hidden rounded-full bg-brand-soft" role="progressbar" aria-valuemin={0} aria-valuemax={points.allowance} aria-valuenow={points.left} aria-label={t('points.title')}>
          <div className="h-full bg-brand" style={{ width: `${pct}%` }} />
        </div>
        <p>{t('points.spent', { n: points.spent })}</p>
        <p>{t('points.renews', { date: dateLong(points.renews_at, lang) })}</p>
        <p className="text-sm text-muted">{t('points.explain')}</p>
      </div>
    </div>
  )
}

export function ProfilePage() {
  const { t, lang, setLang } = useI18n()
  const { user, logout, setUser } = useAuth()
  const nav = useNavigate()
  const res = useAsync(() => api.notifications(), [])
  useLive('notification.created', res.reload)
  const [confirmDel, setConfirmDel] = useState(false)
  const [delErr, setDelErr] = useState<unknown>(null)
  async function del() {
    setDelErr(null)
    try {
      await api.deleteMe()
      setUser(null)
      nav('/')
    } catch (e) {
      setDelErr(e)
    }
  }
  if (!user) return null
  return (
    <div className="space-y-4">
      <PageTitle sub={user.email}>{user.display_name}</PageTitle>
      <div className="card space-y-3 p-4">
        <p>{t('profile.role')}: <strong>{t(`role.${user.role}`)}</strong></p>
        <p className="flex items-center gap-2">
          <Icon name={user.age_verified ? 'check' : 'alert'} className="h-5 w-5" />
          {user.age_verified ? t('profile.ageOk') : t('profile.agePending')}
        </p>
        {!user.age_verified && <Link className="btn btn-primary" to="/verificar-edad">{t('age.cta')}</Link>}
        <div>
          <span className="label" id="lang-l">{t('profile.language')}</span>
          <div className="flex gap-2" role="group" aria-labelledby="lang-l">
            <button className="chip" aria-pressed={lang === 'es'} onClick={() => setLang('es')}>Castellano</button>
            <button className="chip" aria-pressed={lang === 'va'} onClick={() => setLang('va')}>Valencià</button>
          </div>
        </div>
        <button className="btn btn-danger" onClick={async () => { await logout(); nav('/') }}>
          <Icon name="logout" /> {t('auth.logout')}
        </button>
        <div className="space-y-2 border-t border-line pt-3">
          {!!delErr && (delErr instanceof ApiError && delErr.status === 409 ? <Notice icon="alert" tone="warn">{t('profile.delBusy')}</Notice> : <ErrorBox error={delErr} />)}
          {confirmDel ? (
            <>
              <Notice icon="alert" tone="bad">{t('profile.delWarn')}</Notice>
              <div className="flex gap-2">
                <button className="btn btn-danger" onClick={del}><Icon name="trash" /> {t('profile.delConfirm')}</button>
                <button className="btn btn-secondary" onClick={() => setConfirmDel(false)}>{t('common.cancel')}</button>
              </div>
            </>
          ) : (
            <button className="btn btn-danger" onClick={() => setConfirmDel(true)}><Icon name="trash" /> {t('profile.delAcc')}</button>
          )}
        </div>
      </div>
      <section aria-labelledby="notif-h">
        <h2 id="notif-h" className="mb-2 text-xl font-bold">{t('notif.title')}</h2>
        {res.loading && <Spinner />}
        {!!res.error && <ErrorBox error={res.error} onRetry={res.reload} />}
        {res.data && !res.data.items.length && <Notice>{t('notif.empty')}</Notice>}
        <ul className="space-y-2">
          {res.data?.items.map((n) => {
            const p = n.payload as Record<string, unknown>
            return (
              <li key={n.id} className="card flex items-start gap-3 p-3">
                <Icon name="bell" className="mt-1 h-5 w-5 shrink-0 text-brand" />
                <div>
                  <p className={n.read_at ? '' : 'font-bold'}>{t(`notif.${n.kind}`, { slot: p.slot ?? p.locker_slot ?? '' }, t('notif.generic'))}</p>
                  <p className="text-sm text-muted">{dateTime(n.created_at, lang)}</p>
                </div>
              </li>
            )
          })}
        </ul>
      </section>
    </div>
  )
}
