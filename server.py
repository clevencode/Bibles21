#!/usr/bin/env python3
"""API local Segond 21 — SQLite read-only + UI estática (SD / Pi / PC)."""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("BIBLIA_DB", ROOT / "data" / "biblia.db"))
STATIC = ROOT / "static"
HOST = os.environ.get("BIBLIA_HOST", "127.0.0.1")
PORT = int(os.environ.get("BIBLIA_PORT", "8765"))

app = FastAPI(title="Bible S21 Local", docs_url=None, redoc_url=None)


def _db_uri() -> str:
    # mode=ro evita escritas acidentais no cartão SD
    path = DB_PATH.resolve().as_posix()
    return f"file:{path}?mode=ro"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="biblia.db em falta — corre: python scripts/migrate.py --fixture",
        )
    con = sqlite3.connect(_db_uri(), uri=True)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA query_only=ON")
        yield con
    finally:
        con.close()


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "testamento": row["testamento"],
        "livro": row["livro"],
        "livro_osis": row["livro_osis"],
        "capitulo": row["capitulo"],
        "versiculo": row["versiculo"],
        "texto": row["texto"],
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    ok = DB_PATH.exists()
    return {"ok": ok, "db": str(DB_PATH), "ro": True}


@app.get("/livros")
def livros() -> list[dict[str, Any]]:
    with connect() as con:
        cur = con.execute(
            """
            SELECT livro, livro_osis, testamento,
                   COUNT(*) AS n_versiculos,
                   MAX(capitulo) AS n_capitulos
            FROM versiculos
            GROUP BY livro, livro_osis, testamento
            ORDER BY
                CASE testamento WHEN 'AT' THEN 0 ELSE 1 END,
                MIN(id)
            """
        )
        return [dict(r) for r in cur.fetchall()]


@app.get("/capitulo")
def capitulo(
    livro: str = Query(..., min_length=1),
    capitulo: int = Query(..., ge=1),
) -> dict[str, Any]:
    with connect() as con:
        cur = con.execute(
            """
            SELECT id, testamento, livro, livro_osis, capitulo, versiculo, texto
            FROM versiculos
            WHERE (livro = ? OR livro_osis = ?) AND capitulo = ?
            ORDER BY versiculo
            """,
            (livro, livro, capitulo),
        )
        verses = [_row_dict(r) for r in cur.fetchall()]
    if not verses:
        raise HTTPException(404, detail="capítulo não encontrado")
    return {
        "livro": verses[0]["livro"],
        "livro_osis": verses[0]["livro_osis"],
        "testamento": verses[0]["testamento"],
        "capitulo": capitulo,
        "versiculos": verses,
    }


@app.get("/versiculo")
def versiculo(
    livro: str = Query(..., min_length=1),
    capitulo: int = Query(..., ge=1),
    versiculo: int = Query(..., ge=1),
) -> dict[str, Any]:
    with connect() as con:
        row = con.execute(
            """
            SELECT id, testamento, livro, livro_osis, capitulo, versiculo, texto
            FROM versiculos
            WHERE (livro = ? OR livro_osis = ?)
              AND capitulo = ? AND versiculo = ?
            """,
            (livro, livro, capitulo, versiculo),
        ).fetchone()
    if not row:
        raise HTTPException(404, detail="versículo não encontrado")
    return _row_dict(row)


@app.get("/buscar")
def buscar(
    q: str = Query(..., min_length=2),
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    q = q.strip()
    with connect() as con:
        # FTS5: sanitizar tokens simples
        tokens = re.findall(r"[\wàâäéèêëïîôùûüçœæ'-]+", q, flags=re.I)
        rows: list[sqlite3.Row] = []
        if tokens:
            fts_q = " ".join(f'"{t}"' for t in tokens[:8])
            try:
                cur = con.execute(
                    """
                    SELECT v.id, v.testamento, v.livro, v.livro_osis,
                           v.capitulo, v.versiculo, v.texto
                    FROM versiculos_fts f
                    JOIN versiculos v ON v.id = f.rowid
                    WHERE versiculos_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_q, limit),
                )
                rows = cur.fetchall()
            except sqlite3.OperationalError:
                rows = []
        if not rows:
            cur = con.execute(
                """
                SELECT id, testamento, livro, livro_osis, capitulo, versiculo, texto
                FROM versiculos
                WHERE texto LIKE ?
                LIMIT ?
                """,
                (f"%{q}%", limit),
            )
            rows = cur.fetchall()
    return {"q": q, "count": len(rows), "results": [_row_dict(r) for r in rows]}


@app.get("/ref/{ref}")
def ref_lookup(ref: str) -> dict[str, Any]:
    """Formato YouVersion-like: Dan.12.4 ou Jean.3.16"""
    m = re.match(
        r"^([A-Za-z0-9]+)\.(\d+)\.(\d+)$",
        ref.strip(),
    )
    if not m:
        raise HTTPException(400, detail="use OSIS.capítulo.versículo (ex. Dan.12.4)")
    osis, cap, ver = m.group(1), int(m.group(2)), int(m.group(3))
    with connect() as con:
        row = con.execute(
            """
            SELECT id, testamento, livro, livro_osis, capitulo, versiculo, texto
            FROM versiculos
            WHERE lower(livro_osis) = lower(?) AND capitulo = ? AND versiculo = ?
            """,
            (osis, cap, ver),
        ).fetchone()
    if not row:
        raise HTTPException(404, detail="referência não encontrada")
    return _row_dict(row)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def main() -> None:
    import uvicorn

    uvicorn.run(
        "server:app",
        host=HOST,
        port=PORT,
        reload=False,
        access_log=False,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
