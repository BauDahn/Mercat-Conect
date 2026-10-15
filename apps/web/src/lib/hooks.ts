import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../api/client'
import type { TFn } from '../i18n'

export interface AsyncState<T> {
  data: T | undefined
  error: unknown
  loading: boolean
  reload: () => void
}

/** Carga asíncrona sencilla; `reload` recarga sin parpadeo. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | undefined>(undefined)
  const [error, setError] = useState<unknown>(undefined)
  const [loading, setLoading] = useState(true)
  const [n, setN] = useState(0)
  useEffect(() => {
    let alive = true
    fn().then(
      (d) => {
        if (!alive) return
        setData(d)
        setError(undefined)
        setLoading(false)
      },
      (e) => {
        if (!alive) return
        setError(e)
        setLoading(false)
      },
    )
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [n, ...deps])
  const reload = useCallback(() => setN((x) => x + 1), [])
  return { data, error, loading, reload }
}

export function errorText(t: TFn, e: unknown): string {
  if (e instanceof ApiError) {
    return t(e.messageKey, e.params, t(`errors.${e.code}`, e.params, t('errors.generic')))
  }
  return t('errors.network')
}

export function useOnline(): boolean {
  const [on, setOn] = useState(navigator.onLine)
  useEffect(() => {
    const u = () => setOn(true)
    const d = () => setOn(false)
    window.addEventListener('online', u)
    window.addEventListener('offline', d)
    return () => {
      window.removeEventListener('online', u)
      window.removeEventListener('offline', d)
    }
  }, [])
  return on
}
