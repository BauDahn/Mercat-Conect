import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { ProductArt } from '../components/ProductArt'
import { OfferBadges, StateLine } from '../components/OfferCard'
import { ErrorBox, Notice, Spinner } from '../components/ui'
import { Icon } from '../components/Icon'
import { useI18n } from '../i18n'
import { useAuth } from '../state/auth'
import { useLive } from '../state/live'
import { useAsync, useOnline } from '../lib/hooks'
import { cardState } from '../lib/offers'
import { dateLong, distanceLabel, money, timeHM, uuid } from '../lib/format'

export function OfferPage() {
  const { id = '' } = useParams()
  const { t, lang } = useI18n()
  const { user, points } = useAuth()
  const nav = useNavigate()
  const online = useOnline()
  const [qty, setQty] = useState(1)
  // El coste y el máximo los calcula el servidor para la cantidad elegida (con debounce).
  const [qtyD, setQtyD] = useState(1)
  useEffect(() => {
    const h = window.setTimeout(() => setQtyD(qty), 350)
    return () => window.clearTimeout(h)
  }, [qty])
  const res = useAsync(() => api.getOffer(id, qtyD), [id, user?.id, qtyD])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<unknown>(null)
  const key = useRef<string | null>(null)

  useLive('offer.updated', (e) => {
    if ((e as { offer_id: string }).offer_id === id) res.reload()
  })
  useLive('reconnect', res.reload)

  if (res.loading) return <Spinner />
  if (res.error || !res.data) return <ErrorBox error={res.error} onRetry={res.reload} />
  const o = res.data
  const d = o.decision ?? null
  const state = cardState(o, user, d, points?.left ?? null)
  const maxQty = Math.max(1, Math.min(o.qty_available, d && d.max_units > 0 ? d.max_units : o.qty_available))
  const q = Math.min(Math.max(1, qty), maxQty)
  const canBuy = state.kind === 'ok' && online && qty === qtyD

  async function reserve() {
    setBusy(true)
    setErr(null)
    // Misma clave mientras se reintenta la misma petición; nueva si cambia el pedido.
    key.current ??= uuid()
    try {
      const order = await api.createOrder([{ offer_id: o.id, qty: q }], key.current)
      nav(`/pedidos/${order.id}`)
    } catch (e) {
      setErr(e)
      if (e instanceof ApiError) key.current = null
      res.reload()
    } finally {
      setBusy(false)
    }
  }

  const refrigerated = o.product.food_class === 'REFRIGERATED'
  const per = o.product.unit || ''
  return (
    <article className="space-y-4">
      <Link to="/" className="inline-flex min-h-11 items-center text-brand underline">&larr; {t('common.back')}</Link>
      <div className="card overflow-hidden">
        <ProductArt offer={o} className="h-40" />
        <div className="space-y-3 p-4">
          <OfferBadges o={o} />
          <h1 className="text-2xl font-bold">{o.product.name} · {o.stall.name}</h1>
          <p className="text-xl">
            <strong className="text-brand-dark">{money(o.price_cents, lang)}</strong> {per && <span>/ {per}</span>}{' '}
            {o.reference_price_cents ? <span className="text-muted">({t('offer.usualPrice')} <s>{money(o.reference_price_cents, lang)}</s>)</span> : null}
          </p>

          <section className="rounded-xl bg-brand-soft p-4" aria-labelledby="today-h">
            <h2 id="today-h" className="mb-2 font-bold">{t('offer.todayForYou')}</h2>
            {d ? (
              <ul className="space-y-1">
                <li>{t('offer.costFor', { n: d.points_cost, q: qtyD, unit: per })}</li>
                <li>{t('offer.maxPer', { n: d.max_units, unit: per })}</li>
                {d.reasons.length > 0 && (
                  <li>
                    <strong>{t('offer.reason')}</strong>{' '}
                    {d.reasons.map((r) => t(r, {}, t(`reasons.${r}`, {}, r))).join(' ')}
                  </li>
                )}
                {d.rules_applied.length > 0 && (
                  <li className="text-sm text-muted">
                    {t('offer.rules')}: {d.rules_applied.map((r) => t(`rules.${r}`, {}, r)).join(' · ')}
                  </li>
                )}
                {o.policy_profile && <li className="text-sm text-muted">{t('offer.profile')}: {t(`profile.${o.policy_profile}`)}</li>}
              </ul>
            ) : (
              <p>{t('offer.rulesNeedLogin')}</p>
            )}
          </section>

          <ul className="space-y-1 text-sm">
            <li className="flex items-center gap-2"><Icon name={refrigerated ? 'therm' : 'box'} className="h-4 w-4" />
              {t('offer.pickupPlace', { kind: refrigerated ? t('offer.lockerCold') : t('offer.lockerAmbient'), day: dateLong(o.pickup_from, lang), from: timeHM(o.pickup_from, lang), to: timeHM(o.pickup_until, lang) })}
            </li>
            {o.distance_m != null && (
              <li className="flex items-center gap-2"><Icon name="pin" className="h-4 w-4" />{t('offer.distance', { d: distanceLabel(o.distance_m, lang) })}</li>
            )}
            <li>{t('offer.allergens')}: {o.product.allergens?.length ? o.product.allergens.join(', ') : t('offer.noAllergens')} · {o.consume_by === 'TODAY' ? t('offer.consumeToday') : t('offer.bestBefore')}</li>
            <li>{t('offer.left', { n: o.effective_stock ?? o.qty_available, count: o.effective_stock ?? o.qty_available })}</li>
          </ul>

          <StateLine o={o} d={d} />
          {state.kind === 'unverified' && <Link className="btn btn-secondary" to="/verificar-edad">{t('age.cta')}</Link>}
          {state.kind === 'anon' && <Link className="btn btn-secondary" to="/entrar" state={{ from: `/oferta/${o.id}` }}>{t('auth.login')}</Link>}
          {!online && <Notice icon="wifi" tone="warn">{t('offline.noBuy')}</Notice>}
          {!!err && <ErrorBox error={err} />}

          <div className="flex flex-wrap items-end gap-3">
            <div>
              <span className="label" id="qty-l">{t('offer.qty')}</span>
              <div className="flex items-center gap-1" role="group" aria-labelledby="qty-l">
                <button className="btn btn-secondary" aria-label={t('offer.less')} disabled={q <= 1} onClick={() => { setQty(q - 1); key.current = null }}><Icon name="minus" /></button>
                <output className="w-12 text-center text-xl font-bold" aria-live="polite">{q}</output>
                <button className="btn btn-secondary" aria-label={t('offer.more')} disabled={q >= maxQty} onClick={() => { setQty(q + 1); key.current = null }}><Icon name="plus" /></button>
              </div>
            </div>
            <button className="btn btn-primary flex-1" disabled={!canBuy || busy} onClick={reserve}>
              {busy ? t('common.loading') : t('offer.reservePay')}
            </button>
          </div>
          {d && canBuy && (
            <p className="text-sm text-muted">{t('offer.total', { price: money(o.price_cents * q, lang), pts: d.points_cost })}</p>
          )}
          <p className="text-sm text-muted">{t('offer.serverRecalc')}</p>
        </div>
      </div>
    </article>
  )
}
