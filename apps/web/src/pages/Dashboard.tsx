import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Offer } from '../api/types'
import { OfferCard } from '../components/OfferCard'
import { Link } from 'react-router-dom'
import { Button, EmptyState, ErrorBox, Skeleton } from '../components/ui'
import { Icon } from '../components/Icon'
import { useI18n } from '../i18n'
import { useAuth } from '../state/auth'
import { useServerTime } from '../state/servertime'
import { useLive } from '../state/live'
import { useAsync } from '../lib/hooks'
import { inlineDecision } from '../lib/offers'
import { weekday } from '../lib/format'

const SORTS = ['closing_soon', 'savings', 'price_asc', 'price_desc', 'newest', 'distance'] as const
type Sort = (typeof SORTS)[number]

function useDebounced<T>(v: T, ms: number): T {
  const [x, setX] = useState(v)
  useEffect(() => {
    const id = window.setTimeout(() => setX(v), ms)
    return () => window.clearTimeout(id)
  }, [v, ms])
  return x
}

export function Dashboard() {
  const { t, lang } = useI18n()
  const { user, points } = useAuth()
  const { nowMs } = useServerTime()
  const [market, setMarket] = useState('')
  const [category, setCategory] = useState('')
  const [sort, setSort] = useState<Sort>('closing_soon')
  const [qText, setQText] = useState('')
  const [allergen, setAllergen] = useState('')
  const [nowOnly, setNowOnly] = useState(false)
  const [maxPrice, setMaxPrice] = useState('')
  const q = useDebounced(qText.trim(), 300)

  const serverSort = sort === 'savings' ? 'closing_soon' : sort
  const res = useAsync(() => api.listOffers({ market: market || undefined, sort: serverSort, q: q || undefined }), [market, serverSort, q, user?.id])

  const [items, setItems] = useState<Offer[]>([])
  useEffect(() => {
    if (res.data) setItems(res.data.items)
  }, [res.data])

  // Listas de filtros acumuladas (el filtro de mercado reduce el listado).
  const [markets, setMarkets] = useState<Record<string, string>>({})
  const [categories, setCategories] = useState<string[]>([])
  useEffect(() => {
    if (!items.length) return
    setMarkets((m) => {
      const n = { ...m }
      for (const o of items) n[o.stall.market_id] = o.stall.market_name ?? n[o.stall.market_id] ?? o.stall.market_id.slice(0, 8)
      return n
    })
    setCategories((c) => Array.from(new Set([...c, ...items.map((o) => o.stall.category)])).sort())
  }, [items])

  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])
  // GET /offers trae `decision` por oferta cuando hay sesión.
  const decisions = useMemo(() => Object.fromEntries(items.map((o) => [o.id, inlineDecision(o)])), [items])

  useLive('offer.updated', (e) => {
    const ev = e as { offer_id: string; qty_available: number; status: Offer['status']; price_cents?: number }
    setItems((l) =>
      l.map((o) =>
        o.id === ev.offer_id
          ? { ...o, qty_available: ev.qty_available, status: ev.status, price_cents: ev.price_cents ?? o.price_cents, effective_stock: o.effective_stock === undefined ? undefined : Math.min(o.effective_stock, ev.qty_available) }
          : o,
      ),
    )
    // el coste en puntos puede haber cambiado: recarga agrupada
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(res.reload, 800)
  })
  useLive('reconnect', () => {
    res.reload()
  })

  const allergens = useMemo(() => Array.from(new Set(items.flatMap((o) => o.product.allergens ?? []))).sort(), [items])

  const now = nowMs()
  const visible = useMemo(() => {
    const maxCents = maxPrice ? Math.round(parseFloat(maxPrice.replace(',', '.')) * 100) : null
    let l = items.filter((o) => !category || o.stall.category === category)
    if (allergen) l = l.filter((o) => !(o.product.allergens ?? []).includes(allergen))
    if (nowOnly) l = l.filter((o) => new Date(o.pickup_from).getTime() <= now && now <= new Date(o.pickup_until).getTime())
    if (maxCents !== null && !Number.isNaN(maxCents)) l = l.filter((o) => o.price_cents <= maxCents)
    if (sort === 'savings') {
      const save = (o: Offer) => (o.reference_price_cents ?? o.price_cents) - o.price_cents
      l = [...l].sort((a, b) => save(b) - save(a))
    }
    const out = (o: Offer) => (o.qty_available <= 0 || o.status === 'SOLD_OUT' ? 1 : 0)
    return [...l].sort((a, b) => out(a) - out(b)) // agotadas al final (orden estable)
  }, [items, category, allergen, nowOnly, maxPrice, sort, now])

  const closing = useMemo(
    () =>
      visible
        .filter((o) => o.qty_available > 0 && new Date(o.pickup_until).getTime() > now)
        .sort((a, b) => new Date(a.pickup_until).getTime() - new Date(b.pickup_until).getTime())
        .slice(0, 6),
    [visible, now],
  )

  const anon = !user
  const pointsLeft = points?.left ?? 0
  const allowance = points?.allowance ?? 0
  const pct = allowance > 0 ? Math.min(100, Math.round((pointsLeft / allowance) * 100)) : 0
  const verifyPending = !!user && (!user.age_verified || user.status === 'PENDING')

  return (
    <div className="space-y-8">
      {anon && <AnonHero />}

      {user && (
        <section aria-labelledby="hello-h" className="grid gap-4 lg:grid-cols-[1fr_minmax(0,22rem)] lg:items-stretch">
          <div className="space-y-1 pt-2">
            <p className="text-sm font-bold uppercase tracking-wide text-muted">{t('ui.today')}</p>
            <h1 id="hello-h" className="text-3xl font-extrabold leading-tight sm:text-4xl">{t('ui.hi', { name: user.display_name.split(' ')[0] })}</h1>
            <p className="text-muted">{t('ui.heroSubUser')}</p>
          </div>
          <div className="card flex flex-col justify-between gap-3 bg-brand-soft p-5 shadow-none">
            <div className="flex items-baseline justify-between gap-2">
              <p className="font-bold text-brand-dark">{t('ui.balance')}</p>
              <p className="text-3xl font-extrabold tabular-nums text-brand-dark">{pointsLeft}<span className="text-lg text-muted">/{allowance}</span></p>
            </div>
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={allowance}
              aria-valuenow={pointsLeft}
              aria-label={t('ui.balance')}
              className="h-3 w-full overflow-hidden rounded-full bg-white"
            >
              <div className="h-full rounded-full bg-brand transition-[width] duration-500" style={{ width: `${pct}%` }} />
            </div>
            <p className="text-sm font-semibold text-brand-dark">
              {points ? t('ui.pointsRenew', { day: weekday(points.renews_at, lang) }) : ''}
            </p>
          </div>
        </section>
      )}

      {verifyPending && (
        <section role="region" aria-label={t('ui.verifyTitle')} className="flex flex-col gap-3 rounded-2xl border-2 border-accent bg-accent-soft p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white text-accent"><Icon name="alert" className="h-6 w-6" /></span>
            <div>
              <p className="text-lg font-extrabold text-accent">{t('ui.verifyTitle')}</p>
              <p className="text-ink">{t('ui.verifySub')}</p>
            </div>
          </div>
          <Link to="/verificar-edad" className="btn btn-accent shrink-0">{t('ui.verifyCta')}</Link>
        </section>
      )}

      <section aria-label={t('dash.filters')} className="space-y-3">
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,14rem)]">
          <div className="relative">
            <Icon name="search" className="pointer-events-none absolute left-3 top-3.5 h-5 w-5 text-muted" />
            <input type="search" className="input !pl-10" placeholder={t('dash.search')} aria-label={t('dash.search')} value={qText} onChange={(e) => setQText(e.target.value)} />
          </div>
          <select className="input font-semibold" value={market} onChange={(e) => setMarket(e.target.value)} aria-label={t('dash.market')}>
            <option value="">{t('dash.allMarkets')}</option>
            {Object.entries(markets).map(([id, name]) => (
              <option key={id} value={id}>{name}</option>
            ))}
          </select>
        </div>
        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 lg:mx-0 lg:px-0" role="group" aria-label={t('dash.categories')}>
          <button className="chip" aria-pressed={category === ''} onClick={() => setCategory('')}>{t('dash.all')}</button>
          {categories.map((c) => (
            <button key={c} className="chip" aria-pressed={category === c} onClick={() => setCategory(c)}>{c}</button>
          ))}
        </div>
        <details className="card p-4">
          <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between font-bold">
            {t('dash.moreFilters')}
            <Icon name="plus" className="h-5 w-5" />
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <label>
              <span className="label">{t('dash.noAllergen')}</span>
              <select className="input" value={allergen} onChange={(e) => setAllergen(e.target.value)}>
                <option value="">{t('dash.any')}</option>
                {allergens.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </label>
            <label>
              <span className="label">{t('dash.maxPrice')}</span>
              <input className="input" inputMode="decimal" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} placeholder="5,00" />
            </label>
            <label className="flex min-h-12 items-center gap-3 self-end font-semibold">
              <input type="checkbox" className="h-6 w-6 accent-[var(--color-brand)]" checked={nowOnly} onChange={(e) => setNowOnly(e.target.checked)} />
              {t('dash.pickupNow')}
            </label>
          </div>
        </details>
      </section>

      {!!res.error && <ErrorBox error={res.error} onRetry={res.reload} />}

      {res.loading && !items.length && (
        <section aria-busy="true" className="space-y-4">
          <Skeleton count={3} compact />
        </section>
      )}

      {closing.length > 0 && (
        <section aria-labelledby="closing-h" className="space-y-3">
          <div className="flex items-end justify-between gap-3">
            <h2 id="closing-h" className="text-2xl font-extrabold">{t('dash.closingSoon')}</h2>
            <p className="hidden text-sm font-semibold text-muted sm:block">{t('ui.swipeHint')}</p>
          </div>
          <div className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-3 lg:mx-0 lg:px-0">
            {closing.map((o) => <OfferCard key={o.id} o={o} d={decisions[o.id]} compact />)}
          </div>
        </section>
      )}

      <section aria-labelledby="near-h" className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 id="near-h" className="text-2xl font-extrabold">{t('dash.nearYou')}</h2>
            {!res.loading && <p className="text-sm font-semibold text-muted">{t('ui.offersCount', { n: visible.length, count: visible.length })}</p>}
          </div>
          <label className="flex items-center gap-2 text-sm font-bold">
            <span className="shrink-0">{t('dash.sortBy')}</span>
            <select className="input !w-auto min-w-48" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              {SORTS.map((s) => <option key={s} value={s}>{t(`dash.sort.${s}`)}</option>)}
            </select>
          </label>
        </div>
        {!res.loading && !visible.length && !res.error && (
          <EmptyState icon="basket" title={t('ui.emptyTitle')} action={category || q || market ? <Button variant="secondary" onClick={() => { setCategory(''); setQText(''); setMarket('') }}>{t('ui.clearFilters')}</Button> : undefined}>
            {t('ui.emptySub')}
          </EmptyState>
        )}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {visible.map((o) => <OfferCard key={o.id} o={o} d={decisions[o.id]} />)}
        </div>
      </section>
    </div>
  )
}

/** Portada para visitantes: qué es y la elección entre cliente y productor. */
function AnonHero() {
  const { t } = useI18n()
  return (
    <section aria-labelledby="hero-h" className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand to-brand-dark p-6 text-white shadow-[var(--shadow-lift)] sm:p-10">
        <p className="mb-2 inline-flex rounded-full bg-white/15 px-3 py-1 text-sm font-bold">{t('ui.heroKicker')}</p>
        <h1 id="hero-h" className="text-3xl font-extrabold leading-tight sm:text-5xl">{t('ui.heroTitle')}</h1>
        <p className="mt-3 max-w-xl text-base text-white/90 sm:text-lg">{t('ui.heroSub')}</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/registro" className="btn btn-accent">{t('ui.signup')}</Link>
          <Link to="/entrar" className="btn border-2 border-white bg-transparent text-white hover:bg-white/10">{t('ui.enter')}</Link>
        </div>
      </div>
      <div className="grid gap-4">
        <Link to="/registro" className="card group flex items-center gap-4 p-5 transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)]">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-accent-soft text-3xl" aria-hidden="true">🛍️</span>
          <span>
            <span className="block text-lg font-extrabold">{t('ui.chooseCustomer')}</span>
            <span className="text-sm text-muted">{t('ui.chooseCustomerSub')}</span>
          </span>
        </Link>
        <Link to="/entrar" className="card group flex items-center gap-4 p-5 transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)]">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-brand-soft text-3xl" aria-hidden="true">🧑‍🌾</span>
          <span>
            <span className="block text-lg font-extrabold">{t('ui.chooseBusiness')}</span>
            <span className="text-sm text-muted">{t('ui.chooseBusinessSub')}</span>
          </span>
        </Link>
      </div>
    </section>
  )
}
