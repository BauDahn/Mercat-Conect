// Iconos SVG propios (trazo 24x24). Sin dependencias externas.
const P: Record<string, string> = {
  leaf: 'M20 4C10 4 4 9 4 16c0 2 1 4 3 4 7 0 13-6 13-16zM4 20c3-5 7-8 11-10',
  fish: 'M2 12c4-6 11-7 15-3l5-3v12l-5-3c-4 4-11 3-15-3zM15 11h.01',
  basket: 'M3 9h18l-2 11H5L3 9zM8 9l3-5M16 9l-3-5M9 13v4M15 13v4M12 13v4',
  home: 'M3 11l9-8 9 8M5 10v10h14V10M10 20v-6h4v6',
  bag: 'M5 8h14l1 13H4L5 8zM9 8V6a3 3 0 016 0v2',
  star: 'M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9L12 3z',
  user: 'M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c0-4 3.6-7 8-7s8 3 8 7',
  store: 'M3 9l1-5h16l1 5M3 9c0 2 4 2 4.5 0 .5 2 4 2 4.5 0 .5 2 4 2 4.5 0C17 11 21 11 21 9M5 11v9h14v-9M10 20v-5h4v5',
  chart: 'M4 20V4M4 20h16M8 16v-5M12 16V8M16 16v-3',
  flask: 'M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3',
  lock: 'M6 11h12v10H6zM8 11V8a4 4 0 018 0v3M12 15v2',
  clock: 'M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2',
  search: 'M11 18a7 7 0 100-14 7 7 0 000 14zM21 21l-5-5',
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  check: 'M5 12l5 5 9-10',
  x: 'M6 6l12 12M18 6L6 18',
  alert: 'M12 3l10 18H2L12 3zM12 10v5M12 18h.01',
  info: 'M12 21a9 9 0 100-18 9 9 0 000 18zM12 11v5M12 8h.01',
  bell: 'M6 16V11a6 6 0 0112 0v5l2 2H4l2-2zM10 21h4',
  globe: 'M12 21a9 9 0 100-18 9 9 0 000 18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18',
  therm: 'M10 14V5a2 2 0 014 0v9a4 4 0 11-4 0zM12 10v6',
  wifi: 'M2 9c6-5 14-5 20 0M5 13c4-3 10-3 14 0M8.5 16.5c2-1.5 5-1.5 7 0M12 20h.01',
  box: 'M3 7l9-4 9 4v10l-9 4-9-4V7zM3 7l9 4 9-4M12 11v10',
  euro: 'M17 6a7 7 0 100 12M4 10h9M4 14h9',
  logout: 'M10 4H5v16h5M15 8l4 4-4 4M19 12H9',
  tool: 'M14 6a4 4 0 005 5l-9 9a2.5 2.5 0 01-4-4l9-9a4 4 0 00-1-1z',
  refresh: 'M20 11a8 8 0 10-2 6M20 5v6h-6',
  play: 'M7 4l13 8-13 8V4z',
  pin: 'M12 21s-7-6.2-7-11.5A7 7 0 0119 9.5C19 14.8 12 21 12 21zM12 12a2.5 2.5 0 100-5 2.5 2.5 0 000 5z',
  trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13',
}

export type IconName = keyof typeof P

export function Icon({ name, className = 'h-5 w-5' }: { name: IconName; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true" focusable="false">
      <path d={P[name]} />
    </svg>
  )
}
