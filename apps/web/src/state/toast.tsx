import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { Icon } from '../components/Icon'

interface ToastItem { id: number; text: string; kind: 'info' | 'error' | 'ok' }
const Ctx = createContext<(text: string, kind?: ToastItem['kind']) => void>(() => {})
let seq = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const push = useCallback((text: string, kind: ToastItem['kind'] = 'info') => {
    const id = ++seq
    setItems((l) => [...l, { id, text, kind }])
    window.setTimeout(() => setItems((l) => l.filter((x) => x.id !== id)), 6000)
  }, [])
  const v = useMemo(() => push, [push])
  return (
    <Ctx.Provider value={v}>
      {children}
      <div className="fixed inset-x-0 bottom-20 z-50 flex flex-col items-center gap-2 px-4 pointer-events-none" role="status" aria-live="polite">
        {items.map((i) => (
          <div key={i.id} className="pointer-events-auto flex max-w-md items-start gap-2 rounded-xl border border-line bg-white px-4 py-3 text-sm shadow-lg">
            <Icon name={i.kind === 'error' ? 'alert' : i.kind === 'ok' ? 'check' : 'bell'} className="mt-0.5 h-5 w-5 shrink-0 text-brand" />
            <span>{i.text}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  )
}

export function useToast() {
  return useContext(Ctx)
}
