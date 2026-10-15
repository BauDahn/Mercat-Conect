import type {
  Guardrails, Metrics, Notification, Offer, OfferDetail, Order, OrderStatus, PaymentIntent, Payout, Points,
  Donation, Product, ProducerOfferInput, ProducerOfferPatch, SimCompartment, SimLocker, Stall, StallInput, User,
} from './types'

export const API_BASE = '/api'

export class ApiError extends Error {
  status: number
  code: string
  messageKey: string
  params: Record<string, unknown>
  constructor(status: number, code: string, messageKey: string, params: Record<string, unknown>) {
    super(`${status} ${code}`)
    this.status = status
    this.code = code
    this.messageKey = messageKey
    this.params = params
  }
}

type Query = Record<string, string | number | boolean | undefined | null>

interface Opts {
  body?: unknown
  query?: Query
  headers?: Record<string, string>
}

async function request<T>(method: string, path: string, opts: Opts = {}): Promise<T> {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(opts.query ?? {})) if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
  const url = `${API_BASE}${path}${qs.size ? `?${qs}` : ''}`
  const headers: Record<string, string> = { Accept: 'application/json', ...opts.headers }
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(url, {
    method,
    headers,
    credentials: 'same-origin',
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  })
  if (!res.ok) {
    // Tolerante: el cuerpo de error puede no seguir el formato {error:{...}}.
    let code = res.status === 401 ? 'unauthorized' : res.status === 404 ? 'not_found' : 'bad_request'
    let key = `errors.${code}`
    let params: Record<string, unknown> = {}
    try {
      const j = await res.json()
      const e = j?.error ?? j?.detail?.error
      if (e && typeof e === 'object') {
        code = e.code ?? code
        key = e.message_key ?? `errors.${code}`
        params = e.params ?? {}
      }
    } catch {
      /* cuerpo vacío o no JSON */
    }
    throw new ApiError(res.status, code, key, params)
  }
  if (res.status === 204) return undefined as T
  const ct = res.headers.get('content-type') ?? ''
  return (ct.includes('json') ? await res.json() : await res.text()) as T
}

const get = <T>(p: string, query?: Query) => request<T>('GET', p, { query })
const post = <T>(p: string, body?: unknown, headers?: Record<string, string>) => request<T>('POST', p, { body, headers })

export interface OfferQuery { market?: string; category?: string; sort?: string; q?: string }

export const api = {
  healthz: () => get<{ status: string; demo_mode?: boolean }>('/healthz'),
  // auth
  register: (b: { email: string; password: string; display_name: string; lang: 'es' | 'va' }) => post<User>('/auth/register', b),
  login: (b: { email: string; password: string }) => post<User>('/auth/login', b),
  logout: () => post<void>('/auth/logout'),
  ageStart: () => get<{ redirect_url: string; state: string }>('/identity/age/start'),
  ageCallback: (state: string, token: string, kind: 'adult' | 'minor' = 'adult') => get<User>('/identity/age/callback', { state, token, kind }),
  me: () => get<User>('/me'),
  // ofertas
  listOffers: (q: OfferQuery = {}) => get<{ items: Offer[] }>('/offers', { ...q }),
  getOffer: (id: string, qty?: number) => get<OfferDetail>(`/offers/${id}`, { qty }),
  // pedidos
  createOrder: (items: { offer_id: string; qty: number }[], key: string) =>
    post<Order>('/orders', { items }, { 'Idempotency-Key': key }),
  listOrders: (status?: OrderStatus) => get<{ items: Order[] }>('/orders', { status }),
  getOrder: (id: string) => get<Order>(`/orders/${id}`),
  payOrder: (id: string, simulate?: 'success' | 'failure' | 'delay') =>
    post<PaymentIntent>(`/orders/${id}/pay`, simulate ? { simulate } : {}),
  // yo
  points: () => get<Points>('/me/points'),
  notifications: () => get<{ items: Notification[] }>('/notifications'),
  // productor
  producerListOffers: (status?: string) => get<{ items: OfferDetail[] }>('/producer/offers', { status }),
  producerCreateOffer: (b: ProducerOfferInput) => post<OfferDetail>('/producer/offers', b),
  producerUpdateOffer: (id: string, b: ProducerOfferPatch) => request<OfferDetail>('PATCH', `/producer/offers/${id}`, { body: b }),
  producerPublish: (id: string) => post<OfferDetail>(`/producer/offers/${id}/publish`),
  producerDeleteDraft: (id: string) => request<void>('DELETE', `/producer/offers/${id}`),
  deleteMe: () => request<void>('DELETE', '/me'),
  adminQuality: () => get<{ ok: boolean; checked_at: string; failures: { test: string; detail: string }[] }>('/admin/calidad'),
  producerWithdraw: (id: string) => post<OfferDetail>(`/producer/offers/${id}/withdraw`),
  producerStalls: () => get<{ items: Stall[] }>('/producer/stalls'),
  listProducts: (stallId: string) => get<{ items: Product[] }>('/products', { stall_id: stallId }),
  producerReject: (id: string) => post<Order>(`/producer/orders/${id}/reject`),
  producerOrders: (status?: OrderStatus) => get<{ items: Order[] }>('/producer/orders', { status }),
  producerAccept: (id: string) => post<Order>(`/producer/orders/${id}/accept`),
  producerDeposit: (id: string) => post<Order>(`/producer/orders/${id}/deposit`),
  producerPayouts: () => get<{ items: Payout[] }>('/producer/payouts'),
  // gestión
  adminMetrics: () => get<Metrics>('/admin/metrics'),
  adminGuardrails: (g: Guardrails) => request<Guardrails>('PUT', '/admin/guardrails', { body: g }),
  adminDonations: () => get<{ items: Donation[] }>('/admin/donations'),
  adminCreateStall: (s: StallInput) => post<Stall>('/admin/stalls', s),
  // demo
  demoClock: (b: { set?: string; advance_seconds?: number; paused?: boolean }) => post<{ now: string; paused?: boolean }>('/demo/clock', b),
  demoSimulate: (b: { offer_id?: string; buyers?: number; scenario?: 'peak' | 'steady' | 'closing' }) =>
    post<{ attempted?: number; held?: number; denied?: number }>('/demo/simulate', b),
  demoReset: () => post<void>('/demo/reset'),
  simLockers: () => get<{ items: SimLocker[] }>('/sim/lockers'),
  simLockerNetwork: (id: string, online: boolean) => post<SimLocker>(`/sim/lockers/${id}/network`, { online }),
  simLockerAction: (lockerId: string, slot: number, action: string, body?: { code?: string; celsius?: number }) =>
    post<SimCompartment>(`/sim/lockers/${lockerId}/compartments/${slot}/${action}`, body ?? {}),
}
