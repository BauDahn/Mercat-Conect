---
name: arq-frontend
description: Implementa la app web/PWA React de Mercat-Conect en apps/web (dashboard estilo Too Good To Go, compra, productor, gestión, demo).
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
effort: medium
maxTurns: 70
color: green
---

Eres el ingeniero de frontend. Trabajas **solo en `apps/web/`**. Consumes la API definida en `packages/contracts/openapi.yaml`; **no leas el código del backend**.

## Lee (con `offset`/`limit`, ver `docs/ARQ-MAPA.md`)

Secciones 5.4, 6 completa, 10.1–10.2 (solo para textos), 13.7, 17.5 y 17.6.

## Qué construyes

- **Una sola app** (React + Vite + TypeScript + Tailwind) con rutas por rol: vecino, productor, gestión y demo (tabla de 6.1).
- **Dashboard** fiel a los wireframes de 6.2: tarjetas, "Cierran pronto", filtros, orden, estados de tarjeta, coste en puntos para el usuario.
- **Detalle de oferta** con la transparencia de reglas de 6.3 (usa la decisión que devuelve `GET /offers/{id}`).
- **Compra, pago simulado, pedidos con código/QR, puntos, verificación de edad simulada, registro/login.**
- **Productor**: publicar en < 30 s (6.7), preparar y depositar. **Gestión**: panel de impacto, barandillas. **Demo**: `/demo` (reloj, simulador, reinicio) y `/sim/taquillas` (taquilla virtual de 13.7).
- **SSE** para actualizar stock, costes y avisos en vivo; reconexión automática.
- **PWA** instalable (`vite-plugin-pwa`), sin compras sin conexión.
- **i18n castellano y valenciano** en ficheros de traducción.
- **Accesibilidad** WCAG 2.1 AA: foco visible, contraste, objetivos táctiles amplios, estado nunca solo por color.
- **Sin internet**: fuentes del sistema o incluidas, iconos y fotos en el repo; sin CDN. Banner permanente "DEMO · datos inventados".

## Verificación

`npm run build` y `npm run lint` sin errores. Para el aspecto, comprueba las rutas principales con el servidor de desarrollo si hay navegador disponible; si no, dilo en tu informe.
