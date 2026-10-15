import { useState, type FormEvent, type ReactNode } from 'react'
import { API_BASE, ApiError, api } from '../api/client'
import type { Guardrails, Metrics } from '../api/types'
import { ErrorBox, Field, Notice, PageTitle, Spinner } from '../components/ui'
import { useI18n } from '../i18n'
import { useAsync } from '../lib/hooks'
import { dateTime, money } from '../lib/format'

function Shell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <PageTitle>{title}</PageTitle>
      {children}
    </div>
  )
}

function pct(n: number | undefined): string {
  return n === undefined || n === null ? '–' : `${Math.round(n * 100)} %`
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="text-2xl font-bold text-brand-dark">{value}</p>
    </div>
  )
}

function Heatmap({ m }: { m: Metrics }) {
  const { t } = useI18n()
  const cells = m.heatmap ?? []
  if (!cells.length) return null
  const max = Math.max(1, ...cells.map((c) => c.orders ?? 0))
  const hours = Array.from(new Set(cells.map((c) => c.hour ?? 0))).sort((a, b) => a - b)
  const get = (d: number, h: number) => cells.find((c) => c.weekday === d && c.hour === h)?.orders ?? 0
  return (
    <section className="card overflow-x-auto p-4" aria-labelledby="hm-h">
      <h2 id="hm-h" className="mb-2 font-bold">{t('adm.heatmap')}</h2>
      <table className="text-center text-sm">
        <thead><tr><th scope="col"><span className="sr-only">{t('adm.day')}</span></th>{hours.map((h) => <th key={h} scope="col" className="px-2">{h}h</th>)}</tr></thead>
        <tbody>
          {[0, 1, 2, 3, 4, 5, 6].map((d) => (
            <tr key={d}>
              <th scope="row" className="pr-2 text-left">{t(`adm.wd.${d}`)}</th>
              {hours.map((h) => {
                const v = get(d, h)
                return <td key={h} className="h-9 w-10 border border-white font-semibold" style={{ background: `rgba(20,99,60,${0.08 + 0.8 * (v / max)})`, color: v / max > 0.5 ? '#fff' : '#1c2420' }}>{v}</td>
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

export function AdminMetrics() {
  const { t, lang } = useI18n()
  const res = useAsync(() => api.adminMetrics(), [])
  const m = res.data
  return (
    <Shell title={t('adm.title')}>
      {res.loading && <Spinner />}
      {!!res.error && <ErrorBox error={res.error} onRetry={res.reload} />}
      {m && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Stat label={t('adm.kgRescued')} value={`${(m.kg_rescued ?? 0).toFixed(1)} kg`} />
            <Stat label={t('adm.kgDonated')} value={`${(m.kg_donated ?? 0).toFixed(1)} kg`} />
            <Stat label={t('adm.sellThrough')} value={pct(m.sell_through)} />
            <Stat label={t('adm.soldOut')} value={pct(m.sold_out_rate)} />
            <Stat label={t('adm.noShow')} value={pct(m.no_show_rate)} />
            <Stat label={t('adm.denial')} value={pct(m.points_denial_rate)} />
            <Stat label={t('adm.lockerUse')} value={pct(m.locker_utilization)} />
            <Stat label={t('adm.co2')} value={m.co2_avoided_kg == null ? t('adm.na') : `${m.co2_avoided_kg.toFixed(1)} kg`} />
            <Stat label={t('adm.revenue')} value={money(m.producer_revenue_cents ?? 0, lang)} />
          </div>
          <Heatmap m={m} />
        </div>
      )}
      <section className="card mt-4 p-4">
        <h2 className="mb-2 font-bold">{t('adm.openData')}</h2>
        <ul className="flex flex-wrap gap-2">
          {['impact', 'offers_by_day', 'sellthrough'].map((n) => (
            <li key={n}><a className="btn btn-secondary" href={`${API_BASE}/open-data/${n}.csv`} download>{n}.csv</a></li>
          ))}
        </ul>
      </section>
    </Shell>
  )
}

export function AdminGuardrails() {
  const { t } = useI18n()
  const [g, setG] = useState({ max_points_per_unit: '', max_units_per_user: '', max_price_ratio: '', weekly_allowance: '', min_open_data_cell: '' })
  const [err, setErr] = useState<unknown>(null)
  const [ok, setOk] = useState(false)
  const fields = Object.keys(g) as (keyof typeof g)[]

  async function submit(e: FormEvent) {
    e.preventDefault()
    setErr(null)
    setOk(false)
    const body: Guardrails = {}
    for (const k of fields) {
      const raw = g[k].trim().replace(',', '.')
      if (raw === '') continue
      ;(body as Record<string, number>)[k] = k === 'max_price_ratio' ? parseFloat(raw) : parseInt(raw, 10)
    }
    try {
      const r = await api.adminGuardrails(body)
      setG((s) => ({ ...s, ...Object.fromEntries(Object.entries(r).map(([k, v]) => [k, v == null ? '' : String(v)])) }))
      setOk(true)
    } catch (x) {
      setErr(x)
    }
  }
  return (
    <Shell title={t('adm.guardrails')}>
      <form onSubmit={submit} className="card space-y-4 p-4">
        <Notice>{t('adm.guardHint')}</Notice>
        {!!err && <ErrorBox error={err} />}
        {ok && <Notice icon="check">{t('common.saved')}</Notice>}
        {fields.map((k) => (
          <Field key={k} label={t(`adm.g.${k}`)}>
            <input className="input" inputMode="decimal" value={g[k]} onChange={(e) => setG((s) => ({ ...s, [k]: e.target.value }))} />
          </Field>
        ))}
        <button className="btn btn-primary w-full">{t('common.save')}</button>
      </form>
    </Shell>
  )
}

export function AdminStalls() {
  const { t } = useI18n()
  const offers = useAsync(() => api.listOffers(), [])
  const markets = new Map<string, string>()
  for (const o of offers.data?.items ?? []) markets.set(o.stall.market_id, o.stall.market_name ?? o.stall.market_id)
  const [market, setMarket] = useState('')
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [owner, setOwner] = useState('')
  const [err, setErr] = useState<unknown>(null)
  const [ok, setOk] = useState('')

  async function submit(e: FormEvent) {
    e.preventDefault()
    setErr(null)
    setOk('')
    try {
      const s = await api.adminCreateStall({ market_id: market || [...markets.keys()][0], name, category, owner_user_id: owner || undefined })
      setOk(s.name)
      setName('')
    } catch (x) {
      setErr(x)
    }
  }
  return (
    <Shell title={t('adm.stalls')}>
      <form onSubmit={submit} className="card space-y-4 p-4">
        {!!err && <ErrorBox error={err} />}
        {ok && <Notice icon="check">{t('adm.stallCreated', { name: ok })}</Notice>}
        <Field label={t('dash.market')}>
          <select className="input" value={market} onChange={(e) => setMarket(e.target.value)}>
            {[...markets].map(([id, n]) => <option key={id} value={id}>{n}</option>)}
          </select>
        </Field>
        <Field label={t('adm.stallName')}><input className="input" required value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label={t('adm.stallCategory')}><input className="input" required value={category} onChange={(e) => setCategory(e.target.value)} /></Field>
        <Field label={t('adm.owner')} hint={t('adm.ownerHint')}><input className="input" value={owner} onChange={(e) => setOwner(e.target.value)} /></Field>
        <button className="btn btn-primary w-full">{t('adm.createStall')}</button>
      </form>
    </Shell>
  )
}

export function AdminDonations() {
  const { t, lang } = useI18n()
  const res = useAsync(() => api.adminDonations(), [])
  return (
    <Shell title={t('adm.donations')}>
      {res.loading && <Spinner />}
      {!!res.error && <ErrorBox error={res.error} onRetry={res.reload} />}
      {res.data && !res.data.items.length && <p className="card p-6 text-center text-muted">{t('adm.noDonations')}</p>}
      <ul className="space-y-3">
        {res.data?.items.map((d) => (
          <li key={d.id} className="card p-4">
            <p className="font-bold">{d.product_name ?? d.offer_id.slice(0, 8)} · {t('adm.donQty', { n: d.qty })}</p>
            <p className="text-sm text-muted">{d.charity_name ?? d.charity_id.slice(0, 8)} · {t(`adm.donStatus.${d.status}`)} · {dateTime(d.created_at, lang)}</p>
          </li>
        ))}
      </ul>
    </Shell>
  )
}

export function AdminQuality() {
  const { t, lang } = useI18n()
  const res = useAsync(() => api.adminQuality(), [])
  const noLayers = res.error instanceof ApiError && res.error.status === 503
  return (
    <Shell title={t('adm.quality')}>
      {res.loading && <Spinner />}
      {noLayers && <Notice icon="alert" tone="warn">{t('adm.qNoLayers')}</Notice>}
      {!!res.error && !noLayers && <ErrorBox error={res.error} onRetry={res.reload} />}
      {res.data?.ok && <Notice icon="check">{t('adm.qOk')}</Notice>}
      {res.data && !res.data.ok && (
        <div className="space-y-2">
          <Notice icon="alert" tone="bad">{t('adm.qFail')}</Notice>
          <ul className="space-y-2">
            {res.data.failures.map((f, i) => (
              <li key={i} className="card p-3"><p className="font-bold">{f.test}</p><p className="text-sm text-muted">{f.detail}</p></li>
            ))}
          </ul>
        </div>
      )}
      {res.data && <p className="mt-2 text-sm text-muted">{t('adm.qChecked', { d: dateTime(res.data.checked_at, lang) })}</p>}
      <button className="btn btn-secondary mt-3" onClick={res.reload}>{t('common.retry')}</button>
    </Shell>
  )
}
