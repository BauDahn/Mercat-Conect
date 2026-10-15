import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { PaymentIntent } from '../api/types'
import { ErrorBox, Notice, PageTitle, Spinner } from '../components/ui'
import { StatusBadge, orderTitle } from '../components/OrderBits'
import { Qr } from '../components/Qr'
import { Icon } from '../components/Icon'
import { useI18n } from '../i18n'
import { useAuth } from '../state/auth'
import { useServerTime } from '../state/servertime'
import { useLive } from '../state/live'
import { useAsync, useOnline } from '../lib/hooks'
import { dateTime, minutesLeft, money, timeHM } from '../lib/format'

export function OrdersPage() {
  const { t, lang } = useI18n()
  const res = useAsync(() => api.listOrders(), [])
  useLive('order.updated', res.reload)
  useLive('reconnect', res.reload)
  if (res.loading) return <Spinner />
  if (res.error) return <ErrorBox error={res.error} onRetry={res.reload} />
  const items = [...(res.data?.items ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at))
  return (
    <div>
      <PageTitle>{t('orders.title')}</PageTitle>
      {!items.length && <p className="card p-6 text-center text-muted">{t('orders.empty')}</p>}
      <ul className="space-y-3">
        {items.map((o) => (
          <li key={o.id}>
            <Link to={`/pedidos/${o.id}`} className="card block space-y-1 p-4">
              <div className="flex items-center justify-between gap-2">
                <StatusBadge s={o.status} />
                <span className="text-sm text-muted">{dateTime(o.created_at, lang)}</span>
              </div>
              <p className="font-bold">{orderTitle(o)}</p>
              <p className="text-sm text-muted">{o.stall?.name} · {money(o.total_cents, lang)} · {t('order.pts', { n: o.points_cost })}</p>
              {o.status === 'IN_LOCKER' && <p className="font-semibold text-brand">{t('order.inLockerShort', { slot: o.locker?.slot ?? '?' })}</p>}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function OrderPage() {
  const { id = '' } = useParams()
  const { t, lang } = useI18n()
  const { refreshPoints } = useAuth()
  const { demoMode, nowMs } = useServerTime()
  const online = useOnline()
  const res = useAsync(() => api.getOrder(id), [id])
  const [pay, setPay] = useState<PaymentIntent | null>(null)
  const [payErr, setPayErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const reload = res.reload
  useLive('order.updated', (e) => {
    if ((e as { order_id: string }).order_id === id) {
      reload()
      void refreshPoints()
    }
  })
  useLive('reconnect', reload)
  const status = res.data?.status
  // Respaldo si el SSE no llega: sondeo suave mientras el pedido está en curso.
  useEffect(() => {
    if (!status || !['HELD', 'PAID', 'PREPARING'].includes(status)) return
    const i = window.setInterval(reload, 8000)
    return () => window.clearInterval(i)
  }, [status, reload])

  if (res.loading) return <Spinner />
  if (res.error || !res.data) return <ErrorBox error={res.error} onRetry={res.reload} />
  const o = res.data

  async function doPay(simulate?: 'success' | 'failure' | 'delay') {
    setBusy(true)
    setPayErr(null)
    try {
      let sim = simulate
      try {
        if (!sim && demoMode && localStorage.getItem('mc_sim_pay') === 'failure') {
          sim = 'failure'
          localStorage.removeItem('mc_sim_pay') // un solo uso
        }
      } catch {
        /* sin almacenamiento */
      }
      setPay(await api.payOrder(o.id, demoMode ? sim : undefined))
      await refreshPoints()
    } catch (e) {
      setPayErr(e)
    } finally {
      setBusy(false)
      reload()
    }
  }

  const holdMin = o.hold_expires_at ? minutesLeft(o.hold_expires_at, nowMs()) : null
  return (
    <article className="space-y-4">
      <Link to="/pedidos" className="inline-flex min-h-11 items-center text-brand underline">&larr; {t('orders.title')}</Link>
      <div className="card space-y-3 p-4">
        <div className="flex items-center justify-between gap-2">
          <h1 className="text-xl font-bold">{t('order.title')}</h1>
          <StatusBadge s={o.status} />
        </div>
        <p>{t(`order.help.${o.status}`, {}, '')}</p>
        <ul className="divide-y divide-line">
          {o.items.map((i) => (
            <li key={i.offer_id} className="flex justify-between py-2">
              <span>{i.qty}× {i.product_name}</span>
              <span>{money(i.unit_cents * i.qty, lang)}</span>
            </li>
          ))}
        </ul>
        <p className="flex justify-between font-bold"><span>{t('order.total')}</span><span>{money(o.total_cents, lang)}</span></p>
        <p className="text-sm text-muted">{t('order.pts', { n: o.points_cost })} · {t('order.pickupUntil', { to: timeHM(o.pickup_until, lang) })}{o.stall ? ` · ${o.stall.name}` : ''}</p>
        {o.rules_applied.length > 0 && <p className="text-sm text-muted">{t('offer.rules')}: {o.rules_applied.map((r) => t(`rules.${r}`, {}, r)).join(' · ')}</p>}
      </div>

      {o.status === 'HELD' && (
        <section className="card space-y-3 p-4" aria-labelledby="pay-h">
          <h2 id="pay-h" className="text-lg font-bold">{t('pay.title')}</h2>
          {holdMin !== null && <Notice icon="clock" tone="warn">{holdMin > 0 ? t('pay.holdLeft', { n: holdMin }) : t('pay.holdExpiring')}</Notice>}
          {!online && <Notice icon="wifi" tone="warn">{t('offline.noBuy')}</Notice>}
          {!!payErr && <ErrorBox error={payErr} />}
          {pay?.status === 'FAILED' && <Notice icon="alert" tone="bad">{t('errors.payment_failed')}</Notice>}
          {pay?.status === 'PENDING' && <Notice icon="clock">{t('pay.pending')}</Notice>}
          {pay?.checkout_url && pay.status === 'PENDING' && <a className="btn btn-secondary" href={pay.checkout_url}>{t('pay.openCheckout')}</a>}
          <button className="btn btn-primary w-full" disabled={busy || !online} onClick={() => doPay('success')}>
            {t('pay.pay', { amount: money(o.total_cents, lang) })}
          </button>
          {demoMode && (
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-secondary" disabled={busy || !online} onClick={() => doPay('failure')}>{t('pay.simFail')}</button>
              <button className="btn btn-secondary" disabled={busy || !online} onClick={() => doPay('delay')}>{t('pay.simDelay')}</button>
            </div>
          )}
          <p className="text-sm text-muted">{t('pay.simNote')}</p>
        </section>
      )}

      {o.status === 'IN_LOCKER' && (
        <section className="card flex flex-col items-center gap-3 p-5 text-center" aria-labelledby="code-h">
          <h2 id="code-h" className="text-lg font-bold">{t('order.pickupCodeTitle')}</h2>
          <p className="flex items-center gap-2 font-semibold text-brand-dark">
            <Icon name="lock" /> {t('order.inLocker', { slot: o.locker?.slot ?? '?', market: o.locker?.market_name ?? '' })}
          </p>
          {o.pickup_code ? (
            <>
              <p className="font-mono text-4xl font-bold tracking-[.3em]" aria-label={t('order.codeAria', { code: o.pickup_code.split('').join(' ') })}>{o.pickup_code}</p>
              <Qr value={o.pickup_code} label={t('order.qrAlt')} />
            </>
          ) : (
            <Notice icon="info">{t('order.noCode')}</Notice>
          )}
          <p className="text-sm text-muted">{t('order.pickupUntil', { to: timeHM(o.pickup_until, lang) })}</p>
        </section>
      )}
    </article>
  )
}
