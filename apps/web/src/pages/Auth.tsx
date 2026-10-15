import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { User } from '../api/types'
import { ErrorBox, Field, PageTitle } from '../components/ui'
import { useI18n } from '../i18n'
import { useAuth } from '../state/auth'

function home(u: User, from?: string): string {
  if (from && from !== '/entrar') return from
  if (u.role === 'PRODUCER') return '/productor/pedidos'
  if (u.role === 'MANAGER' || u.role === 'ADMIN') return '/admin'
  return '/'
}

export function Login() {
  const { t } = useI18n()
  const { setUser } = useAuth()
  const nav = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      const u = await api.login({ email, password })
      setUser(u)
      nav(home(u, from), { replace: true })
    } catch (x) {
      setErr(x)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form onSubmit={submit} className="card mx-auto max-w-md space-y-4 p-5">
      <PageTitle sub={t('auth.demoHint')}>{t('auth.login')}</PageTitle>
      {!!err && <ErrorBox error={err} />}
      <Field label={t('auth.email')}><input className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
      <Field label={t('auth.password')}><input className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
      <button className="btn btn-primary w-full" disabled={busy}>{t('auth.login')}</button>
      <p className="text-center">{t('auth.noAccount')} <Link className="font-semibold text-brand underline" to="/registro">{t('auth.register')}</Link></p>
    </form>
  )
}

export function Register() {
  const { t, lang } = useI18n()
  const { setUser } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      const u = await api.register({ email, password, display_name: name, lang })
      setUser(u)
      nav('/verificar-edad', { replace: true }) // la cuenta queda PENDING hasta verificar la edad
    } catch (x) {
      setErr(x)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form onSubmit={submit} className="card mx-auto max-w-md space-y-4 p-5">
      <PageTitle sub={t('auth.registerSub')}>{t('auth.register')}</PageTitle>
      {!!err && <ErrorBox error={err} />}
      <Field label={t('auth.name')}><input className="input" autoComplete="name" required value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label={t('auth.email')}><input className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
      <Field label={t('auth.password')} hint={t('auth.passwordHint')}><input className="input" type="password" autoComplete="new-password" minLength={8} required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
      <button className="btn btn-primary w-full" disabled={busy}>{t('auth.register')}</button>
      <p className="text-center">{t('auth.haveAccount')} <Link className="font-semibold text-brand underline" to="/entrar">{t('auth.login')}</Link></p>
    </form>
  )
}
