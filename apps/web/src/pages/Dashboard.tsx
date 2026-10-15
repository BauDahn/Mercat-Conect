import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Offer } from '../api/types'
import { OfferCard } from '../components/OfferCard'
import { ErrorBox, Spinner } from '../components/ui'
import { Icon } from '../components/Icon'
import { useI18n } from '../i18n'
import { useAuth } from '../state/auth'
import { useServerTime } from '../state/servertime'
import { useLive } from '../state/live'
import { useAsync } from '../lib/hooks'
import { inlineDecision } from '../lib/offers'

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
  const { t } = useI18n()
  const { user } = useAuth()
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

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        <select className="input font-semibold" value={market} onChange={(e) => setMarket(e.target.value)} aria-label={t('dash.market')}>
          <option value="">{t('dash.allMarkets')}</option>
          {Object.entries(markets).map(([id, name]) => (
            <option key={id} value={id}>{name}</option>
          ))}
        </select>
        <div className="relative">
          <Icon name="search" className="pointer-events-none absolute left-3 top-3.5 h-5 w-5 text-muted" />
          <input type="search" className="input !pl-10" placeholder={t('dash.search')} aria-label={t('dash.search')} value={qText} onChange={(e) => setQText(e.target.value)} />
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1" role="group" aria-label={t('dash.categories')}>
          <button className="chip" aria-pressed={category === ''} onClick={() => setCategory('')}>{t('dash.all')}</button>
          {categories.map((c) => (
            <button key={c} className="chip" aria-pressed={category === c} onClick={() => setCategory(c)}>{c}</button>
          ))}
        </div>
        <details className="card p-3">
          <summary className="min-h-11 cursor-pointer font-semibold leading-[2.75rem]">{t('dash.moreFilters')}</summary>
          <div className="mt-2 grid gap-3 sm:grid-cols-3">
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
            <label className="flex min-h-12 items-center gap-2 self-end font-semibold">
              <input type="checkbox" className="h-6 w-6" checked={nowOnly} onChange={(e) => setNowOnly(e.target.checked)} />
              {t('dash.pickupNow')}
            </label>
          </div>
        </details>
      </div>

      {res.loading && !items.length && <Spinner />}
      {!!res.error && <ErrorBox error={res.error} onRetry={res.reload} />}

      {closing.length > 0 && (
        <section aria-labelledby="closing-h">
          <h2 id="closing-h" className="mb-2 text-xl font-bold">{t('dash.closingSoon')}</h2>
          <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-2">
            {closing.map((o) => <OfferCard key={o.id} o={o} d={decisions[o.id]} compact />)}
          </div>
        </section>
      )}

      <section aria-labelledby="near-h">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 id="near-h" className="text-xl font-bold">{t('dash.nearYou')}</h2>
          <label className="flex items-center gap-2 text-sm font-semibold">
            {t('dash.sortBy')}
            <select className="input !w-auto" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              {SORTS.map((s) => <option key={s} value={s}>{t(`dash.sort.${s}`)}</option>)}
            </select>
          </label>
        </div>
        {!res.loading && !visible.length && !res.error && <p className="card p-6 text-center text-muted">{t('dash.empty')}</p>}
        <div className="grid gap-3 sm:grid-cols-2">
          {visible.map((o) => <OfferCard key={o.id} o={o} d={decisions[o.id]} />)}
        </div>
      </section>
    </div>
  )
}
