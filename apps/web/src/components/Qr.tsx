import { useMemo } from 'react'
import qrcode from 'qrcode-generator'

/** QR generado en el cliente (sin servicios externos). */
export function Qr({ value, label }: { value: string; label: string }) {
  const { n, d } = useMemo(() => {
    const qr = qrcode(0, 'M')
    qr.addData(value)
    qr.make()
    const n = qr.getModuleCount()
    let d = ''
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) d += `M${c} ${r}h1v1h-1z`
    return { n, d }
  }, [value])
  return (
    <svg viewBox={`-2 -2 ${n + 4} ${n + 4}`} className="h-48 w-48 bg-white" role="img" aria-label={label} shapeRendering="crispEdges">
      <path d={d} fill="#000" />
    </svg>
  )
}
