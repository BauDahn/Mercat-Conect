import type { Decision, Offer, User } from '../api/types'

export type CardState =
  | { kind: 'soldout' }
  | { kind: 'anon' }
  | { kind: 'unverified' }
  | { kind: 'nopoints'; missing: number | null }
  | { kind: 'max'; max: number }
  | { kind: 'denied'; reason: string }
  | { kind: 'ok' }
  | { kind: 'unknown' }

/** Estado de tarjeta (§6.2) a partir de la oferta, el usuario y la decisión del motor. */
export function cardState(o: Offer, user: User | null, d: Decision | null | undefined, left: number | null): CardState {
  if (o.status === 'SOLD_OUT' || o.qty_available <= 0) return { kind: 'soldout' }
  if (!user) return { kind: 'anon' }
  if (!user.age_verified || user.status === 'PENDING') return { kind: 'unverified' }
  if (!d) return { kind: 'unknown' }
  if (d.allowed) return { kind: 'ok' }
  const keys = (d.reasons ?? []).join(' ')
  if (/no_points|points/.test(keys)) return { kind: 'nopoints', missing: left === null ? null : Math.max(1, d.points_cost - left) }
  if (/exceeds_max|max/.test(keys)) return { kind: 'max', max: d.max_units }
  if (d.max_units > 0 && d.points_cost === 0) return { kind: 'max', max: d.max_units }
  return { kind: 'denied', reason: d.reasons?.[0] ?? '' }
}

export function discountPct(o: Offer): number | null {
  const r = o.reference_price_cents
  if (!r || r <= 0 || o.price_cents >= r) return null
  return Math.round((1 - o.price_cents / r) * 100)
}

/** Extrae la decisión si el listado ya la trae (campo no contractual; se tolera). */
export function inlineDecision(o: Offer): Decision | null {
  const d = (o as Offer & { decision?: Decision | null }).decision
  return d && typeof d === 'object' ? d : null
}
