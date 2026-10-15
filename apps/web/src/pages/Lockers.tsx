import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { SimCompartment, SimLocker } from '../api/types'
import { Badge, ErrorBox, Notice, PageTitle, Spinner } from '../components/ui'
import { Icon, type IconName } from '../components/Icon'
import { useI18n } from '../i18n'
import { useAsync } from '../lib/hooks'

const ST: Record<SimCompartment['status'], { icon: IconName; tone: 'ok' | 'info' | 'warn' | 'bad' }> = {
  FREE: { icon: 'check', tone: 'ok' },
  RESERVED: { icon: 'clock', tone: 'warn' },
  OCCUPIED: { icon: 'lock', tone: 'info' },
  OUT_OF_SERVICE: { icon: 'x', tone: 'bad' },
}

function Compartment({ l, c, onDone }: { l: SimLocker; c: SimCompartment; onDone: () => void }) {
  const { t } = useI18n()
  const [temp, setTemp] = useState(c.celsius ?? 4)
  const [err, setErr] = useState<unknown>(null)
  useEffect(() => setTemp(c.celsius ?? 4), [c.celsius])
  async function act(action: string, body?: { code?: string; celsius?: number }) {
    setErr(null)
    try {
      await api.simLockerAction(l.id, c.slot, action, body)
    } catch (e) {
      setErr(e)
    } finally {
      onDone()
    }
  }
  const s = ST[c.status]
  const hot = c.celsius != null && c.celsius > 8
  return (
    <li className="card space-y-2 p-3">
      <div className="flex items-center justify-between">
        <h3 className="font-bold">{t('lock.slot', { n: c.slot })} · {c.size}</h3>
        <Badge icon={s.icon} tone={s.tone}>{t(`lock.status.${c.status}`)}</Badge>
      </div>
      <p className="flex items-center gap-1 text-sm">
        <Icon name={c.door === 'OPEN' ? 'x' : 'lock'} className="h-4 w-4" /> {c.door === 'OPEN' ? t('lock.open') : t('lock.closed')}
        {' · '}{c.zone === 'REFRIGERATED' ? t('offer.lockerCold') : t('offer.lockerAmbient')}
      </p>
      {c.celsius != null && (
        <p className={`flex items-center gap-1 font-semibold ${hot ? 'text-danger' : ''}`}>
          <Icon name="therm" className="h-5 w-5" /> {c.celsius.toFixed(1)} °C {hot && <span>({t('lock.tooHot')})</span>}
        </p>
      )}
      {!!err && <ErrorBox error={err} />}
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-secondary" onClick={() => act('close_door')}>{t('lock.close')}</button>
        <button className="btn btn-secondary" onClick={() => act('open_door')}>{t('lock.openBtn')}</button>
        <button className="btn btn-danger" onClick={() => act('fail')}>{t('lock.fail')}</button>
      </div>
      <label className="block text-sm font-semibold">
        {t('lock.temp')}: {temp} °C
        <input type="range" min={0} max={20} step={0.5} value={temp} className="h-10 w-full" onChange={(e) => setTemp(Number(e.target.value))} onPointerUp={() => act('set_temperature', { celsius: temp })} onKeyUp={() => act('set_temperature', { celsius: temp })} />
      </label>
    </li>
  )
}

function Keypad({ l, c }: { l: SimLocker; c: SimCompartment[] }) {
  const { t } = useI18n()
  const [code, setCode] = useState('')
  const [slot, setSlot] = useState(c.find((x) => x.status === 'OCCUPIED')?.slot ?? c[0]?.slot ?? 1)
  const [res, setRes] = useState<{ ok: boolean; err?: unknown } | null>(null)
  async function enter() {
    try {
      await api.simLockerAction(l.id, slot, 'enter_code', { code })
      setRes({ ok: true })
      setCode('')
    } catch (e) {
      setRes({ ok: false, err: e })
    }
  }
  return (
    <div className="card space-y-3 p-4">
      <h3 className="font-bold">{t('lock.keypad')}</h3>
      <label className="block text-sm font-semibold">{t('lock.slotSel')}
        <select className="input" value={slot} onChange={(e) => setSlot(Number(e.target.value))}>{c.map((x) => <option key={x.slot} value={x.slot}>{x.slot}</option>)}</select>
      </label>
      <output className="block min-h-12 rounded-lg bg-ink px-3 py-2 text-right font-mono text-2xl tracking-widest text-white" aria-label={t('lock.codeLabel')}>{code || '–'}</output>
      <div className="grid grid-cols-3 gap-2">
        {['1', '2', '3', '4', '5', '6', '7', '8', '9', 'C', '0', 'OK'].map((k) => (
          <button key={k} className="btn btn-secondary text-xl" onClick={() => (k === 'C' ? setCode('') : k === 'OK' ? enter() : setCode((x) => (x + k).slice(0, 12)))}>{k}</button>
        ))}
      </div>
      {res?.ok && <Notice icon="check">{t('lock.codeOk')}</Notice>}
      {res && !res.ok && <ErrorBox error={res.err} />}
    </div>
  )
}

export function LockersPage() {
  const { t } = useI18n()
  const res = useAsync(() => api.simLockers(), [])
  const { reload } = res
  useEffect(() => {
    const i = window.setInterval(reload, 4000)
    return () => window.clearInterval(i)
  }, [reload])
  return (
    <div className="space-y-4">
      <PageTitle sub={t('lock.sub')}>{t('lock.title')}</PageTitle>
      {res.loading && <Spinner />}
      {!!res.error && <ErrorBox error={res.error} onRetry={res.reload} />}
      {res.data?.items.map((l) => (
        <section key={l.id} className="space-y-3" aria-label={l.device_id}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xl font-bold">{l.device_id}</h2>
            <Badge icon="wifi" tone={l.online === false ? 'bad' : 'ok'}>{l.online === false ? t('lock.offline') : t('lock.online')}</Badge>
            <button className="btn btn-secondary" onClick={() => api.simLockerNetwork(l.id, l.online === false).finally(reload)}>
              {l.online === false ? t('lock.restore') : t('lock.cut')}
            </button>
          </div>
          <ul className="grid gap-3 sm:grid-cols-2">
            {l.compartments.map((c) => <Compartment key={c.slot} l={l} c={c} onDone={reload} />)}
          </ul>
          <Keypad l={l} c={l.compartments} />
        </section>
      ))}
    </div>
  )
}
