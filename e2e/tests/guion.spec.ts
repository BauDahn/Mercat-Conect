// Guion de la demo (ARQUITECTURA.md 17.6): escenas 1, 4, 5, 6, 7 y 9.
// Requiere la demo en marcha (make demo-local). BASE_URL y API_URL configurables.
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const API = process.env.API_URL ?? 'http://localhost:8000'
const PASS = 'demo1234'

async function reset(request: APIRequestContext) {
  // BUG conocido (ver informe QA): el primer /demo/reset tras actividad puede dar 500 seed_failed; se reintenta.
  let status = 0
  for (let i = 0; i < 6 && status !== 204; i++) {
    if (i) await new Promise((r) => setTimeout(r, 3000))
    status = (await request.post(`${API}/demo/reset`, { timeout: 120_000 })).status()
  }
  expect(status).toBe(204)
}

async function login(page: Page, email: string) {
  await page.goto('/entrar')
  await page.waitForLoadState('networkidle')
  await page.getByLabel('Correo electrónico').fill(email)
  await page.getByLabel('Contraseña').fill(PASS)
  await page.locator('form button.btn-primary').click()
  await expect(page).not.toHaveURL(/\/entrar/)
}

async function logout(page: Page) {
  await page.context().clearCookies()
  await page.evaluate(() => { try { localStorage.clear(); sessionStorage.clear() } catch { /* */ } })
}

async function points(page: Page): Promise<number> {
  const chip = page.locator('a[href="/puntos"]').filter({ hasText: /pts/ }).first()
  await expect(chip).toBeVisible()
  const m = (await chip.innerText()).match(/\d+/)
  return Number(m![0])
}

const card = (page: Page, name: string) => page.locator('a[href^="/oferta/"]').filter({ hasText: name }).first()

test.describe.serial('guion de la demo', () => {
  test.beforeAll(async ({ request }) => { await reset(request) })

  let orderUrl = ''
  let code = ''

  test('escena 1: dashboard como Marta', async ({ page }) => {
    await login(page, 'marta@demo.test')
    await expect(page.getByText(/DEMO/).first()).toBeVisible()
    const c = card(page, 'Tomates de la huerta')
    await expect(c).toBeVisible()
    await expect(c).toContainText('1,80')
    await expect(c).toContainText(/Quedan\s+\d+/)
    await expect(c).toContainText(/\d+\s*pts?|puntos?/i)
    expect(await points(page)).toBe(20)
  })

  test('escena 4: Marta compra tomates (puntos y stock bajan)', async ({ page }) => {
    await login(page, 'marta@demo.test')
    await card(page, 'Tomates de la huerta').click()
    await expect(page.getByText('Quedan 12')).toBeVisible()
    await page.getByRole('button', { name: 'Reservar y pagar' }).click()
    await expect(page).toHaveURL(/\/pedidos\/[0-9a-f-]+/)
    await page.getByRole('button', { name: /^Pagar / }).click()
    await expect(page.getByText('Mis pedidos')).toBeVisible()
    await expect.poll(() => points(page)).toBeLessThan(20)
    orderUrl = new URL(page.url()).pathname
    await page.goto('/')
    await expect(card(page, 'Tomates de la huerta')).toContainText('Quedan 11')
  })

  test('escena 5: Luis (0 puntos) no puede comprar', async ({ page }) => {
    await login(page, 'luis@demo.test')
    expect(await points(page)).toBe(0)
    const c = card(page, 'Tomates de la huerta')
    await expect(c).toContainText(/Te faltan \d+ puntos?/)
    await c.click()
    await expect(page.getByRole('button', { name: 'Reservar y pagar' })).toHaveCount(0)
    await expect(page.getByText(/Te faltan|No tienes puntos suficientes/).first()).toBeVisible()
  })

  test('escena 6: Pepa acepta, prepara y deposita', async ({ page }) => {
    await login(page, 'pepa@demo.test')
    await page.goto('/productor/pedidos')
    await page.getByRole('button', { name: 'Aceptar y preparar' }).first().click()
    await page.getByRole('button', { name: 'Depositar en taquilla' }).first().click()
    await expect(page.getByRole('button', { name: 'Depositar en taquilla' })).toHaveCount(0)
  })

  test('escena 7: Marta teclea el código en la taquilla virtual', async ({ page, context }) => {
    await login(page, 'marta@demo.test')
    await page.goto(orderUrl)
    await expect(page.getByText('Código para abrir la taquilla')).toBeVisible()
    code = (await page.locator('p.font-mono').first().innerText()).trim()
    expect(code).toMatch(/^\d{4,12}$/)
    await page.goto('/sim/taquillas')
    // la taquilla virtual que contiene el pedido: la única con un compartimento ocupado (Depositado)
    const locker = page.locator('section[aria-label^="LOCKER-"]').filter({ has: page.locator('li', { hasText: /Ocupad|Depositad/i }) }).first()
    await expect(locker).toBeVisible()
    for (const d of code) await locker.getByRole('button', { name: d, exact: true }).click()
    await locker.getByRole('button', { name: 'OK', exact: true }).click()
    await expect(locker.getByText('Código aceptado.')).toBeVisible()
    await page.goto(orderUrl)
    await expect(page.getByText(/Retirado|Recogido|COLLECTED/i).first()).toBeVisible({ timeout: 15_000 })
  })

  test('escena 9: reloj a las 13:45 baja el coste; a las 15:00 el mercado cierra y el sobrante se dona', async ({ page }) => {
    await login(page, 'marta@demo.test')
    type Offer = { id: string; decision: { points_cost: number } }
    const costs = async () => {
      const r = await page.request.get('/api/offers')
      expect(r.ok()).toBeTruthy()
      const m = new Map<string, number>()
      for (const o of ((await r.json()).items as Offer[])) m.set(o.id, o.decision.points_cost)
      return m
    }
    const antes = await costs()
    expect(antes.size).toBeGreaterThan(0)
    const sumShared = (m: Map<string, number>) => [...antes.keys()].filter((k) => m.has(k)).reduce((t, k) => t + m.get(k)!, 0)
    await page.goto('/demo')
    await page.getByRole('button', { name: '13:45', exact: true }).click()
    await expect(page.getByText(/13:45/).first()).toBeVisible()
    await expect.poll(async () => {
      const d = await costs()
      return d.size > 0 && sumShared(d) < [...antes.keys()].filter((k) => d.has(k)).reduce((t, k) => t + antes.get(k)!, 0)
    }).toBe(true)
    await page.goto('/demo')
    await page.getByRole('button', { name: '15:00', exact: true }).click()
    await expect.poll(async () => {
      await page.goto('/')
      return page.locator('a[href^="/oferta/"]').count()
    }, { timeout: 30_000 }).toBe(0)
    await logout(page)
    await login(page, 'gestion@demo.test')
    await page.goto('/admin/donaciones')
    await expect(page.getByText(/Dorada|Mejillones/).first()).toBeVisible()
  })
})
