import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/client'

interface ServerTime {
  demoMode: boolean
  /** Hora del servidor (DemoClock en demo) en ms. */
  nowMs: () => number
  /** Vuelve a leer la hora del servidor (tras mover el reloj de demo). */
  paused: boolean
  sync: (serverNowIso?: string, paused?: boolean) => Promise<void>
  tick: number
}

const Ctx = createContext<ServerTime | null>(null)

export function ServerTimeProvider({ children }: { children: ReactNode }) {
  const [demoMode, setDemoMode] = useState(false)
  const [offset, setOffset] = useState(0)
  const [paused, setPaused] = useState(false)
  const [frozen, setFrozen] = useState(0)
  const [tick, setTick] = useState(0)

  const sync = useCallback(async (iso?: string, p?: boolean) => {
    try {
      let now = iso
      let pz = p
      if (!now) {
        // Solo demo: advance_seconds=0 devuelve la hora vigente sin moverla.
        const r = await api.demoClock({ advance_seconds: 0 })
        now = r.now
        pz = r.paused
      }
      setOffset(new Date(now).getTime() - Date.now())
      setFrozen(new Date(now).getTime())
      setPaused(pz === true)
    } catch {
      setOffset(0) // producción: hora local
    }
    setTick((n) => n + 1)
  }, [])

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const h = await api.healthz()
        if (!alive) return
        setDemoMode(h.demo_mode === true)
        if (h.demo_mode) await sync()
      } catch {
        /* API caída: se verá en cada pantalla */
      }
    })()
    return () => {
      alive = false
    }
  }, [sync])

  useEffect(() => {
    // El reloj corre solo (1 s = 1 s); se refresca la vista cada segundo en demo y se re-sincroniza cada 30 s.
    const id = window.setInterval(() => setTick((n) => n + 1), demoMode ? 1000 : 20000)
    const re = demoMode ? window.setInterval(() => void sync(), 30000) : undefined
    return () => {
      window.clearInterval(id)
      window.clearInterval(re)
    }
  }, [demoMode, sync])

  const value = useMemo(() => ({ demoMode, nowMs: () => (paused ? frozen : Date.now() + offset), paused, sync, tick }), [demoMode, offset, paused, frozen, sync, tick])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useServerTime(): ServerTime {
  const c = useContext(Ctx)
  if (!c) throw new Error('ServerTimeProvider ausente')
  return c
}
