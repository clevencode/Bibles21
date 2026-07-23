#!/usr/bin/env python3
"""
Extrai Segond 21 a partir de EPUB (páginas HTML OCR) → JSON estruturado.

Estratégia: o EPUB é OCR por página com cabeçalhos correntes fiáveis após
marcadores "PAGE N", e muitas referências cruzadas isoladas (ignorar).

Uso:
  python scripts/parse_s21_epub.py --epub "C:\\Users\\...\\La Bible -  Segond 21 .epub"
  python scripts/migrate.py --input data/raw/s21.json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from parse_s21_djvu import (  # noqa: E402
    BOOKS,
    EXPECTED_CHAPTERS,
    BookOut,
    Chapter,
    Verse,
    build_payload,
    clean_text,
    norm,
    repair_verse_sequence,
    split_by_verse_resets,
    split_verses,
)

DEFAULT_OUT = ROOT / "data" / "raw" / "s21.json"
DEFAULT_WORK = ROOT / "data" / "raw" / "epub_extract"


TAG_RE = re.compile(r"<[^>]+>")
ACCURACY_RE = re.compile(
    r"The text on this page is estimated to be only [\d.]+% accurate",
    re.I,
)
IMG_ONLY_RE = re.compile(r"^\s*(?:<img\b.*?>\s*)+$", re.I | re.S)
PAGE_RE = re.compile(r"^PAGE\s+\d+$", re.I)
REF_TAIL_RE = re.compile(r"^(\d{1,3})[\.:](\d{1,3})(?:\s+(.*))?$", re.S)


def html_to_text(html: str) -> str:
    html = ACCURACY_RE.sub(" ", html)
    html = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<(br|/p|/div|/h[1-6])\s*/?>", "\n", html, flags=re.I)
    html = TAG_RE.sub(" ", html)
    text = unescape(html)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def page_sort_key(path: Path) -> int:
    m = re.search(r"page_(\d+)\.html$", path.name, re.I)
    return int(m.group(1)) if m else 10**9


def extract_epub(epub: Path, work: Path) -> Path:
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(epub, "r") as zf:
        zf.extractall(work)
    pages = list(work.rglob("page_*.html"))
    if not pages:
        raise SystemExit(f"nenhuma page_*.html em {epub}")
    return pages[0].parent


def collect_lines(pages_dir: Path) -> list[str]:
    pages = sorted(pages_dir.glob("page_*.html"), key=page_sort_key)
    chunks: list[str] = []
    for p in pages:
        raw = p.read_text(encoding="utf-8", errors="replace")
        if IMG_ONLY_RE.search(TAG_RE.sub("", raw).strip()):
            continue
        text = html_to_text(raw)
        if not text or len(text) < 20:
            continue
        if text.count("....") > 20 and "Au commencement" not in text:
            if sum(ch.isdigit() for ch in text) > len(text) * 0.25:
                continue
        # marcar página para o extractor (nome do ficheiro)
        m = re.search(r"page_(\d+)\.html$", p.name, re.I)
        marker = f"PAGE {m.group(1)}" if m else "PAGE 0"
        chunks.append(marker + "\n" + text)
    big = "\n\n".join(chunks)
    # Normalizar variantes OCR de títulos curtos
    big = re.sub(r"(?i)\bAPOCAIMPSE\b", "APOCALYPSE", big)
    big = re.sub(r"(?i)\b2JEAN\b", "2 JEAN", big)
    big = re.sub(r"(?i)\b3JEAN\b", "3 JEAN", big)
    big = re.sub(r"(?i)\bIUDE\b", "JUDE", big)
    # Philémon misturado sob HÉBREUX
    big = re.sub(
        r"(?i)(?:H[ÉE]BREUX\s+1[.:]11\s+)?(participation\s+à\s+la\s+foi\s+soit\s+efficace)",
        r"\nPHILEMON 1.6 \1",
        big,
    )
    big = re.sub(
        r"(?i)(Ecrit\s+anonyme\s+dont)",
        r"\nHEBREUX 1.1 \1",
        big,
    )
    return [ln for ln in big.splitlines()]


def build_title_index() -> list[tuple[str, dict]]:
    """Títulos normalizados → livro, mais longos primeiro."""
    pairs: list[tuple[str, dict]] = []
    for book in BOOKS:
        for t in book["titles"]:
            pairs.append((norm(t), book))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs


def match_book_header(
    line: str, title_index: list[tuple[str, dict]]
) -> tuple[dict, int, str] | None:
    """
    Se a linha (ou o seu início) é um cabeçalho LIVRO ch.vs [texto],
    devolve (book, capítulo, resto_do_texto_original).
    """
    s = line.strip()
    if not s or len(s) > 20000:
        return None
    n = norm(s)
    n = re.sub(r"^\d{1,3}\s+", "", n)  # "5 GENESE 5.13"
    for title, book in title_index:
        if n == title:
            return book, 1, ""
        if not n.startswith(title + " "):
            continue
        rest_n = n[len(title) + 1 :]
        m = REF_TAIL_RE.match(rest_n)
        if m:
            ch = int(m.group(1))
            # resto original após "ch.vs"
            mo = re.search(r"(\d{1,3})[\.:](\d{1,3})\s*(.*)$", s, re.S)
            rest = (mo.group(3) if mo else "") or ""
            return book, ch, rest.strip()
        # intro "GENESE Le Livre…" (sem ch.vs)
        if re.match(r"^(LE |LA |LES |L'|APPELES|PREMIER|SE PRESENTANT)", rest_n):
            return book, 1, ""
        if len(rest_n) > 40 and not rest_n[0].isdigit():
            return book, 1, ""
    return None


def is_bare_ref_line(line: str, title_index: list[tuple[str, dict]]) -> bool:
    s = line.strip()
    if not s or len(s) > 48:
        return False
    hit = match_book_header(s, title_index)
    if not hit:
        return False
    _book, _ch, rest = hit
    return not rest


def _pieces_to_chapters(
    pieces: list[tuple[int | None, str]], expected_caps: int
) -> list[Chapter]:
    """Converte fragmentos (capítulo forçado | texto) em capítulos/versículos."""
    chapters: list[Chapter] = []
    bucket_ch = 1
    bucket_text: list[str] = []

    def emit() -> None:
        nonlocal bucket_text, bucket_ch
        if not bucket_text:
            return
        text = clean_text(" ".join(bucket_text))
        verses = repair_verse_sequence(split_verses(text))
        chapters.extend(split_by_verse_resets(verses, bucket_ch, expected_caps))
        bucket_text = []

    for forced, frag in pieces:
        if forced is not None and not frag:
            emit()
            bucket_ch = forced
            continue
        if forced is not None and frag:
            emit()
            bucket_ch = forced
            bucket_text.append(frag)
            continue
        if frag:
            bucket_text.append(frag)
    emit()

    merged: dict[int, list[Verse]] = {}
    for ch in chapters:
        merged.setdefault(ch.n, []).extend(ch.verses)
    result: list[Chapter] = []
    for cn in sorted(merged):
        best: dict[int, Verse] = {}
        for v in repair_verse_sequence(merged[cn]):
            if v.n not in best or len(v.text) > len(best[v.n].text):
                best[v.n] = v
        ordered = [best[k] for k in sorted(best) if best[k].text]
        if ordered:
            result.append(Chapter(n=cn, verses=ordered))
    return result


def extract_by_page_headers(lines: list[str]) -> list[BookOut]:
    """Associa texto ao livro indicado pelos cabeçalhos após PAGE."""
    title_index = build_title_index()
    # osis -> lista ordenada (capítulo_forçado|None, texto)
    streams: dict[str, list[tuple[int | None, str]]] = {b["osis"]: [] for b in BOOKS}

    current_osis: str | None = None
    after_page = False
    skipping_footnotes = False
    first_line_idx: dict[str, int] = {}

    def set_book(book: dict, ch: int, idx: int, rest: str = "") -> None:
        nonlocal current_osis
        current_osis = book["osis"]
        first_line_idx.setdefault(current_osis, idx)
        streams[current_osis].append((ch, rest))

    for idx, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue

        if PAGE_RE.match(s):
            after_page = True
            skipping_footnotes = False
            continue

        if skipping_footnotes:
            continue

        hit = match_book_header(s, title_index)

        if hit and is_bare_ref_line(s, title_index):
            if after_page:
                book, ch, _rest = hit
                set_book(book, ch, idx)
                after_page = False
                continue
            skipping_footnotes = True
            after_page = False
            continue

        if hit:
            book, ch, rest = hit
            if after_page or len(rest) > 80 or len(s) > 120:
                set_book(book, ch, idx, rest)
                after_page = False
                continue
            skipping_footnotes = True
            after_page = False
            continue

        after_page = False

        n = norm(s)
        intro_hit = False
        for title, book in title_index:
            if n == title or (
                n.startswith(title + " ")
                and any(
                    k in n
                    for k in (
                        "LIVRE",
                        "SE PRESENTANT",
                        "EPITRE",
                        "APOCALYPSE SE",
                        "QUATRIEME",
                        "DEUXIEME",
                        "TROISIEME",
                        "CINQUIEME",
                    )
                )
            ):
                set_book(book, 1, idx)
                intro_hit = True
                break
        if intro_hit:
            continue

        if current_osis:
            if len(s) <= 3 and not re.search(r"[A-Za-zÀ-ü]", s):
                continue
            streams[current_osis].append((None, s))

    books_out: list[BookOut] = []
    for book in BOOKS:
        osis = book["osis"]
        expected = EXPECTED_CHAPTERS.get(osis, 50)
        chapters = _pieces_to_chapters(streams.get(osis) or [], expected)
        start = first_line_idx.get(osis, 0)
        books_out.append(BookOut(meta=book, start=start, end=start, chapters=chapters))
    return books_out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epub", type=Path, required=True, help="caminho do ficheiro .epub")
    ap.add_argument("--work", type=Path, default=DEFAULT_WORK)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--keep-extract",
        action="store_true",
        help="não apagar pasta de extracção",
    )
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    if not args.epub.exists():
        raise SystemExit(f"EPUB não encontrado: {args.epub}")

    print(f"EPUB: {args.epub}")
    pages_dir = extract_epub(args.epub, args.work)
    print(f"páginas HTML em: {pages_dir}")

    lines = collect_lines(pages_dir)
    print(f"linhas de texto: {len(lines)}")

    txt_path = args.work.parent / "s21_epub.txt"
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"texto plano: {txt_path}")

    books_out = extract_by_page_headers(lines)
    nonempty = sum(1 for b in books_out if b.chapters)
    print(f"livros com texto: {nonempty}/{len(books_out)}")

    for b in books_out:
        nver = sum(len(c.verses) for c in b.chapters)
        exp = EXPECTED_CHAPTERS.get(b.meta["osis"])
        flag = ""
        if exp and abs(len(b.chapters) - exp) > 2:
            flag = f" ⚠ caps {len(b.chapters)}≠{exp}"
        elif nver == 0:
            flag = " ⚠ vazio"
        print(
            f"  {b.meta['osis']:7} {b.meta['livro']:<28} "
            f"caps={len(b.chapters):3} vers={nver:5}{flag}"
        )

    payload = build_payload(books_out)
    payload["source"] = f"epub:{args.epub.name}"
    payload["note"] = (
        "Extraído de EPUB (OCR por página, cabeçalhos após PAGE). "
        "Segond 21 © Société Biblique de Genève. Uso pessoal / autorização."
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"\n→ {args.output}  "
        f"({payload['stats']['verses']} versículos, {payload['stats']['books']} livros)"
    )

    if args.report:
        print("\nRelatório capítulos:")
        for b in books_out:
            exp = EXPECTED_CHAPTERS.get(b.meta["osis"])
            got = len(b.chapters)
            nver = sum(len(c.verses) for c in b.chapters)
            if exp and (got != exp or nver == 0):
                print(f"  {b.meta['osis']}: caps={got} (esp. {exp}), vers={nver}")

    if not args.keep_extract:
        pass


if __name__ == "__main__":
    main()
