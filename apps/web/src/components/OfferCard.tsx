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

export function OfferCard({ o, d, compact = false }: { o: Offer; d: Decision | null | undefined; compact?: boolean }) {
  const { t, lang } = useI18n()
  const soldOut = o.qty_available <= 0 || o.status === 'SOLD_OUT'
  const stock = o.effective_stock ?? o.qty_available
  return (
    <Link
      to={`/oferta/${o.id}`}
      className={`card block overflow-hidden ${compact ? 'w-56 shrink-0' : ''} ${soldOut ? 'opacity-60' : ''}`}
      aria-label={`${o.product.name}, ${o.stall.name}`}
    >
      <ProductArt offer={o} className={compact ? 'h-24' : 'h-28'} />
      <div className="space-y-1.5 p-3">
        <OfferBadges o={o} />
        <h3 className="text-lg font-bold leading-tight">{o.product.name}</h3>
        <p className="text-sm text-muted">{o.stall.name} · {o.stall.category}</p>
        <p className="flex items-baseline gap-2">
          <span className="text-xl font-bold text-brand-dark">{money(o.price_cents, lang)}</span>
          {o.reference_price_cents ? (
            <span className="text-sm text-muted">
              {t('offer.before')} <s>{money(o.reference_price_cents, lang)}</s>
            </span>
          ) : null}
        </p>
        <p className="flex items-center gap-1 text-sm">
          <Icon name="clock" className="h-4 w-4" />
          {t('offer.pickup', { from: timeHM(o.pickup_from, lang), to: timeHM(o.pickup_until, lang) })}
        </p>
        <p className="text-sm font-semibold">
          {t('offer.left', { n: stock, count: stock })}
          {d && !soldOut && <> · {t('offer.cost', { n: d.points_cost })}</>}
        </p>
        {!compact && <StateLine o={o} d={d} />}
      </div>
    </Link>
  )
}
