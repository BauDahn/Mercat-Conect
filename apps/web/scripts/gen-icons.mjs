// Genera public/icon-192.png e icon-512.png sin red ni dependencias (PNG RGB con zlib de Node).
import { deflateSync } from 'node:zlib'
import { writeFileSync } from 'node:fs'

const crcTable = Array.from({ length: 256 }, (_, n) => {
  let c = n
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  return c >>> 0
})
const crc = (b) => {
  let c = 0xffffffff
  for (const x of b) c = crcTable[(c ^ x) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}
const chunk = (type, data) => {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length)
  const td = Buffer.concat([Buffer.from(type), data])
  const c = Buffer.alloc(4); c.writeUInt32BE(crc(td))
  return Buffer.concat([len, td, c])
}

function render(size) {
  const BG = [0x14, 0x63, 0x3c], FG = [0xf6, 0xf3, 0xec]
  const s = size / 512
  const raw = Buffer.alloc((size * 3 + 1) * size)
  for (let y = 0; y < size; y++) {
    raw[y * (size * 3 + 1)] = 0
    for (let x = 0; x < size; x++) {
      // hoja: elipse centrada + nervio vertical (coordenadas del icon.svg)
      const px = x / s, py = y / s
      const dx = (px - 256) / 110, dy = (py - 231) / 135
      let col = BG
      if (dx * dx + dy * dy <= 1) col = FG
      if (Math.abs(px - 256) < 11 && py > 150 && py < 370) col = BG
      const o = y * (size * 3 + 1) + 1 + x * 3
      raw[o] = col[0]; raw[o + 1] = col[1]; raw[o + 2] = col[2]
    }
  }
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(size, 0); ihdr.writeUInt32BE(size, 4); ihdr[8] = 8; ihdr[9] = 2
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))])
}

for (const n of [192, 512]) writeFileSync(new URL(`../public/icon-${n}.png`, import.meta.url), render(n))
