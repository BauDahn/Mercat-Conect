const TZ = 'Europe/Madrid'

export function locale(lang: string): string {
  return lang === 'va' ? 'ca-ES' : 'es-ES'
}

export function money(cents: number, lang: string): string {
  return new Intl.NumberFormat(locale(lang), { style: 'currency', currency: 'EUR' }).format(cents / 100)
}

export function timeHM(iso: string, lang: string): string {
  return new Intl.DateTimeFormat(locale(lang), { hour: '2-digit', minute: '2-digit', timeZone: TZ }).format(new Date(iso))
}

/** Distancia legible: "120 m" o "1,4 km" según idioma (redondeo a 10 m). */
export function distanceLabel(m: number, lang: string): string {
  if (m < 1000) return `${Math.max(10, Math.round(m / 10) * 10)} m`
  return `${new Intl.NumberFormat(locale(lang), { maximumFractionDigits: 1 }).format(m / 1000)} km`
}

export function dateLong(iso: string, lang: string): string {
  return new Intl.DateTimeFormat(locale(lang), { weekday: 'long', day: 'numeric', month: 'long', timeZone: TZ }).format(new Date(iso))
}

export function dateTime(iso: string, lang: string): string {
  return new Intl.DateTimeFormat(locale(lang), {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZone: TZ,
  }).format(new Date(iso))
}

export function weekday(iso: string, lang: string): string {
  return new Intl.DateTimeFormat(locale(lang), { weekday: 'long', timeZone: TZ }).format(new Date(iso))
}

/** Parte "YYYY-MM-DD" del instante en hora de Madrid. */
export function madridDate(d: Date): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d)
}

/** Desfase de Madrid respecto a UTC en el instante dado, p. ej. "+02:00". */
function madridOffset(d: Date): string {
  const part = new Intl.DateTimeFormat('en', { timeZone: TZ, timeZoneName: 'longOffset' })
    .formatToParts(d)
    .find((p) => p.type === 'timeZoneName')?.value ?? 'GMT+01:00'
  const m = part.match(/GMT([+-]\d{2}:\d{2})/)
  return m ? m[1] : '+00:00'
}

/** ISO con desfase para "YYYY-MM-DD" + "HH:MM" en hora de Madrid. */
export function madridISO(date: string, hm: string): string {
  const probe = new Date(`${date}T${hm}:00Z`)
  return `${date}T${hm}:00${madridOffset(probe)}`
}

export function minutesLeft(untilIso: string, nowMs: number): number {
  return Math.ceil((new Date(untilIso).getTime() - nowMs) / 60000)
}

export function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return 'k-' + Math.random().toString(36).slice(2) + Date.now().toString(36)
}
