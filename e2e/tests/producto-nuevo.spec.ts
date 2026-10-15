// Producto nuevo con foto opcional (ARQUITECTURA.md 6.7): Pepa (productora) crea un producto y publica
// una oferta; Marta (vecina), que ya tiene el dashboard abierto, la ve aparecer sin recargar.
// Requiere la demo en marcha (make demo-local). BASE_URL y API_URL configurables.
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const API = process.env.API_URL ?? 'http://localhost:8000'
const PASS = 'demo1234'

async function reset(request: APIRequestContext) {
  // Mismo reintento que guion.spec.ts (primer reset tras actividad puede dar 500 seed_failed).
  let status = 0
  for (let i = 0; i < 6 && status !== 204; i++) {
    if (i) await new Promise((r) => setTimeout(r, 3000))
    status = (await request.post(`${API}/demo/reset`, { timeout: 120_000 })).status()
  }
  expect(status).toBe(204)
}

async function login(page: Page, email: string) {
  await page.goto('/entrar', { waitUntil: 'load' })
  await page.getByLabel('Correo electrónico').fill(email)
  await page.getByLabel('Contraseña').fill(PASS)
  await page.locator('form button.btn-primary').click()
  await expect(page).not.toHaveURL(/\/entrar/)
}

test('productora sube un producto nuevo y la vecina lo ve en el dashboard sin recargar', async ({ browser, request }) => {
  await reset(request)
  const name = `Berenjena e2e ${Date.now().toString(36)}`

  // Marta abre el dashboard primero y lo deja abierto (SSE activo).
  const vecina = await browser.newContext({ locale: 'es-ES' })
  const marta = await vecina.newPage()
  await login(marta, 'marta@demo.test')
  await marta.goto('/', { waitUntil: 'load' })

  // Pepa crea el producto nuevo y publica la oferta.
  const productora = await browser.newContext({ locale: 'es-ES' })
  const pepa = await productora.newPage()
  await login(pepa, 'pepa@demo.test')
  await pepa.goto('/productor/publicar', { waitUntil: 'load' })

  await pepa.getByRole('button', { name: 'Producto nuevo' }).click()
  await pepa.getByLabel('Nombre del producto').fill(name)
  await pepa.getByLabel(/Unidad/).fill('kg')
  await pepa.getByLabel(/Precio habitual/).fill('3,20')
  await pepa.getByLabel('Cantidad').fill('4')
  await pepa.getByLabel(/Precio \(EUR\)/).fill('1,50')
  // Foto opcional: se usa una imagen mínima PNG 1x1 generada en memoria.
  const png = Buffer.from('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63f8ffff3f0005fe02fea7d9b5a80000000049454e44ae426082', 'hex')
  await pepa.locator('input[type="file"]').setInputFiles({ name: 'berenjena.png', mimeType: 'image/png', buffer: png })
  await pepa.locator('form button.btn-primary').click()
  await expect(pepa.getByText(/Oferta publicada/)).toBeVisible()

  // Marta, sin recargar, ve la tarjeta con el nombre nuevo (SSE o refresco del listado).
  const card = marta.locator('a[href^="/oferta/"]').filter({ hasText: name }).first()
  await expect(card).toBeVisible({ timeout: 30_000 })

  await vecina.close()
  await productora.close()
})
