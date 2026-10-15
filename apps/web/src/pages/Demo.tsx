import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorBox, Notice, PageTitle } from '../components/ui'
import { Icon } from '../components/Icon'
import { useI18n } from '../i18n'
import { useServerTime } from '../state/servertime'
import { madridDate, madridISO } from '../lib/format'

const JUMPS = ['11:30', '12:30', '13:00', '13:45', '15:00']
const LEVELS = {
  low: { scenario: 'steady', buyers: 5 },
  mid: { scenario: 'steady', buyers: 40 },
  high: { scenario: 'peak', buyers: 200 },
} as const

export function DemoPage() {
  const { t, lang } = useI18n()
  const { nowMs, sync, demoMode, paused } = useServerTime()
  const [err, setErr] = useState<unknown>(null)
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)

  async function run(fn: () => Promise<string | void>) {
    setBusy(true)
    setErr(null)
    setMsg('')
    try {
      setMsg((await fn()) ?? '')
    } catch (e) {
      setErr(e)
    } finally {
      setBusy(false)
    }
  }
  const setClock = (hm: string) => run(async () => {
    const day = madridDate(new Date(nowMs()))
    const r = await api.demoClock({ set: madridISO(day, hm) })
    await sync(r.now, r.paused)
  })
  const advance = () => run(async () => {
    const r = await api.demoClock({ advance_seconds: 600 })
    await sync(r.now, r.paused)
  })
  const togglePause = () => run(async () => {
    const r = await api.demoClock({ paused: !paused })
    await sync(r.now, r.paused)
  })
  const simulate = (lvl: keyof typeof LEVELS) => run(async () => {
    const r = await api.demoSimulate({ ...LEVELS[lvl] })
    return t('demo.simResult', { a: r.attempted ?? 0, h: r.held ?? 0, d: r.denied ?? 0 })
  })
  const reset = () => run(async () => {
    await api.demoReset()
    setConfirmReset(false)
    await sync()
    return t('demo.resetDone')
  })

  return (
    <div className="space-y-4">
      <PageTitle sub={t('demo.sub')}>{t('demo.title')}</PageTitle>
      {!demoMode && <Notice icon="alert" tone="warn">{t('demo.off')}</Notice>}
      {!!err && <ErrorBox error={err} />}
      {msg && <Notice icon="check">{msg}</Notice>}

      <section className="card space-y-3 p-4" aria-labelledby="clk-h">
        <h2 id="clk-h" className="flex items-center gap-2 text-lg font-bold"><Icon name="clock" /> {t('demo.clock')}</h2>
        <p className="text-2xl font-bold" aria-live="polite">{new Intl.DateTimeFormat(lang === 'va' ? 'ca-ES' : 'es-ES', { dateStyle: 'short', timeStyle: 'medium', timeZone: 'Europe/Madrid' }).format(nowMs())}{paused ? ` · ${t('demo.paused')}` : ''}</p>
        <div className="flex flex-wrap gap-2">
          {JUMPS.map((hm) => <button key={hm} className="btn btn-secondary" disabled={busy} onClick={() => setClock(hm)}>{hm}</button>)}
          <button className="btn btn-secondary" disabled={busy} onClick={advance}>+10 min</button>
          <button className="btn btn-secondary" disabled={busy} onClick={togglePause} aria-pressed={paused}>{paused ? t('demo.resume') : t('demo.pause')}</button>
        </div>
      </section>

      <section className="card space-y-3 p-4" aria-labelledby="sim-h">
        <h2 id="sim-h" className="flex items-center gap-2 text-lg font-bold"><Icon name="user" /> {t('demo.demand')}</h2>
        <p className="text-sm text-muted">{t('demo.demandHint')}</p>
        <div className="flex flex-wrap gap-2">
          {(['low', 'mid', 'high'] as const).map((l) => <button key={l} className="btn btn-primary" disabled={busy} onClick={() => simulate(l)}>{t(`demo.level.${l}`)}</button>)}
        </div>
      </section>

      <section className="card space-y-3 p-4" aria-labelledby="inc-h">
        <h2 id="inc-h" className="flex items-center gap-2 text-lg font-bold"><Icon name="alert" /> {t('demo.incidents')}</h2>
        <label className="flex min-h-12 items-center gap-2 font-semibold">
          <input type="checkbox" className="h-6 w-6" defaultChecked={(() => { try { return localStorage.getItem('mc_sim_pay') === 'failure' } catch { return false } })()}
            onChange={(e) => { try { if (e.target.checked) localStorage.setItem('mc_sim_pay', 'failure'); else localStorage.removeItem('mc_sim_pay') } catch { /* ignorar */ } }} />
          {t('demo.payFail')}
        </label>
        <Link className="btn btn-secondary" to="/sim/taquillas"><Icon name="therm" /> {t('demo.coldAlarm')}</Link>
      </section>

      <section className="card space-y-3 p-4" aria-labelledby="rst-h">
        <h2 id="rst-h" className="flex items-center gap-2 text-lg font-bold"><Icon name="refresh" /> {t('demo.reset')}</h2>
        {confirmReset ? (
          <div className="flex gap-2">
            <button className="btn btn-danger" disabled={busy} onClick={reset}>{t('demo.resetConfirm')}</button>
            <button className="btn btn-secondary" onClick={() => setConfirmReset(false)}>{t('common.cancel')}</button>
          </div>
        ) : (
          <button className="btn btn-danger" onClick={() => setConfirmReset(true)}>{t('demo.reset')}</button>
        )}
      </section>
    </div>
  )
}
