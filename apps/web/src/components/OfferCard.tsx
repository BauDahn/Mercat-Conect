import { Link } from 'react-router-dom'
import type { Decision, Offer } from '../api/types'
import { ProductArt } from './ProductArt'
import { Badge } from './ui'
import { Icon } from './Icon'
import { useI18n } from '../i18n'
import { useAuth } from '../state/auth'
import { useServerTime } from '../state/servertime'
import { cardState, discountPct } from '../lib/offers'
import { minutesLeft, money, timeHM, weekday } from '../lib/format'

/** Insignias superpuestas sobre la foto (urgencia, descuento, agotada). */
export function OfferBadges({ o }: { o: Offer }) {
  const { t } = useI18n()
  const { nowMs } = useServerTime()
  const m = minutesLeft(o.pickup_until, nowMs())
  const pct = discountPct(o)
  return (
    <div className="flex flex-wrap gap-1.5">
      {o.qty_available > 0 && m > 0 && m <= 60 && <Badge tone="warn" icon="clock">{t('offer.closesIn', { n: m })}</Badge>}
      {o.qty_available > 0 && o.qty_available <= 3 && <Badge tone="bad" icon="alert">{t('offer.lastUnits')}</Badge>}
      {pct !== null && <Badge tone="ok" icon="euro">{t('offer.discount', { n: pct })}</Badge>}
      {(o.qty_available <= 0 || o.status === 'SOLD_OUT') && <Badge icon="x">{t('offer.soldOut')}</Badge>}
    </div>
  )
}

export function StateLine({ o, d }: { o: Offer; d: Decision | null | undefined }) {
  const { t, lang } = useI18n()
  const { user, points } = useAuth()
  const s = cardState(o, user, d, points?.left ?? null)
  switch (s.kind) {
    case 'soldout':
      return <p className="font-semibold text-muted">{t('offer.soldOutLong')}</p>
    case 'anon':
      return <p className="font-semibold text-brand">{t('offer.loginToReserve')}</p>
    case 'unverified':
      return <p className="font-semibold text-accent">{t('offer.verifyAge')}</p>
    case 'nopoints':
      return (
        <p className="font-semibold text-danger">
          {s.missing !== null ? t('offer.missingPoints', { n: s.missing, count: s.missing }) : t('offer.noPoints')}{' '}
          {points && t('offer.renewsOn', { day: weekday(points.renews_at, lang) })}
        </p>
      )
    case 'max':
      return <p className="font-semibold text-accent">{t('offer.maxToday', { n: s.max })}</p>
    case 'denied':
      return <p className="font-semibold text-danger">{t(s.reason, {}, t('offer.denied'))}</p>
    case 'ok':
      return <p className="font-semibold text-brand">{t('offer.reserve')}</p>
    default:
      return null
  }
}

/** Tarjeta estilo "too good to go": foto grande, precio en verde, pill de unidades y coste en puntos. */
export function OfferCard({ o, d, compact = false }: { o: Offer; d: Decision | null | undefined; compact?: boolean }) {
  const { t, lang } = useI18n()
  const { user, points } = useAuth()
  const soldOut = o.qty_available <= 0 || o.status === 'SOLD_OUT'
  const stock = o.effective_stock ?? o.qty_available
  const state = cardState(o, user, d, points?.left ?? null)
  const blocked = !soldOut && state.kind !== 'ok'
  return (
    <Link
      to={`/oferta/${o.id}`}
      className={`card group flex flex-col overflow-hidden transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)] focus-visible:outline-offset-4 ${compact ? 'w-64 shrink-0 snap-start' : ''} ${soldOut ? 'opacity-70' : ''}`}
      aria-label={`${o.product.name}, ${o.stall.name}, ${money(o.price_cents, lang)}`}
    >
      <ProductArt offer={o} className={compact ? 'h-36' : 'h-40 sm:h-44'}>
        <div className="absolute left-3 top-3 right-3">
          <OfferBadges o={o} />
        </div>
        {soldOut && <div className="absolute inset-0 bg-paper/60 grayscale" aria-hidden="true" />}
      </ProductArt>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <p className="text-sm font-semibold text-muted">{o.stall.name}</p>
        <h3 className="text-lg font-bold leading-snug">{o.product.name}</h3>
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className={`text-2xl font-extrabold ${soldOut ? 'text-muted' : 'text-brand'}`}>{money(o.price_cents, lang)}</span>
          {o.reference_price_cents ? (
            <span className="text-sm text-muted">
              {t('offer.before')} <s>{money(o.reference_price_cents, lang)}</s>
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className={`inline-flex min-h-8 items-center gap-1 rounded-full px-3 font-bold ${soldOut ? 'bg-paper-2 text-muted' : 'bg-accent-soft text-accent'}`}>
            <Icon name="box" className="h-4 w-4" />
            {soldOut ? t('offer.soldOut') : t('offer.left', { n: stock, count: stock })}
          </span>
          <span className="inline-flex items-center gap-1 font-semibold text-ink">
            <Icon name="clock" className="h-4 w-4" />
            {t('offer.pickup', { from: timeHM(o.pickup_from, lang), to: timeHM(o.pickup_until, lang) })}
          </span>
        </div>
        <div className="mt-auto flex items-center justify-between gap-2 border-t border-line pt-2 text-sm">
          {d && !soldOut ? (
            <span className="inline-flex items-center gap-1 font-bold text-brand-dark">
              <Icon name="star" className="h-4 w-4" /> {t('offer.cost', { n: d.points_cost })}
            </span>
          ) : (
            <span className="text-muted">{soldOut ? t('offer.soldOutLong') : ''}</span>
          )}
          {blocked && ['nopoints', 'max', 'denied'].includes(state.kind) && <span className="text-xs font-semibold text-muted">{t('offer.seeWhy')}</span>}
        </div>
        {!compact && blocked && <StateLine o={o} d={d} />}
      </div>
    </Link>
  )
}
