#!/usr/bin/env python3
"""Migra JSON Segond 21 → SQLite (índices + FTS5) para leitura rápida em SD."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "biblia.db"
DEFAULT_RAW = ROOT / "data" / "raw" / "s21.json"
DEFAULT_FIXTURE = ROOT / "data" / "fixtures" / "sample_s21.json"

SCHEMA = """
CREATE TABLE versiculos (
    id INTEGER PRIMARY KEY,
    testamento TEXT NOT NULL,
    livro TEXT NOT NULL,
    livro_osis TEXT NOT NULL,
    capitulo INTEGER NOT NULL,
    versiculo INTEGER NOT NULL,
    texto TEXT NOT NULL
);
CREATE INDEX idx_livro_cap_ver ON versiculos (livro, capitulo, versiculo);
CREATE INDEX idx_osis_cap_ver ON versiculos (livro_osis, capitulo, versiculo);
CREATE INDEX idx_testamento_livro ON versiculos (testamento, livro);

CREATE VIRTUAL TABLE versiculos_fts USING fts5(
    texto,
    livro UNINDEXED,
    livro_osis UNINDEXED,
    capitulo UNINDEXED,
    versiculo UNINDEXED,
    content='versiculos',
    content_rowid='id'
);
"""


def _flatten(payload: dict | list) -> list[tuple]:
    """Aceita books→chapters→verses ou lista flat."""
    rows: list[tuple] = []

    if isinstance(payload, list):
        for item in payload:
            rows.append(
                (
                    str(item.get("testamento") or "AT"),
                    str(item["livro"]),
                    str(item.get("livro_osis") or item["livro"][:3]),
                    int(item["capitulo"]),
                    int(item["versiculo"]),
                    str(item["texto"]),
                )
            )
        return rows

    books = payload.get("books") or payload.get("livros") or []
    for book in books:
        testamento = str(book.get("testamento") or "AT")
        livro = str(book["livro"])
        osis = str(book.get("livro_osis") or livro[:3])
        for ch in book.get("chapters") or book.get("capitulos") or []:
            cap = int(ch["capitulo"] if "capitulo" in ch else ch["chapter"])
            verses = ch.get("verses") or ch.get("versiculos") or []
            for v in verses:
                ver = int(v["versiculo"] if "versiculo" in v else v["verse"])
                texto = str(v["texto"] if "texto" in v else v["text"])
                rows.append((testamento, livro, osis, cap, ver, texto))
    return rows


def migrate(input_path: Path, db_path: Path) -> dict:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    rows = _flatten(data)
    if not rows:
        raise SystemExit(f"nenhum versículo em {input_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(SCHEMA)
        con.executemany(
            """
            INSERT INTO versiculos
                (testamento, livro, livro_osis, capitulo, versiculo, texto)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        con.execute(
            """
            INSERT INTO versiculos_fts
                (rowid, texto, livro, livro_osis, capitulo, versiculo)
            SELECT id, texto, livro, livro_osis, capitulo, versiculo
            FROM versiculos
            """
        )
        con.commit()
        con.execute("VACUUM")
        con.commit()
        n_livros = con.execute(
            "SELECT COUNT(DISTINCT livro) FROM versiculos"
        ).fetchone()[0]
        n_ver = con.execute("SELECT COUNT(*) FROM versiculos").fetchone()[0]
    finally:
        con.close()

    size = db_path.stat().st_size
    return {
        "db": str(db_path),
        "livros": n_livros,
        "versiculos": n_ver,
        "bytes": size,
        "source": str(input_path),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="JSON S21 → biblia.db")
    p.add_argument("--input", type=Path, default=None, help="JSON completo S21")
    p.add_argument("--fixture", action="store_true", help="usar sample_s21.json")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = p.parse_args(argv)

    if args.fixture:
        src = DEFAULT_FIXTURE
    elif args.input:
        src = args.input
    elif DEFAULT_RAW.exists():
        src = DEFAULT_RAW
    else:
        print(
            f"Sem {DEFAULT_RAW}. Use --fixture ou coloque s21.json em data/raw/",
            file=sys.stderr,
        )
        return 1

    if not src.exists():
        print(f"ficheiro em falta: {src}", file=sys.stderr)
        return 1

    stats = migrate(src, args.db)
    print(
        f"OK {stats['versiculos']} versículos / {stats['livros']} livros → "
        f"{stats['db']} ({stats['bytes']} bytes) fonte={stats['source']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
