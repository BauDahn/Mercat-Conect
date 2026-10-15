import type { components } from './schema'

type S = components['schemas']
export type User = S['User']
export type Offer = S['Offer']
export type OfferDetail = S['OfferDetail']
export type Decision = S['Decision']
export type Order = S['Order']
export type OrderStatus = S['OrderStatus']
export type OfferStatus = S['OfferStatus']
export type Points = S['Points']
export type Notification = S['Notification']
export type Payout = S['Payout']
export type Metrics = S['Metrics']
export type Guardrails = S['Guardrails']
export type Stall = S['Stall']
export type Product = S['Product']
export type ProductInput = S['ProductInput']
export type PaymentIntent = S['PaymentIntent']
export type ProducerOfferInput = S['ProducerOfferInput']
export type ProducerOfferPatch = S['ProducerOfferPatch']
export type SimLocker = S['SimLocker']
export type SimCompartment = S['SimCompartment']
export type StallInput = S['StallInput']
export type Donation = S['Donation']
export type ErrorCode = S['ErrorCode']

/** Eventos SSE (packages/contracts/events.schema.json, $defs.sse). */
export interface SseOfferUpdated {
  offer_id: string
  status: OfferStatus
  qty_available: number
  price_cents?: number
}
export interface SseOrderUpdated {
  order_id: string
  status: OrderStatus
}
export type SseNotification = Notification
