/** Camada HTTP para PC/Pi (FastAPI). */

async function fetchApi(path) {
  const r = await fetch(path);
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

export async function livros() {
  return fetchApi("/livros");
}

export async function capitulo(livro, cap) {
  return fetchApi(
    `/capitulo?livro=${encodeURIComponent(livro)}&capitulo=${cap}`
  );
}

export async function buscar(q, limit = 50) {
  return fetchApi(`/buscar?q=${encodeURIComponent(q)}&limit=${limit}`);
}
