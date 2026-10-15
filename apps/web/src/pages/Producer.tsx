import { useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { api } from '../api/client'
import type { Offer, Order, Product, ProducerOfferInput, ProductInput, Stall } from '../api/types'
import { ErrorBox, Field, Notice, PageTitle, Spinner } from '../components/ui'
import { StatusBadge, orderTitle } from '../components/OrderBits'
import { useI18n } from '../i18n'
import { useServerTime } from '../state/servertime'
import { useLive } from '../state/live'
import { useAsync } from '../lib/hooks'
import { dateTime, madridDate, madridISO, money, timeHM } from '../lib/format'

function Shell({ title, children }: { title: string; children: ReactNode }) {
  return (<div><PageTitle>{title}</PageTitle>{children}</div>)
}

/** Puestos del productor (GET /producer/stalls), sus plantillas (GET /products) y ofertas vigentes (GET /offers). */
function useCatalog(stallId?: string) {
  const res = useAsync(() => api.listOffers(), [])
  const st = useAsync(() => api.producerStalls(), [])
  const pr = useAsync(() => (stallId ? api.listProducts(stallId) : Promise.resolve({ items: [] as Product[] })), [stallId])
  const offers = useMemo(() => res.data?.items ?? [], [res.data])
  const stalls = useMemo(() => st.data?.items ?? [], [st.data])
  const products = useMemo(() => pr.data?.items ?? [], [pr.data])
  return { res, st, offers, stalls, products, productsLoading: pr.loading, reloadProducts: pr.reload }
}

function useMyStall(stalls: Stall[]) {
  const [id, setId] = useState(() => {
    try { return localStorage.getItem('mc_stall') ?? '' } catch { return '' }
  })
  const current = stalls.find((s) => s.id === id)?.id ?? stalls[0]?.id ?? ''
  const set = (v: string) => {
    setId(v)
    try { localStorage.setItem('mc_stall', v) } catch { /* ignorar */ }
  }
  return [current, set] as const
}

const LAST = 'mc_last_offer'

const PHOTO_MAX_BYTES = 2 * 1024 * 1024
const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp']

type VatRate = '4' | '10' | '21'
type FoodClass = 'REFRIGERATED' | 'AMBIENT'

export function ProducerPublish() {
  const { t, lang } = useI18n()
  const { nowMs } = useServerTime()
  const stallsRes = useAsync(() => api.producerStalls(), [])
  const [stall, setStall] = useMyStall(stallsRes.data?.items ?? [])
  const cat = useCatalog(stall)
  const [mode, setMode] = useState<'existing' | 'new'>('existing')
  // Sin plantillas en el puesto, el formulario va directamente a "producto nuevo".
  const newMode = mode === 'new' || (!cat.productsLoading && cat.products.length === 0)
  const [product, setProduct] = useState('')
  const [qty, setQty] = useState('5')
  const [price, setPrice] = useState('')
  const [profile, setProfile] = useState<'LIBRE' | 'EQUILIBRADO' | 'ESTRICTO'>('EQUILIBRADO')
  const [until, setUntil] = useState('')
  const [from, setFrom] = useState('')
  const [consume, setConsume] = useState<'TODAY' | 'BEST_BEFORE'>('TODAY')
  // Producto nuevo
  const [pName, setPName] = useState('')
  const [pUnit, setPUnit] = useState('kg')
  const [pWeight, setPWeight] = useState('')
  const [pVat, setPVat] = useState<VatRate>('10')
  const [pFood, setPFood] = useState<FoodClass>('AMBIENT')
  const [pUsual, setPUsual] = useState('')
  const [photo, setPhoto] = useState<File | null>(null)
  const [fileKey, setFileKey] = useState(0)
  const [formError, setFormError] = useState('')
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<{ ms: number; photoFailed: boolean } | null>(null)
  const [t0] = useState(() => Date.now())

  // Producto seleccionado: el estado manda aunque la lista aún no se haya recargado.
  const selectedId = product || cat.products[0]?.id || ''
  const prod = cat.products.find((p) => p.id === selectedId)
  const newUsualCents = pUsual.trim() ? Math.round(parseFloat(pUsual.replace(',', '.')) * 100) : null
  const ref = newMode ? (newUsualCents !== null && Number.isNaN(newUsualCents) ? null : newUsualCents) : (prod?.usual_price_cents ?? null)
  // Ventana por defecto: la de las ofertas vigentes (cierre del mercado); si no hay, 13:30-14:30.
  const dflFrom = cat.offers.length ? timeHM(cat.offers.reduce((a, o) => (o.pickup_from < a ? o.pickup_from : a), cat.offers[0].pickup_from), 'es') : '13:30'
  const dflUntil = cat.offers.length ? timeHM(cat.offers.reduce((a, o) => (o.pickup_until > a ? o.pickup_until : a), cat.offers[0].pickup_until), 'es') : '14:30'
  const priceCents = Math.round(parseFloat(price.replace(',', '.')) * 100)
  const overUsual = ref !== null && !Number.isNaN(priceCents) && priceCents > ref

  function repeat() {
    try {
      const l = JSON.parse(localStorage.getItem(LAST) ?? 'null')
      if (!l) return
      setMode('existing'); setProduct(l.product); setQty(String(l.qty)); setPrice(String(l.price)); setProfile(l.profile)
    } catch { /* nada guardado */ }
  }

  function resetNew() {
    setPName(''); setPWeight(''); setPUsual(''); setPhoto(null); setFileKey((k) => k + 1)
  }

  function validateNew(): string {
    const name = pName.trim()
    if (name.length < 2 || name.length > 80) return t('pub.newNameLen')
    if (!pUnit.trim()) return t('pub.newUnitReq')
    if (newUsualCents !== null && Number.isNaN(newUsualCents)) return t('pub.newPrice')
    if (photo && !PHOTO_TYPES.includes(photo.type)) return t('pub.photoType')
    if (photo && photo.size > PHOTO_MAX_BYTES) return t('pub.photoTooBig')
    return ''
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setErr(null)
    setFormError('')
    if (newMode) {
      const m = validateNew()
      if (m) { setFormError(m); return }
    }
    setBusy(true)
    const day = madridDate(new Date(nowMs()))
    try {
      let productId = selectedId
      let refCents = ref
      let photoFailed = false
      if (newMode) {
        const input: ProductInput = {
          stall_id: stall,
          name: pName.trim(),
          unit: pUnit.trim(),
          unit_weight_g: pWeight.trim() ? parseInt(pWeight, 10) : null,
          vat_rate: parseInt(pVat, 10) as 4 | 10 | 21,
          allergens: [],
          food_class: pFood,
          usual_price_cents: newUsualCents,
        }
        const created = await api.producerCreateProduct(input)
        productId = created.id
        refCents = newUsualCents
        if (photo) {
          try { await api.producerUploadProductPhoto(created.id, photo) } catch { photoFailed = true }
        }
        // Tras crear el producto, pasa a "existente" con él seleccionado: si la oferta falla, reintentar no lo duplica.
        setMode('existing')
        setProduct(created.id)
        resetNew()
        cat.reloadProducts()
      }
      const body: ProducerOfferInput = {
        stall_id: stall,
        product_id: productId,
        qty_total: parseInt(qty, 10),
        price_cents: priceCents,
        reference_price_cents: refCents ?? undefined,
        pickup_from: madridISO(day, from || dflFrom),
        pickup_until: madridISO(day, until || dflUntil),
        consume_by: consume,
        profile,
        publish: true,
      }
      await api.producerCreateOffer(body)
      try { localStorage.setItem(LAST, JSON.stringify({ product: productId, qty, price, profile })) } catch { /* ignorar */ }
      setDone({ ms: Date.now() - t0, photoFailed })
    } catch (x) {
      setErr(x)
    } finally {
      setBusy(false)
    }
  }

  if (cat.res.loading || stallsRes.loading) return <Shell title={t('pub.title')}><Spinner /></Shell>
  return (
    <Shell title={t('pub.title')}>
      {done && <Notice icon="check">{t('pub.done', { s: Math.round(done.ms / 1000) })}</Notice>}
      {done?.photoFailed && <Notice icon="alert" tone="warn">{t('pub.photoFailed')}</Notice>}
      {!cat.stalls.length && <Notice icon="alert" tone="warn">{t('pub.noStalls')}</Notice>}
      <form onSubmit={submit} className="card mt-3 space-y-4 p-4">
        {!!err && <ErrorBox error={err} />}
        {!!formError && <p role="alert" className="font-medium text-danger">{formError}</p>}
        {cat.stalls.length > 1 && (
          <Field label={t('pub.stall')}>
            <select className="input" value={stall} onChange={(e) => setStall(e.target.value)}>
              {cat.stalls.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
        )}
        <div role="group" aria-labelledby="mode-l" className="space-y-2">
          <span className="label" id="mode-l">{t('pub.product')}</span>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="chip" aria-pressed={!newMode} disabled={!cat.products.length} onClick={() => setMode('existing')}>{t('pub.modeExisting')}</button>
            <button type="button" className="chip" aria-pressed={newMode} onClick={() => setMode('new')}>{t('pub.modeNew')}</button>
          </div>
        </div>
        {newMode ? (
          <div className="space-y-4">
            <Field label={t('pub.newName')}>
              <input className="input" required minLength={2} maxLength={80} value={pName} onChange={(e) => setPName(e.target.value)} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label={t('pub.newUnit')}>
                <input className="input" required maxLength={20} value={pUnit} onChange={(e) => setPUnit(e.target.value)} />
              </Field>
              <Field label={t('pub.newWeight')}>
                <input className="input" inputMode="numeric" value={pWeight} onChange={(e) => setPWeight(e.target.value)} />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label={t('pub.newVat')}>
                <select className="input" value={pVat} onChange={(e) => setPVat(e.target.value as VatRate)}>
                  <option value="4">4 %</option>
                  <option value="10">10 %</option>
                  <option value="21">21 %</option>
                </select>
              </Field>
              <Field label={t('pub.newFood')}>
                <select className="input" value={pFood} onChange={(e) => setPFood(e.target.value as FoodClass)}>
                  <option value="REFRIGERATED">{t('pub.newRefrigerated')}</option>
                  <option value="AMBIENT">{t('pub.newAmbient')}</option>
                </select>
              </Field>
            </div>
            <Field label={t('pub.newUsual')}>
              <input className="input" inputMode="decimal" value={pUsual} onChange={(e) => setPUsual(e.target.value)} placeholder="2,50" />
            </Field>
            <Field label={t('pub.newPhoto')} hint={t('pub.photoHint')}>
              <input key={fileKey} className="input" type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
            </Field>
          </div>
        ) : (
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Field label={t('pub.product')}>
                <select className="input" required value={selectedId} onChange={(e) => setProduct(e.target.value)}>
                  {cat.products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </Field>
            </div>
            <button type="button" className="btn btn-secondary" onClick={repeat}>{t('pub.repeat')}</button>
          </div>
        )}
        <Field label={t('pub.qty')}><input className="input" inputMode="numeric" required value={qty} onChange={(e) => setQty(e.target.value)} /></Field>
        <Field label={t('pub.price')} hint={ref !== null ? t('pub.usual', { p: money(ref, lang) }) : undefined}>
          <input className="input" inputMode="decimal" required value={price} onChange={(e) => setPrice(e.target.value)} placeholder="2,50" />
        </Field>
        {overUsual && <Notice icon="alert" tone="warn">{t('pub.overUsual')}</Notice>}
        <div role="group" aria-labelledby="prof-l">
          <span className="label" id="prof-l">{t('pub.profile')}</span>
          <div className="flex flex-wrap gap-2">
            {(['LIBRE', 'EQUILIBRADO', 'ESTRICTO'] as const).map((p) => (
              <button type="button" key={p} className="chip" aria-pressed={profile === p} onClick={() => setProfile(p)}>{t(`profile.${p}`)}</button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('pub.from')}><input className="input" type="time" value={from || dflFrom} onChange={(e) => setFrom(e.target.value)} /></Field>
          <Field label={t('pub.until')}><input className="input" type="time" value={until || dflUntil} onChange={(e) => setUntil(e.target.value)} /></Field>
        </div>
        <Field label={t('pub.consume')}>
          <select className="input" value={consume} onChange={(e) => setConsume(e.target.value as 'TODAY' | 'BEST_BEFORE')}>
            <option value="TODAY">{t('offer.consumeToday')}</option>
            <option value="BEST_BEFORE">{t('offer.bestBefore')}</option>
          </select>
        </Field>
        <button className="btn btn-primary w-full" disabled={busy || !stall || (!newMode && !selectedId)}>{t('pub.publish')}</button>
      </form>
    </Shell>
  )
}

export function ProducerOrders() {
  const { t, lang } = useI18n()
  const res = useAsync(() => api.producerOrders(), [])
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState('')
  const [filter, setFilter] = useState<'todo' | 'all'>('todo')
  useLive('order.updated', res.reload)
  useLive('reconnect', res.reload)

  async function act(o: Order, kind: 'accept' | 'deposit' | 'reject') {
    setBusy(o.id)
    setErr(null)
    try {
      await (kind === 'accept' ? api.producerAccept(o.id) : kind === 'reject' ? api.producerReject(o.id) : api.producerDeposit(o.id))
    } catch (e) {
      setErr(e)
    } finally {
      setBusy('')
      res.reload()
    }
  }
  const all = res.data?.items ?? []
  const items = (filter === 'todo' ? all.filter((o) => o.status === 'PAID' || o.status === 'PREPARING') : all).sort((a, b) => b.created_at.localeCompare(a.created_at))
  return (
    <Shell title={t('prod.orders')}>
      <div className="mb-3 flex gap-2">
        <button className="chip" aria-pressed={filter === 'todo'} onClick={() => setFilter('todo')}>{t('prod.toDo')}</button>
        <button className="chip" aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>{t('dash.all')}</button>
      </div>
      {!!err && <ErrorBox error={err} />}
      {res.loading && <Spinner />}
      {!!res.error && <ErrorBox error={res.error} onRetry={res.reload} />}
      {!res.loading && !items.length && <p className="card p-6 text-center text-muted">{t('prod.noOrders')}</p>}
      <ul className="space-y-3">
        {items.map((o) => (
          <li key={o.id} className="card space-y-2 p-4">
            <div className="flex justify-between gap-2"><StatusBadge s={o.status} /><span className="text-sm text-muted">{dateTime(o.created_at, lang)}</span></div>
            <p className="font-bold">{orderTitle(o)}</p>
            <p className="text-sm text-muted">{money(o.total_cents, lang)} · {t('order.pickupUntil', { to: timeHM(o.pickup_until, lang) })}{o.locker ? ` · ${t('prod.slot', { n: o.locker.slot })}` : ''}</p>
            {o.status === 'PAID' && (
              <div className="flex flex-wrap gap-2">
                <button className="btn btn-primary" disabled={busy === o.id} onClick={() => act(o, 'accept')}>{t('prod.accept')}</button>
                <button className="btn btn-danger" disabled={busy === o.id} onClick={() => act(o, 'reject')}>{t('prod.reject')}</button>
              </div>
            )}
            {o.status === 'PREPARING' && <button className="btn btn-primary" disabled={busy === o.id} onClick={() => act(o, 'deposit')}>{t('prod.deposit')}</button>}
          </li>
        ))}
      </ul>
    </Shell>
  )
}

function OfferRow({ o, onChanged }: { o: Offer; onChanged: () => void }) {
  const { t, lang } = useI18n()
  const [edit, setEdit] = useState(false)
  const [price, setPrice] = useState(String(o.price_cents / 100).replace('.', ','))
  const [qty, setQty] = useState(String(o.qty_total))
  const [err, setErr] = useState<unknown>(null)
  async function save() {
    setErr(null)
    try {
      await api.producerUpdateOffer(o.id, { price_cents: Math.round(parseFloat(price.replace(',', '.')) * 100), qty_total: parseInt(qty, 10) })
      setEdit(false)
      onChanged()
    } catch (e) { setErr(e) }
  }
  async function withdraw() {
    setErr(null)
    try { await api.producerWithdraw(o.id); onChanged() } catch (e) { setErr(e) }
  }
  return (
    <li className="card space-y-2 p-4">
      <p className="font-bold">{o.product.name} · {money(o.price_cents, lang)}</p>
      <p className="text-sm text-muted">{t(`offerStatus.${o.status}`, {}, o.status)} · {t('offer.left', { n: o.qty_available, count: o.qty_available })} / {o.qty_total} · {timeHM(o.pickup_from, lang)}-{timeHM(o.pickup_until, lang)}</p>
      {!!err && <ErrorBox error={err} />}
      {edit ? (
        <div className="flex flex-wrap items-end gap-2">
          <Field label={t('pub.price')}><input className="input !w-28" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} /></Field>
          <Field label={t('pub.qty')}><input className="input !w-24" inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value)} /></Field>
          <button className="btn btn-primary" onClick={save}>{t('common.save')}</button>
          <button className="btn btn-secondary" onClick={() => setEdit(false)}>{t('common.cancel')}</button>
        </div>
      ) : (
        o.status === 'DRAFT' ? (
          <div className="flex gap-2">
            <button className="btn btn-primary" onClick={async () => { setErr(null); try { await api.producerPublish(o.id); onChanged() } catch (e) { setErr(e) } }}>{t('prod.publishDraft')}</button>
            <button className="btn btn-danger" onClick={async () => { setErr(null); try { await api.producerDeleteDraft(o.id); onChanged() } catch (e) { setErr(e) } }}>{t('prod.deleteDraft')}</button>
          </div>
        ) : o.status === 'ACTIVE' && (
          <div className="flex gap-2">
            <button className="btn btn-secondary" onClick={() => setEdit(true)}>{t('common.edit')}</button>
            <button className="btn btn-danger" onClick={withdraw}>{t('prod.withdraw')}</button>
          </div>
        )
      )}
    </li>
  )
}

export function ProducerOffers() {
  const { t } = useI18n()
  const stallsRes = useAsync(() => api.producerStalls(), [])
  const [stall] = useMyStall(stallsRes.data?.items ?? [])
  const own = useAsync(() => api.producerListOffers(), [])
  useLive('offer.updated', own.reload)
  const mine = (own.data?.items ?? []).filter((o) => !stall || o.stall.id === stall)
  return (
    <Shell title={t('prod.offers')}>
      {own.loading && <Spinner />}
      {!!own.error && <ErrorBox error={own.error} onRetry={own.reload} />}
      {!own.loading && !mine.length && <p className="card p-6 text-center text-muted">{t('prod.noOffers')}</p>}
      <ul className="space-y-3">{mine.map((o) => <OfferRow key={o.id} o={o} onChanged={own.reload} />)}</ul>
    </Shell>
  )
}

export function ProducerPayouts() {
  const { t, lang } = useI18n()
  const res = useAsync(() => api.producerPayouts(), [])
  return (
    <Shell title={t('prod.payouts')}>
      {res.loading && <Spinner />}
      {!!res.error && <ErrorBox error={res.error} onRetry={res.reload} />}
      {res.data && !res.data.items.length && <p className="card p-6 text-center text-muted">{t('prod.noPayouts')}</p>}
      <ul className="space-y-3">
        {res.data?.items.map((p) => (
          <li key={p.id} className="card p-4">
            <p className="font-bold">{money(p.amount_cents, lang)} · {t(`payout.${p.status}`, {}, p.status)}</p>
            <p className="text-sm text-muted">{p.period_from} → {p.period_to} · {t('payout.gross')} {money(p.gross_cents ?? 0, lang)} · {t('payout.commission')} {money(p.commission_cents ?? 0, lang)}</p>
          </li>
        ))}
      </ul>
    </Shell>
  )
}
