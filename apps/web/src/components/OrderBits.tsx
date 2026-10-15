import type { Order, OrderStatus } from '../api/types'
import { Badge } from './ui'
import type { IconName } from './Icon'
import { useI18n } from '../i18n'

const META: Record<OrderStatus, { icon: IconName; tone: 'info' | 'warn' | 'bad' | 'ok' }> = {
  HELD: { icon: 'clock', tone: 'warn' },
  PAID: { icon: 'check', tone: 'info' },
  EXPIRED_HOLD: { icon: 'x', tone: 'bad' },
  PREPARING: { icon: 'tool', tone: 'info' },
  CANCELLED_BY_PRODUCER: { icon: 'x', tone: 'bad' },
  IN_LOCKER: { icon: 'lock', tone: 'ok' },
  PICKED_UP: { icon: 'check', tone: 'ok' },
  NO_SHOW: { icon: 'alert', tone: 'bad' },
  TEMP_ALARM: { icon: 'therm', tone: 'bad' },
  REFUNDED: { icon: 'euro', tone: 'info' },
}

export function StatusBadge({ s }: { s: OrderStatus }) {
  const { t } = useI18n()
  const m = META[s] ?? { icon: 'info' as IconName, tone: 'info' as const }
  return <Badge icon={m.icon} tone={m.tone}>{t(`order.status.${s}`, {}, s)}</Badge>
}

export function orderTitle(o: Order): string {
  return o.items.map((i) => `${i.qty}× ${i.product_name ?? ''}`.trim()).join(', ')
}
