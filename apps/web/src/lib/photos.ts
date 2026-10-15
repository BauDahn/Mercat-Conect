// Fotos de ejemplo en public/productos (Wikimedia Commons). Licencias: CC0, dominio público, CC BY y CC BY-SA.
// Se usan cuando la API no trae photo_url. Clave: nombre del producto del catálogo (ver data/seed/generate.py).
export const PRODUCT_PHOTOS: Record<string, { file: string; license: string }> = {
  "Tomates de la huerta": { file: "productos/tomates-huerta.jpg", license: "CC BY-SA 3.0" },
  "Naranjas de Valencia": { file: "productos/naranjas.jpg", license: "CC BY-SA 4.0" },
  "Fresas": { file: "productos/fresas.jpg", license: "CC BY-SA 4.0" },
  "Plátanos": { file: "productos/platanos.jpg", license: "CC0" },
  "Uvas": { file: "productos/uvas.jpg", license: "CC0" },
  "Kakis": { file: "productos/kakis.jpg", license: "CC BY-SA 3.0" },
  "Mandarinas": { file: "productos/mandarinas.jpg", license: "CC BY-SA 3.0" },
  "Granadas": { file: "productos/granadas.jpg", license: "CC BY-SA 4.0" },
  "Lechuga": { file: "productos/lechuga.jpg", license: "CC BY-SA 4.0" },
  "Pimientos rojos": { file: "productos/pimientos.jpg", license: "CC0" },
  "Calabacines": { file: "productos/calabacines.jpg", license: "CC BY-SA 3.0" },
  "Espinacas": { file: "productos/espinacas.jpg", license: "CC BY 3.0" },
  "Cebollas": { file: "productos/cebollas.jpg", license: "CC BY-SA 3.0" },
  "Alcachofas": { file: "productos/alcachofas.jpg", license: "CC BY-SA 3.0" },
  "Merluza": { file: "productos/merluza.jpg", license: "CC BY-SA 4.0" },
  "Gambas": { file: "productos/gambas.jpg", license: "CC BY-SA 4.0" },
  "Sardinas": { file: "productos/sardinas.jpg", license: "CC BY-SA 4.0" },
  "Mejillones": { file: "productos/mejillones.jpg", license: "CC BY-SA 3.0" },
  "Dorada": { file: "productos/dorada.jpg", license: "CC BY-SA 4.0" },
  "Pollo troceado": { file: "productos/pollo.jpg", license: "CC BY 2.0" },
  "Longaniza": { file: "productos/longaniza.jpg", license: "CC BY-SA 3.0" },
  "Ternera picada": { file: "productos/ternera.jpg", license: "CC BY-SA 4.0" },
  "Costillas de cerdo": { file: "productos/costillas.jpg", license: "CC0" },
  "Barra de pan": { file: "productos/barra-pan.jpg", license: "CC BY-SA 2.0" },
  "Hogaza de espelta": { file: "productos/hogaza.jpg", license: "CC BY-SA 3.0" },
  "Bollería surtida": { file: "productos/bolleria.jpg", license: "CC0" },
  "Coca de llanda": { file: "productos/coca.jpg", license: "CC0" },
  "Jamón serrano loncheado": { file: "productos/jamon.jpg", license: "CC BY-SA 4.0" },
  "Queso curado": { file: "productos/queso.jpg", license: "CC BY-SA 2.0" },
  "Sobrasada": { file: "productos/sobrasada.jpg", license: "CC BY-SA 2.0" },
  "Fuet": { file: "productos/fuet.jpg", license: "CC BY 2.0" },
  "Leche fresca": { file: "productos/leche.jpg", license: "CC0" },
  "Yogur artesano": { file: "productos/yogur.jpg", license: "CC BY-SA 3.0" },
  "Requesón": { file: "productos/requeson.jpg", license: "CC BY-SA 3.0" },
  "Mató": { file: "productos/mato.jpg", license: "CC BY-SA 2.0" },
  "Garbanzos cocidos": { file: "productos/garbanzos.jpg", license: "CC BY-SA 4.0" },
  "Arroz bomba": { file: "productos/arroz.jpg", license: "CC BY-SA 4.0" },
  "Almendras": { file: "productos/almendras.jpg", license: "CC BY-SA 4.0" },
  "Pasas": { file: "productos/pasas.jpg", license: "CC BY-SA 3.0" },
  "Lentejas": { file: "productos/lentejas.jpg", license: "CC BY-SA 4.0" },
}

export function productPhoto(name: string): string | null {
  const p = PRODUCT_PHOTOS[name]
  return p ? `${import.meta.env.BASE_URL}${p.file}` : null
}
