import type { ReactNode } from 'react'
import type { Offer } from '../api/types'
import { productPhoto } from '../lib/photos'

interface Look { emoji: string; from: string; to: string }

/** Degradado y emoji del sistema por categoría (sin descargas). */
const LOOKS: Record<string, Look> = {
  fruta: { emoji: '🍊', from: '#ffb35c', to: '#f08a3c' },
  verdura: { emoji: '🥬', from: '#9fd3a8', to: '#4f9c63' },
  carne: { emoji: '🥩', from: '#f4a0a0', to: '#c4524f' },
  pescado: { emoji: '🐟', from: '#9ad7e8', to: '#3b8fb0' },
  panaderia: { emoji: '🥖', from: '#f7d28a', to: '#c8903a' },
  charcuteria: { emoji: '🧀', from: '#ffe08a', to: '#d9a21b' },
  lacteos: { emoji: '🥛', from: '#e9f1ff', to: '#9db8e0' },
  despensa: { emoji: '🫘', from: '#e8c9a0', to: '#a8744a' },
}
const FALLBACK: Look = { emoji: '🧺', from: '#d9e8c9', to: '#86a86a' }

export function categoryLook(category: string): Look {
  return LOOKS[category] ?? FALLBACK
}

/** Zona superior de la tarjeta: foto de ejemplo si la hay; si no, degradado con emoji grande. */
export function ProductArt({ offer, className = 'h-44', children }: { offer: Offer; className?: string; children?: ReactNode }) {
  const look = categoryLook(offer.stall.category)
  const photo = offer.product.photo_url || productPhoto(offer.product.name)
  return (
    <div className={`relative w-full overflow-hidden rounded-t-[inherit] ${className}`} style={photo ? undefined : { background: `linear-gradient(135deg, ${look.from}, ${look.to})` }}>
      {photo ? (
        <img src={photo} alt={offer.product.name} className="h-full w-full object-cover" loading="lazy" decoding="async" />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-[5.5rem] leading-none drop-shadow-sm" role="img" aria-label={offer.product.name}>
          <span aria-hidden="true">{look.emoji}</span>
        </div>
      )}
      {children}
    </div>
  )
}
