# Contexto de construcción: apps/web. Imagen de desarrollo (Vite en el puerto 5173).
FROM node:22.11.0-bookworm-slim

ENV npm_config_update_notifier=false

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173", "--strictPort"]
