import { Icon, type IconName } from './Icon'
import type { Offer } from '../api/types'

function glyph(cat: string, name: string): { icon: IconName; bg: string } {
  const s = `${cat} ${name}`.toLowerCase()
  if (/pesc|peix|merluz|gamba|marisc/.test(s)) return { icon: 'fish', bg: 'bg-sky-100 text-sky-900' }
  if (/fruta|fruit|naranj|taronj|verdur|hortal|tomat|lechug/.test(s)) return { icon: 'leaf', bg: 'bg-brand-soft text-brand-dark' }
  return { icon: 'basket', bg: 'bg-accent-soft text-accent' }
}

export function ProductArt({ offer, className = 'h-28' }: { offer: Offer; className?: string }) {
  const url = offer.product.photo_url
  if (url) return <img src={url} alt={offer.product.name} className={`${className} w-full rounded-t-xl object-cover`} loading="lazy" />
  const g = glyph(offer.stall.category, offer.product.name)
  return (
    <div className={`${className} flex w-full items-center justify-center rounded-t-xl ${g.bg}`} role="img" aria-label={offer.product.name}>
      <Icon name={g.icon} className="h-12 w-12" />
    </div>
  )
}
