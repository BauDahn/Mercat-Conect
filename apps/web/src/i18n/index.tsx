import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import es from './es.json'
import va from './va.json'

export type Lang = 'es' | 'va'
type Dict = { [k: string]: string | Dict }

function flatten(d: Dict, prefix = '', out: Record<string, string> = {}): Record<string, string> {
  for (const [k, v] of Object.entries(d)) {
    const key = prefix ? `${prefix}.${k}` : k
    if (typeof v === 'string') out[key] = v
    else flatten(v, key, out)
  }
  return out
}

const dicts: Record<Lang, Record<string, string>> = { es: flatten(es as Dict), va: flatten(va as Dict) }

export type TFn = (key: string, params?: Record<string, unknown>, fallback?: string) => string

function interpolate(s: string, params?: Record<string, unknown>): string {
  if (!params) return s
  return s.replace(/\{(\w+)\}/g, (_, k: string) => (params[k] !== undefined ? String(params[k]) : `{${k}}`))
}

const KEY = 'mc_lang'

function initialLang(): Lang {
  try {
    const s = localStorage.getItem(KEY)
    if (s === 'es' || s === 'va') return s
  } catch {
    /* sin almacenamiento */
  }
  return navigator.language?.toLowerCase().startsWith('ca') ? 'va' : 'es'
}

interface I18n {
  lang: Lang
  setLang: (l: Lang) => void
  t: TFn
  /** true si existe la clave en el idioma activo o en castellano */
  has: (key: string) => boolean
}

const Ctx = createContext<I18n | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang)
  useEffect(() => {
    document.documentElement.lang = lang === 'va' ? 'ca' : 'es'
  }, [lang])
  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    try {
      localStorage.setItem(KEY, l)
    } catch {
      /* ignorar */
    }
  }, [])
  const value = useMemo<I18n>(() => {
    const has = (key: string) => key in dicts[lang] || key in dicts.es
    const t: TFn = (key, params, fallback) => {
      const one = params?.count === 1 ? `${key}_one` : null
      const s = (one && (dicts[lang][one] ?? dicts.es[one])) || dicts[lang][key] || dicts.es[key]
      return s !== undefined ? interpolate(s, params) : (fallback ?? key)
    }
    return { lang, setLang, t, has }
  }, [lang, setLang])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useI18n(): I18n {
  const c = useContext(Ctx)
  if (!c) throw new Error('I18nProvider ausente')
  return c
}
