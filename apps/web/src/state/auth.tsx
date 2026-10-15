import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, ApiError } from '../api/client'
import type { Points, User } from '../api/types'

interface Auth {
  user: User | null
  points: Points | null
  ready: boolean
  setUser: (u: User | null) => void
  refreshPoints: () => Promise<void>
  logout: () => Promise<void>
}

const Ctx = createContext<Auth | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(null)
  const [points, setPoints] = useState<Points | null>(null)
  const [ready, setReady] = useState(false)

  const setUser = useCallback((u: User | null) => {
    setUserState(u)
    if (!u) setPoints(null)
  }, [])

  const refreshPoints = useCallback(async () => {
    try {
      setPoints(await api.points())
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setUser(null)
    }
  }, [setUser])

  // La sesión (cookie) se valida con GET /me; no se guarda el usuario en el navegador.
  useEffect(() => {
    let alive = true
    api.me().then(
      (u) => alive && setUserState(u),
      () => undefined,
    ).finally(() => alive && setReady(true))
    return () => {
      alive = false
    }
  }, [])

  // Tras iniciar sesión o verificar la edad, recarga el saldo.
  const uid = user?.id
  const ageOk = user?.age_verified
  useEffect(() => {
    if (uid) void refreshPoints()
  }, [uid, ageOk, refreshPoints])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      /* la sesión local se limpia igualmente */
    }
    setUser(null)
  }, [setUser])

  const value = useMemo(() => ({ user, points, ready, setUser, refreshPoints, logout }), [user, points, ready, setUser, refreshPoints, logout])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth(): Auth {
  const c = useContext(Ctx)
  if (!c) throw new Error('AuthProvider ausente')
  return c
}
