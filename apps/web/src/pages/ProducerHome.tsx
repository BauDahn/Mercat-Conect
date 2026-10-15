import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { EmptyState, ErrorBox, Skeleton, Stat } from '../components/ui'
import { Icon } from '../components/Icon'
import { useI18n } from '../i18n'
import { useAsync } from '../lib/hooks'
import { useLive } from '../state/live'
import { money } from '../lib/format'

/** Panel del productor (§6.1): KPIs, publicar en grande, pedidos por preparar y sus ofertas. */
export function ProducerHome() {
  const { t, lang } = useI18n()
  const offers = useAsync(() => api.producerListOffers(), [])
  const orders = useAsync(() => api.producerOrders(), [])
  useLive('order.updated', orders.reload)
  useLive('offer.updated', offers.reload)

  const list = offers.data?.items ?? []
  const active = list.filter((o) => o.status === 'ACTIVE')
  const drafts = list.filter((o) => o.status === 'DRAFT')
  const toPrepare = (orders.data?.items ?? []).filter((o) => o.status === 'PAID' || o.status === 'PREPARING')
  const loading = offers.loading || orders.loading

  return (
    <div className="space-y-8">
      <section aria-labelledby="ph-h" className="flex flex-col gap-4 rounded-3xl bg-gradient-to-br from-brand to-brand-dark p-6 text-white shadow-[var(--shadow-lift)] sm:flex-row sm:items-center sm:justify-between sm:p-8">
        <div>
          <p className="text-sm font-bold uppercase tracking-wide text-white/80">{t('ui.producerKicker')}</p>
          <h1 id="ph-h" className="text-3xl font-extrabold">{t('ui.producerTitle')}</h1>
          <p className="mt-1 text-white/90">{t('ui.producerSub')}</p>
        </div>
        <Link to="/productor/publicar" className="btn btn-accent !min-h-14 px-6 text-lg shadow-[var(--shadow-soft)]">
          <Icon name="plus" className="h-6 w-6" /> {t('ui.publishBig')}
        </Link>
      </section>

      {!!(offers.error || orders.error) && <ErrorBox error={offers.error ?? orders.error} onRetry={() => { offers.reload(); orders.reload() }} />}

      <section aria-label={t('ui.kpis')} className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <Stat label={t('ui.kpiActive')} value={loading ? '…' : active.length} icon="box" />
        <Stat label={t('ui.kpiToPrepare')} value={loading ? '…' : toPrepare.length} icon="bag" tone="accent" />
        <div className="col-span-2 lg:col-span-1"><Stat label={t('ui.kpiDrafts')} value={loading ? '…' : drafts.length} icon="store" tone="ink" /></div>
      </section>

      <div className="grid gap-8 lg:grid-cols-2">
        <section aria-labelledby="ph-orders" className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 id="ph-orders" className="text-xl font-extrabold">{t('ui.toPrepare')}</h2>
            <Link to="/productor/pedidos" className="font-bold text-brand-dark underline underline-offset-4">{t('ui.seeAll')}</Link>
          </div>
          {loading && <Skeleton count={2} />}
          {!loading && !toPrepare.length && <EmptyState icon="bag" title={t('ui.noToPrepare')}>{t('ui.noToPrepareSub')}</EmptyState>}
          <ul className="space-y-3">
            {toPrepare.slice(0, 4).map((o) => (
              <li key={o.id} className="card flex items-center justify-between gap-3 p-4">
                <div>
                  <p className="font-bold">{t(`order.status.${o.status}`, {}, o.status)}</p>
                  <p className="text-sm text-muted">{money(o.total_cents ?? 0, lang)}</p>
                </div>
                <Link to="/productor/pedidos" className="btn btn-primary !min-h-12">{t('ui.prepare')}</Link>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="ph-offers" className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 id="ph-offers" className="text-xl font-extrabold">{t('ui.yourOffers')}</h2>
            <Link to="/productor/ofertas" className="font-bold text-brand-dark underline underline-offset-4">{t('ui.seeAll')}</Link>
          </div>
          {loading && <Skeleton count={2} />}
          {!loading && !list.length && <EmptyState icon="basket" title={t('ui.noOffersYet')} action={<Link to="/productor/publicar" className="btn btn-secondary">{t('ui.publishBig')}</Link>}>{t('ui.noOffersYetSub')}</EmptyState>}
          <ul className="space-y-3">
            {list.slice(0, 4).map((o) => (
              <li key={o.id} className="card flex items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="truncate font-bold">{o.product.name}</p>
                  <p className="text-sm text-muted">{t('ui.unitsLeft', { n: o.qty_available })} · {money(o.price_cents, lang)}</p>
                </div>
                <span className="shrink-0 rounded-full bg-brand-soft px-3 py-1 text-sm font-bold text-brand-dark">{t(`offerStatus.${o.status}`, {}, o.status)}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
