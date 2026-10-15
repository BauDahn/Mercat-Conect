import type { ReactNode, ButtonHTMLAttributes } from 'react'
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

/** Botón con variantes del sistema de diseño (área táctil ≥ 48 px). */
export function Button({ variant = 'primary', icon, children, className = '', ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'accent' | 'secondary' | 'ghost'; icon?: IconName }) {
  const v = variant === 'accent' ? 'btn-accent' : variant === 'secondary' ? 'btn-secondary' : variant === 'ghost' ? 'btn-ghost' : 'btn-primary'
  return (
    <button className={`btn ${v} ${className}`} {...rest}>
      {icon && <Icon name={icon} className="h-5 w-5" />}
      {children}
    </button>
  )
}

/** Esqueleto de carga con la forma de una tarjeta de oferta. */
export function Skeleton({ count = 4, compact = false }: { count?: number; compact?: boolean }) {
  const { t } = useI18n()
  return (
    <div role="status" aria-label={t('common.loading')} className={compact ? 'flex gap-4 overflow-hidden' : 'grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'}>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className={`card overflow-hidden ${compact ? 'w-64 shrink-0' : ''}`} aria-hidden="true">
          <div className={`skeleton rounded-none ${compact ? 'h-36' : 'h-40'}`} />
          <div className="space-y-3 p-4">
            <div className="skeleton h-4 w-1/2" />
            <div className="skeleton h-5 w-4/5" />
            <div className="skeleton h-7 w-1/3" />
            <div className="skeleton h-4 w-2/3" />
          </div>
        </div>
      ))}
    </div>
  )
}

/** Estado vacío amable: icono, explicación y, si se pasa, una acción. */
export function EmptyState({ icon = 'basket', title, children, action }: { icon?: IconName; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center gap-3 px-6 py-10 text-center">
      <span className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-soft text-brand-dark">
        <Icon name={icon} className="h-8 w-8" />
      </span>
      <h3 className="text-xl font-bold">{title}</h3>
      {children && <div className="max-w-md text-muted">{children}</div>}
      {action}
    </div>
  )
}

/** Cifra destacada (KPI) con etiqueta y tono opcional. */
export function Stat({ label, value, hint, icon, tone = 'brand' }: { label: string; value: ReactNode; hint?: ReactNode; icon?: IconName; tone?: 'brand' | 'accent' | 'ink' }) {
  const color = tone === 'accent' ? 'text-accent' : tone === 'ink' ? 'text-ink' : 'text-brand-dark'
  return (
    <div className="card flex flex-col gap-1 p-5">
      <div className="flex items-center gap-2 text-sm font-semibold text-muted">
        {icon && <Icon name={icon} className="h-5 w-5" />}
        {label}
      </div>
      <p className={`text-3xl font-extrabold tabular-nums ${color}`}>{value}</p>
      {hint && <p className="text-sm text-muted">{hint}</p>}
    </div>
  )
}
