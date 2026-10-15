import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'
import { useI18n } from '../i18n'
import { errorText } from '../lib/hooks'

export function Spinner() {
  const { t } = useI18n()
  return <p role="status" className="p-6 text-center text-muted">{t('common.loading')}</p>
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n()
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border-2 border-danger bg-danger-soft p-4 text-danger">
      <Icon name="alert" className="h-6 w-6 shrink-0" />
      <span className="flex-1 font-medium">{errorText(t, error)}</span>
      {onRetry && <button className="btn btn-secondary" onClick={onRetry}>{t('common.retry')}</button>}
    </div>
  )
}

export function Notice({ icon = 'info', tone = 'info', children }: { icon?: IconName; tone?: 'info' | 'warn' | 'bad'; children: ReactNode }) {
  const cls = tone === 'bad' ? 'border-danger bg-danger-soft text-danger' : tone === 'warn' ? 'border-accent bg-accent-soft text-accent' : 'border-brand bg-brand-soft text-brand-dark'
  return (
    <div className={`flex items-start gap-3 rounded-xl border-2 p-3 ${cls}`}>
      <Icon name={icon} className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="font-medium">{children}</div>
    </div>
  )
}

/** Insignia: el estado nunca se comunica solo por color (icono + texto). */
export function Badge({ children, icon, tone = 'info' }: { children: ReactNode; icon?: IconName; tone?: 'info' | 'warn' | 'bad' | 'ok' }) {
  const cls =
    tone === 'warn' ? 'bg-accent-soft text-accent border-accent' : tone === 'bad' ? 'bg-danger-soft text-danger border-danger' : tone === 'ok' ? 'bg-brand-soft text-brand-dark border-brand' : 'bg-white text-ink border-line'
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-sm font-semibold ${cls}`}>
      {icon && <Icon name={icon} className="h-4 w-4" />}
      {children}
    </span>
  )
}

export function PageTitle({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="mb-4">
      <h1 className="text-2xl font-bold">{children}</h1>
      {sub && <p className="text-muted">{sub}</p>}
    </div>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-sm text-muted">{hint}</span>}
    </label>
  )
}
