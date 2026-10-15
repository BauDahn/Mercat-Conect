import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorBox, Field, Notice, PageTitle } from '../components/ui'
import { useI18n } from '../i18n'
import { useAuth } from '../state/auth'

/** Verificación de edad simulada: token = DNI inventado, kind = adult|minor (el servidor solo guarda un hash). */
export function AgeVerify() {
  const { t } = useI18n()
  const { user, setUser } = useAuth()
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [state, setState] = useState(params.get('state') ?? '')
  const [token, setToken] = useState(params.get('token') ?? '')
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const auto = useRef(false)

  async function callback(s: string, tk: string, kind: 'adult' | 'minor' = 'adult') {
    setBusy(true)
    setErr(null)
    try {
      const u = await api.ageCallback(s, tk, kind)
      setUser(u)
      setDone(true)
      window.setTimeout(() => nav('/', { replace: true }), 1500)
    } catch (e) {
      setErr(e)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (auto.current || user?.age_verified) return
    auto.current = true
    if (params.get('state') && params.get('token')) {
      void callback(params.get('state')!, params.get('token')!)
      return
    }
    api.ageStart().then(
      (r) => {
        setState(r.state)
        try {
          const u = new URL(r.redirect_url, window.location.origin)
          const tk = u.searchParams.get('token')
          if (tk) setToken(tk)
        } catch {
          /* redirect_url no es una URL: se ignora */
        }
      },
      setErr,
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function submit(e: FormEvent) {
    e.preventDefault()
  }

  if (user?.age_verified && !done) return <Notice icon="check">{t('age.already')}</Notice>
  return (
    <form onSubmit={submit} className="card mx-auto max-w-md space-y-4 p-5">
      <PageTitle sub={t('age.sub')}>{t('age.title')}</PageTitle>
      <Notice icon="info">{t('age.privacy')}</Notice>
      {done && <Notice icon="check">{t('age.ok')}</Notice>}
      {!!err && <ErrorBox error={err} />}
      <Field label={t("age.doc")} hint={t('age.docHint')}>
        <input className="input" required value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" />
      </Field>
      <div className="grid gap-2 sm:grid-cols-2">
        <button type="button" className="btn btn-primary" disabled={busy || !state || !token} onClick={() => callback(state, token, 'adult')}>{t('age.adult')}</button>
        <button type="button" className="btn btn-secondary" disabled={busy || !state || !token} onClick={() => callback(state, token, 'minor')}>{t('age.minor')}</button>
      </div>
    </form>
  )
}
