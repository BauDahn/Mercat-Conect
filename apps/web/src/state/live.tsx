import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { API_BASE } from '../api/client'
import { useAuth } from './auth'

export type LiveType = 'offer.updated' | 'order.updated' | 'notification.created' | 'reconnect'
type Handler = (data: unknown) => void

interface Live {
  connected: boolean
  subscribe: (type: LiveType, h: Handler) => () => void
}

const Ctx = createContext<Live | null>(null)
const TYPES: LiveType[] = ['offer.updated', 'order.updated', 'notification.created']

export function LiveProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [connected, setConnected] = useState(false)
  const handlers = useRef(new Map<LiveType, Set<Handler>>())

  const api = useMemo<Live>(
    () => ({
      connected,
      subscribe(type, h) {
        const set = handlers.current.get(type) ?? new Set()
        set.add(h)
        handlers.current.set(type, set)
        return () => void set.delete(h)
      },
    }),
    [connected],
  )

  const uid = user?.id
  useEffect(() => {
    if (!uid) return
    let es: EventSource | null = null
    let timer: number | undefined
    let delay = 1000
    let wasDown = false
    let stopped = false
    const emit = (type: LiveType, data: unknown) => handlers.current.get(type)?.forEach((h) => h(data))

    const open = () => {
      es = new EventSource(`${API_BASE}/stream`, { withCredentials: true })
      es.onopen = () => {
        setConnected(true)
        delay = 1000
        if (wasDown) emit('reconnect', null) // recargar estado perdido
        wasDown = false
      }
      for (const t of TYPES) {
        es.addEventListener(t, (ev) => {
          try {
            emit(t, JSON.parse((ev as MessageEvent).data))
          } catch {
            /* evento mal formado: se ignora */
          }
        })
      }
      es.onerror = () => {
        setConnected(false)
        wasDown = true
        es?.close()
        if (stopped) return
        // EventSource no expone el estado HTTP: se sondea para distinguir 429 (espera creciente, respeta Retry-After).
        const ctl = new AbortController()
        fetch(`${API_BASE}/stream`, { credentials: 'same-origin', headers: { Accept: 'text/event-stream' }, signal: ctl.signal })
          .then((r) => {
            ctl.abort()
            if (r.status === 429) {
              const ra = Number(r.headers.get('Retry-After')) * 1000
              delay = Math.min(Math.max(delay * 2, Number.isFinite(ra) ? ra : 0, 5000), 60000)
            }
          })
          .catch(() => undefined)
          .finally(() => {
            if (stopped) return
            timer = window.setTimeout(open, delay)
            if (delay < 15000) delay = Math.min(delay * 2, 15000)
          })
      }
    }
    open()
    return () => {
      stopped = true
      window.clearTimeout(timer)
      es?.close()
      setConnected(false)
    }
  }, [uid])

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>
}

/** Suscribe un manejador a un evento SSE mientras el componente está montado. */
export function useLive(type: LiveType, handler: Handler) {
  const c = useContext(Ctx)
  const ref = useRef(handler)
  useEffect(() => {
    ref.current = handler
  })
  const subscribe = c?.subscribe
  useEffect(() => subscribe?.(type, (d) => ref.current(d)), [subscribe, type])
}

export function useLiveConnected(): boolean {
  return useContext(Ctx)?.connected ?? false
}
