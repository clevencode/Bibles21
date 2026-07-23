#!/usr/bin/env python3
"""
Extrai Segond 21 (OCR Archive.org djvu.txt) → JSON estruturado (livros/capítulos/versículos).

Fonte típica:
  https://archive.org/download/la-bible-segond-21/La%20Bible%20-%20%20Segond%2021%20_djvu.txt

Uso pessoal / autorização — o texto © Société Biblique de Genève. Este script não
redistribui o corpus; escreve em data/raw/ (gitignored).

OCR imperfecto: números de versículo por vezes truncados (10→0, 17→"). O parser
repara sequências óbvias e reporta estatísticas / avisos.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TXT = ROOT / "data" / "raw" / "s21_full.txt"
DEFAULT_OUT = ROOT / "data" / "raw" / "s21.json"

# Canon protestante FR + OSIS (ordem S21)
BOOKS: list[dict] = [
    {"livro": "Genèse", "osis": "Gen", "t": "AT", "titles": ["GENESE"]},
    {"livro": "Exode", "osis": "Exod", "t": "AT", "titles": ["EXODE"]},
    {"livro": "Lévitique", "osis": "Lev", "t": "AT", "titles": ["LEVITIQUE"]},
    {"livro": "Nombres", "osis": "Num", "t": "AT", "titles": ["NOMBRES"]},
    {"livro": "Deutéronome", "osis": "Deut", "t": "AT", "titles": ["DEUTERONOME"]},
    {"livro": "Josué", "osis": "Josh", "t": "AT", "titles": ["JOSUE"]},
    {"livro": "Juges", "osis": "Judg", "t": "AT", "titles": ["JUGES"]},
    {"livro": "Ruth", "osis": "Ruth", "t": "AT", "titles": ["RUTH"]},
    {"livro": "1 Samuel", "osis": "1Sam", "t": "AT", "titles": ["1 SAMUEL"]},
    {"livro": "2 Samuel", "osis": "2Sam", "t": "AT", "titles": ["2 SAMUEL"]},
    {"livro": "1 Rois", "osis": "1Kgs", "t": "AT", "titles": ["1 ROIS"]},
    {"livro": "2 Rois", "osis": "2Kgs", "t": "AT", "titles": ["2 ROIS"]},
    {"livro": "1 Chroniques", "osis": "1Chr", "t": "AT", "titles": ["1 CHRONIQUES"]},
    {"livro": "2 Chroniques", "osis": "2Chr", "t": "AT", "titles": ["2 CHRONIQUES"]},
    {"livro": "Esdras", "osis": "Ezra", "t": "AT", "titles": ["ESDRAS"]},
    {"livro": "Néhémie", "osis": "Neh", "t": "AT", "titles": ["NEHEMIE"]},
    {"livro": "Esther", "osis": "Esth", "t": "AT", "titles": ["ESTHER"]},
    {"livro": "Job", "osis": "Job", "t": "AT", "titles": ["JOB"]},
    {
        "livro": "Psaumes",
        "osis": "Ps",
        "t": "AT",
        "titles": ["PSAUMES"],
        "anchors": ["APPELES TEHILLIM", "PREMIER LIVRE 1-41"],
    },
    {"livro": "Proverbes", "osis": "Prov", "t": "AT", "titles": ["PROVERBES"]},
    {"livro": "Ecclésiaste", "osis": "Eccl", "t": "AT", "titles": ["ECCLESIASTE"]},
    {
        "livro": "Cantique des cantiques",
        "osis": "Song",
        "t": "AT",
        "titles": ["CANTIQUE DES CANTIQUES", "CANTIQUE"],
    },
    {"livro": "Ésaïe", "osis": "Isa", "t": "AT", "titles": ["ESAIE"]},
    {"livro": "Jérémie", "osis": "Jer", "t": "AT", "titles": ["JEREMIE"]},
    {"livro": "Lamentations", "osis": "Lam", "t": "AT", "titles": ["LAMENTATIONS"]},
    {"livro": "Ézéchiel", "osis": "Ezek", "t": "AT", "titles": ["EZECHIEL"]},
    {"livro": "Daniel", "osis": "Dan", "t": "AT", "titles": ["DANIEL"]},
    {"livro": "Osée", "osis": "Hos", "t": "AT", "titles": ["OSEE"]},
    {"livro": "Joël", "osis": "Joel", "t": "AT", "titles": ["JOEL"]},
    {"livro": "Amos", "osis": "Amos", "t": "AT", "titles": ["AMOS"]},
    {"livro": "Abdias", "osis": "Obad", "t": "AT", "titles": ["ABDIAS"]},
    {"livro": "Jonas", "osis": "Jonah", "t": "AT", "titles": ["JONAS"]},
    {"livro": "Michée", "osis": "Mic", "t": "AT", "titles": ["MICHEE"]},
    {"livro": "Nahoum", "osis": "Nah", "t": "AT", "titles": ["NAHUM", "NAHOUM"]},
    {"livro": "Habakuk", "osis": "Hab", "t": "AT", "titles": ["HABAKUK"]},
    {"livro": "Sophonie", "osis": "Zeph", "t": "AT", "titles": ["SOPHONIE"]},
    {"livro": "Aggée", "osis": "Hag", "t": "AT", "titles": ["AGGEE"]},
    {"livro": "Zacharie", "osis": "Zech", "t": "AT", "titles": ["ZACHARIE"]},
    {"livro": "Malachie", "osis": "Mal", "t": "AT", "titles": ["MALACHIE"]},
    {"livro": "Matthieu", "osis": "Matt", "t": "NT", "titles": ["MATTHIEU"]},
    {"livro": "Marc", "osis": "Mark", "t": "NT", "titles": ["MARC"]},
    {"livro": "Luc", "osis": "Luke", "t": "NT", "titles": ["LUC"]},
    {"livro": "Jean", "osis": "John", "t": "NT", "titles": ["JEAN"]},
    {
        "livro": "Actes",
        "osis": "Acts",
        "t": "NT",
        "titles": ["ACTES DES APOTRES", "ACTES"],
    },
    {"livro": "Romains", "osis": "Rom", "t": "NT", "titles": ["ROMAINS"]},
    {"livro": "1 Corinthiens", "osis": "1Cor", "t": "NT", "titles": ["1 CORINTHIENS"]},
    {"livro": "2 Corinthiens", "osis": "2Cor", "t": "NT", "titles": ["2 CORINTHIENS"]},
    {"livro": "Galates", "osis": "Gal", "t": "NT", "titles": ["GALATES"]},
    {"livro": "Éphésiens", "osis": "Eph", "t": "NT", "titles": ["EPHESIENS"]},
    {"livro": "Philippiens", "osis": "Phil", "t": "NT", "titles": ["PHILIPPIENS"]},
    {"livro": "Colossiens", "osis": "Col", "t": "NT", "titles": ["COLOSSIENS"]},
    {
        "livro": "1 Thessaloniciens",
        "osis": "1Thess",
        "t": "NT",
        "titles": ["1 THESSALONICIENS"],
    },
    {
        "livro": "2 Thessaloniciens",
        "osis": "2Thess",
        "t": "NT",
        "titles": ["2 THESSALONICIENS"],
    },
    {"livro": "1 Timothée", "osis": "1Tim", "t": "NT", "titles": ["1 TIMOTHEE"]},
    {"livro": "2 Timothée", "osis": "2Tim", "t": "NT", "titles": ["2 TIMOTHEE"]},
    {"livro": "Tite", "osis": "Titus", "t": "NT", "titles": ["TITE"]},
    {
        "livro": "Philémon",
        "osis": "Phlm",
        "t": "NT",
        "titles": ["PHILEMON"],
        # OCR EPUB mistura Philémon sob cabeçalho HÉBREUX; âncoras do corpo real
        "anchors": [
            "PARTICIPATION A LA FOI SOIT EFFICACE",
            "DEVENU MON FILS EN PRISON",
            "DEMANDE DE PAUL",
        ],
    },
    {
        "livro": "Hébreux",
        "osis": "Heb",
        "t": "NT",
        "titles": ["HEBREUX"],
        # preferir intro real (após Philémon OCR) em vez do cabeçalho errado 1.11
        "anchors": ["ECRIT ANONYME"],
    },
    {"livro": "Jacques", "osis": "Jas", "t": "NT", "titles": ["JACQUES"]},
    {"livro": "1 Pierre", "osis": "1Pet", "t": "NT", "titles": ["1 PIERRE"]},
    {"livro": "2 Pierre", "osis": "2Pet", "t": "NT", "titles": ["2 PIERRE"]},
    {"livro": "1 Jean", "osis": "1John", "t": "NT", "titles": ["1 JEAN"]},
    {
        "livro": "2 Jean",
        "osis": "2John",
        "t": "NT",
        "titles": ["2 JEAN", "2JEAN"],
        "anchors": ["CHERE DAME", "APPEL A UN AMOUR"],
    },
    {
        "livro": "3 Jean",
        "osis": "3John",
        "t": "NT",
        "titles": ["3 JEAN", "3JEAN"],
        "anchors": [
            "TROISIEME EPITRE DE JEAN",
            "GAIUS DE DERBE",
            "A L'INSTAR DE 2 JEAN",
        ],
        "optional": True,  # EPUB OCR corta quase todo o corpo
    },
    {
        "livro": "Judas",
        "osis": "Jude",
        "t": "NT",
        "titles": ["JUDAS", "JUDE", "IUDE"],
        "anchors": ["DE LA PART DE JUDE", "EPITRE DE JUDE"],
    },
    {
        "livro": "Apocalypse",
        "osis": "Rev",
        "t": "NT",
        "titles": ["APOCALYPSE", "APOCAIMPSE"],
        "anchors": ["APOCALYPSE.", "REVELATION DE JESUS-CHRIST"],
    },
]

# Capítulos esperados (canon protestante) — validação / hints
EXPECTED_CHAPTERS: dict[str, int] = {
    "Gen": 50, "Exod": 40, "Lev": 27, "Num": 36, "Deut": 34, "Josh": 24, "Judg": 21,
    "Ruth": 4, "1Sam": 31, "2Sam": 24, "1Kgs": 22, "2Kgs": 25, "1Chr": 29, "2Chr": 36,
    "Ezra": 10, "Neh": 13, "Esth": 10, "Job": 42, "Ps": 150, "Prov": 31, "Eccl": 12,
    "Song": 8, "Isa": 66, "Jer": 52, "Lam": 5, "Ezek": 48, "Dan": 12, "Hos": 14,
    "Joel": 3, "Amos": 9, "Obad": 1, "Jonah": 4, "Mic": 7, "Nah": 3, "Hab": 3,
    "Zeph": 3, "Hag": 2, "Zech": 14, "Mal": 4, "Matt": 28, "Mark": 16, "Luke": 24,
    "John": 21, "Acts": 28, "Rom": 16, "1Cor": 16, "2Cor": 13, "Gal": 6, "Eph": 6,
    "Phil": 4, "Col": 4, "1Thess": 5, "2Thess": 3, "1Tim": 6, "2Tim": 4, "Titus": 3,
    "Phlm": 1, "Heb": 13, "Jas": 5, "1Pet": 5, "2Pet": 3, "1John": 5, "2John": 1,
    "3John": 1, "Jude": 1, "Rev": 22,
}

HEADER_RE = re.compile(
    r"^(.+?)\s+(\d+)[\.:](\d+)(?:\s|$)"
)
# Versículo OCR: "2La" / "3«" OU após pontuação ". 4 Dieu" / ": 12 la terre"
VERSE_SPLIT_RE = re.compile(
    r"(?:"
    r"(?<=[.!?»\":])\s+(\d{1,3})\s+(?=\S)"  # '. 4 Dieu' / ': 12 la'
    r"|"
    r"(?<![0-9A-Za-zÀ-ü])(\d{1,3})(?=[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇŒÆ«\"'(])"  # '2La' / '3«'
    r")"
)
FOOTNOTE_RE = re.compile(
    r"^\d{1,3}\.\d{1,3}\s+\S+"  # 2.24 note…
)
SECTION_RANGE_RE = re.compile(r"\b(\d{1,3})\.\d{1,3}\s*[-–—]\s*\d{1,3}\.\d{1,3}\b")
# Capítulo isolado (layout tipográfico): linha só com número
CHAPTER_ONLY_RE = re.compile(r"^(\d{1,3})$")
# Início de capítulo estilo "2 *Pourquoi" (Psaumes)
CHAPTER_LEAD_RE = re.compile(
    r"^(\d{1,3})\s*[\*†‡]?\s*(?=[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇŒÆ«\"'])"
)

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper().replace("'", "'").replace("'", "'")
    return re.sub(r"\s+", " ", s).strip()


def clean_text(s: str) -> str:
    s = s.replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    # juntar hifenização OCR: "au- des-" + "sus" → "au-dessus" já partido por linhas
    s = re.sub(r"(\w)-\s+(\w)", r"\1\2", s)
    s = re.sub(r"\s+", " ", s).strip()
    # aspas tipográficas
    s = s.replace("«", "«").replace("»", "»")
    return s


@dataclass
class Verse:
    n: int
    text: str


@dataclass
class Chapter:
    n: int
    verses: list[Verse] = field(default_factory=list)


@dataclass
class BookOut:
    meta: dict
    start: int
    end: int
    chapters: list[Chapter] = field(default_factory=list)


def find_book_starts(
    lines: list[str], start_cursor: int | None = None
) -> list[tuple[dict, int]]:
    """Encontra início de cada livro em ordem canónica."""
    title_index: dict[str, list[int]] = {}
    for i, line in enumerate(lines):
        n = norm(line)
        if not n or len(n) > 40:
            continue
        title_index.setdefault(n, []).append(i)

    if start_cursor is None:
        start_cursor = 0
        for i, line in enumerate(lines):
            n = norm(line)
            # início real: "GENESE Le Livre…" (não TOC curto)
            if n.startswith("GENESE ") and "LIVRE" in n:
                start_cursor = i
                break
            if n == "GENESE":
                # confirmar que a seguir há conteúdo, não só índice
                nxt = norm(lines[i + 1]) if i + 1 < len(lines) else ""
                if "LIVRE" in nxt or "AU COMMENCEMENT" in nxt or len(nxt) > 80:
                    start_cursor = i
                    break
        else:
            for i, line in enumerate(lines):
                if "AU COMMENCEMENT" in norm(line) and "DIEU CREA" in norm(line):
                    start_cursor = max(0, i - 2)
                    break

    starts: list[tuple[dict, int]] = []
    cursor = start_cursor

    def line_has_book_title(nline: str, tn: str) -> bool:
        if nline == tn:
            return True
        if not nline.startswith(tn + " "):
            return False
        rest = nline[len(tn) + 1 :]
        # cabeçalho corrente "GENESE 2.4 …" — não é início de livro
        if re.match(r"^\d+[\.:]\d+", rest):
            return False
        return True

    for bi, book in enumerate(BOOKS):
        found: int | None = None

        # 1) âncoras textuais (Psaumes, Apocalypse…)
        for anchor in book.get("anchors") or []:
            an = norm(anchor)
            for i in range(cursor, len(lines)):
                if an in norm(lines[i]):
                    found = i
                    break
            if found is not None:
                break

        # 2) título exacto (linha só com o nome) — ignorar TOC curto isolado
        if found is None:
            for title in book["titles"]:
                tn = norm(title)
                for i in title_index.get(tn, []):
                    if i < cursor:
                        continue
                    # TOC: linha só com o nome e vizinhas também curtas
                    if len(lines[i].strip()) <= len(title) + 2:
                        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                        if len(nxt) < 40 and not any(
                            norm(nxt).startswith(norm(t) + " ")
                            or norm(nxt) == norm(t)
                            for t in book["titles"]
                        ):
                            # possível título real se a linha seguinte for intro longa
                            if len(nxt) < 20:
                                continue
                    found = i
                    break
                if found is not None:
                    break

        # 2b) título no início de linha longa (EPUB OCR)
        if found is None:
            # títulos mais longos primeiro
            for title in sorted(book["titles"], key=len, reverse=True):
                tn = norm(title)
                for i in range(cursor, len(lines)):
                    if line_has_book_title(norm(lines[i]), tn):
                        found = i
                        break
                if found is not None:
                    break

        # 3) primeiro cabeçalho corrente LIVRE n.m após cursor (início ou meio de linha)
        if found is None:
            for title in sorted(book["titles"], key=len, reverse=True):
                tn = norm(title)
                hdr = re.compile(
                    rf"(?<![A-Z0-9]){re.escape(tn)}\s+(\d+)[\.:](\d+)"
                )
                for i in range(cursor, len(lines)):
                    n = norm(lines[i])
                    m = hdr.search(n)
                    if not m:
                        continue
                    # preferir capítulo baixo (início do livro)
                    ch = int(m.group(1))
                    if ch > 3 and book["osis"] not in ("Obad", "Phlm", "2John", "3John", "Jude"):
                        # ainda assim aceitar se for a primeira ocorrência
                        pass
                    found = i
                    break
                if found is not None:
                    break

        if found is None:
            if book.get("optional"):
                print(
                    f"aviso: livro opcional não encontrado: {book['livro']} "
                    f"(após linha {cursor}) — ignorado"
                )
                continue
            raise SystemExit(
                f"livro não encontrado: {book['livro']} (após linha {cursor})"
            )

        # Cantique: preferir "CANTIQUE DES CANTIQUES"
        if book["osis"] == "Song":
            for i in range(cursor, len(lines)):
                if line_has_book_title(norm(lines[i]), norm("CANTIQUE DES CANTIQUES")):
                    found = i
                    break

        # Actes: preferir título longo
        if book["osis"] == "Acts":
            for i in range(cursor, len(lines)):
                n = norm(lines[i])
                if "ACTES DES APOTRES" in n or line_has_book_title(n, norm("ACTES DES APOTRES")):
                    found = i
                    break

        starts.append((book, found))
        cursor = found + 1

    return starts


def parse_header_chapter(line: str, book_titles: set[str]) -> int | None:
    """Aceita cabeçalho no início ou embutido (EPUB OCR)."""
    n = norm(line)
    # títulos longos primeiro
    for tn in sorted(book_titles, key=len, reverse=True):
        m = re.search(rf"(?<![A-Z0-9]){re.escape(tn)}\s+(\d+)[\.:](\d+)", n)
        if m:
            return int(m.group(1))
    m = HEADER_RE.match(line.strip())
    if not m:
        return None
    if norm(m.group(1)) not in book_titles:
        return None
    return int(m.group(2))


def is_running_header(line: str, book_titles: set[str]) -> bool:
    return parse_header_chapter(line, book_titles) is not None


def is_noise_line(line: str, book_titles: set[str]) -> bool:
    s = line.strip()
    if not s:
        return True
    if is_running_header(s, book_titles):
        return True
    if FOOTNOTE_RE.match(s) and len(s) < 120:
        if re.search(r"\b(voir|renvoi|cit[eé]|page)\b", s, re.I):
            return True
        if re.match(r"^\d+\.\d+\s+[a-zàâäéèêëïîôùûüç]", s):
            return True
    n = norm(s)
    if n in book_titles and len(s) < 40:
        return True
    if re.fullmatch(r"\d{1,3}", s):
        return True
    if len(s) <= 2 and not re.search(r"[A-Za-zÀ-ü]", s):
        return True
    return False


def extract_book_body(
    lines: list[str], start: int, end: int, book: dict
) -> list[Chapter]:
    titles = {norm(t) for t in book["titles"]}
    if book["osis"] == "Ps":
        titles.add(norm("PSAUMES"))
    if book["osis"] == "Acts":
        titles.update({norm("ACTES"), norm("ACTES DES APOTRES")})
    if book["osis"] == "Nah":
        titles.update({norm("NAHUM"), norm("NAHOUM")})
    if book["osis"] == "Jude":
        titles.update({norm("JUDAS"), norm("JUDE"), norm("IUDE")})
    if book["osis"] == "2John":
        titles.update({norm("2 JEAN"), norm("2JEAN")})
    if book["osis"] == "3John":
        titles.update({norm("3 JEAN"), norm("3JEAN")})
    if book["osis"] == "Rev":
        titles.update({norm("APOCALYPSE"), norm("APOCAIMPSE")})

    expected_caps = EXPECTED_CHAPTERS.get(book["osis"], 50)

    i = start + 1
    while i < end:
        s = lines[i].strip()
        if SECTION_RANGE_RE.search(s):
            i += 1
            break
        if "PREMIER LIVRE" in norm(s):
            i += 1
            break
        if VERSE_SPLIT_RE.search(s) and re.search(r"[A-Za-zÀ-ü]{4,}", s):
            break
        i += 1

    # Acumular texto com marcadores de capítulo explícitos
    pieces: list[tuple[int | None, str]] = []  # (forced_chapter|None, text)
    current_forced: int | None = 1

    while i < end:
        s = lines[i].strip()
        ch = parse_header_chapter(s, titles)
        if ch is not None:
            current_forced = ch
            pieces.append((current_forced, ""))  # marker
            i += 1
            continue
        m = SECTION_RANGE_RE.search(s)
        if m and len(s) < 90:
            current_forced = int(m.group(1))
            pieces.append((current_forced, ""))
            i += 1
            continue
        # Psaumes / capítulos: "2 *Pourquoi"
        m2 = CHAPTER_LEAD_RE.match(s)
        if book["osis"] == "Ps" and m2:
            cn = int(m2.group(1))
            if 1 <= cn <= expected_caps:
                current_forced = cn
                rest = s[m2.end() :].strip()
                pieces.append((current_forced, rest))
                i += 1
                continue
        if is_noise_line(s, titles):
            i += 1
            continue
        if (
            len(s) < 45
            and not VERSE_SPLIT_RE.search(s)
            and not re.search(r"\d", s)
            and s[:1].isupper()
            and not s.endswith((".", "»", "!", "?", ",", ";", ":"))
            and not s.lower().endswith(
                (" et", " de", " du", " la", " le", " les", " des", " un", " une", " au", " aux")
            )
        ):
            i += 1
            continue
        pieces.append((None, s))
        i += 1

    # Agrupar por capítulo forçado; dentro de cada bloco, partir versículos
    # e detetar resets (verso 1) para subcapítulos em falta
    chapters: list[Chapter] = []
    bucket_ch = 1
    bucket_text: list[str] = []

    def emit_bucket():
        nonlocal bucket_text, bucket_ch
        if not bucket_text:
            return
        text = clean_text(" ".join(bucket_text))
        verses = split_verses(text)
        # partir em capítulos pelo reset da numeração
        chapters.extend(split_by_verse_resets(verses, bucket_ch, expected_caps))
        bucket_text = []

    for forced, frag in pieces:
        if forced is not None and frag == "":
            emit_bucket()
            bucket_ch = forced
            continue
        if forced is not None and frag:
            emit_bucket()
            bucket_ch = forced
            bucket_text.append(frag)
            continue
        bucket_text.append(frag)
    emit_bucket()

    # fundir capítulos duplicados / ordenar
    merged: dict[int, list[Verse]] = {}
    for ch in chapters:
        merged.setdefault(ch.n, []).extend(ch.verses)
    result: list[Chapter] = []
    for cn in sorted(merged):
        vs = repair_verse_sequence(merged[cn])
        # dedupe by verse number keeping longest text
        by_n: dict[int, str] = {}
        for v in vs:
            if v.n not in by_n:
                by_n[v.n] = v.text
            else:
                # manter o primeiro; anexar só se o novo for claramente continuação curta
                if len(v.text) > 20 and v.text not in by_n[v.n]:
                    pass
        result.append(
            Chapter(n=cn, verses=[Verse(n, by_n[n]) for n in sorted(by_n)])
        )
    return result


def split_by_verse_resets(
    verses: list[Verse], start_chapter: int, max_chapter: int
) -> list[Chapter]:
    """Quando a numeração volta a 1 após versos altos, avança o capítulo."""
    if not verses:
        return []
    out: list[Chapter] = []
    ch = max(1, start_chapter)
    buf: list[Verse] = []
    last_n = 0

    def flush():
        nonlocal buf, ch
        if buf:
            out.append(Chapter(n=ch, verses=list(buf)))
            buf = []

    for v in verses:
        # reset só se claramente novo capítulo (verso 1 após >= 4)
        if buf and v.n == 1 and last_n >= 4:
            flush()
            if ch < max_chapter:
                ch += 1
        buf.append(v)
        last_n = v.n
    flush()
    return out


def split_verses(text: str) -> list[Verse]:
    if not text:
        return []
    verses: list[Verse] = []
    last = 0
    for m in VERSE_SPLIT_RE.finditer(text):
        num_s = m.group(1) or m.group(2)
        num = int(num_s)
        chunk = text[last : m.start()]
        if verses:
            verses[-1] = Verse(verses[-1].n, clean_verse_text(verses[-1].text + chunk))
        else:
            pre = clean_verse_text(chunk)
            if pre:
                verses.append(Verse(1, pre))
            elif num != 1:
                # texto começa directamente no verso N
                pass
        # iniciar novo verso (texto depois do marcador)
        last = m.end()
        verses.append(Verse(num, ""))
    tail = text[last:]
    if verses:
        verses[-1] = Verse(verses[-1].n, clean_verse_text(verses[-1].text + tail))
    elif tail.strip():
        verses.append(Verse(1, clean_verse_text(tail)))
    verses = [v for v in verses if v.text and len(v.text) > 1]
    return repair_verse_sequence(verses)


def clean_verse_text(s: str) -> str:
    s = clean_text(s)
    # remover artefactos no início
    s = re.sub(r"^[\s\|\[\]`'\"«»*_~]+", "", s)
    s = re.sub(r"\s+([;:,\.!?»])", r"\1", s)
    return s.strip()


def repair_verse_sequence(verses: list[Verse]) -> list[Verse]:
    """Corrige só dígitos truncados óbvios (10→0, 11→1). Não funde regressões."""
    if not verses:
        return verses
    out: list[Verse] = []
    for v in verses:
        n = v.n
        if out:
            prev = out[-1].n
            if n == 0 and prev % 10 == 9:
                n = prev + 1
            elif n == 1 and prev == 10:
                n = 11
            elif (
                2 <= n <= 9
                and prev >= 10
                and prev % 10 == 9
                and prev + 1 == (prev // 10) * 10 + 10 + n
            ):
                n = prev + 1
        out.append(Verse(n, v.text))
    return [v for v in out if v.text and len(v.text) > 1]


def build_payload(books: list[BookOut]) -> dict:
    out_books = []
    for b in books:
        chapters = []
        for ch in b.chapters:
            chapters.append(
                {
                    "capitulo": ch.n,
                    "verses": [
                        {"versiculo": v.n, "texto": v.text} for v in ch.verses
                    ],
                }
            )
        out_books.append(
            {
                "testamento": b.meta["t"],
                "livro": b.meta["livro"],
                "livro_osis": b.meta["osis"],
                "chapters": chapters,
            }
        )
    total = sum(
        len(v["verses"]) for b in out_books for v in b["chapters"]
    )
    return {
        "version": "S21",
        "source": "archive.org/la-bible-segond-21 (djvu OCR)",
        "note": (
            "Extraído de OCR — qualidade variável. "
            "Segond 21 © Société Biblique de Genève. Uso pessoal / autorização."
        ),
        "stats": {
            "books": len(out_books),
            "verses": total,
        },
        "books": out_books,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=DEFAULT_TXT)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--report", action="store_true", help="mostrar gaps vs canon")
    args = ap.parse_args()

    if not args.input.exists():
        raise SystemExit(
            f"falta {args.input}\n"
            "Descarrega:\n"
            "  curl -L -o data/raw/s21_full.txt "
            "'https://archive.org/download/la-bible-segond-21/"
            "La%20Bible%20-%20%20Segond%2021%20_djvu.txt'"
        )

    text = args.input.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    print(f"linhas={len(lines)} ficheiro={args.input}")

    starts = find_book_starts(lines)
    print(f"livros detectados={len(starts)}")

    books_out: list[BookOut] = []
    for idx, (book, start) in enumerate(starts):
        end = starts[idx + 1][1] if idx + 1 < len(starts) else len(lines) - 200
        # não incluir colofão final
        chapters = extract_book_body(lines, start, end, book)
        books_out.append(BookOut(meta=book, start=start, end=end, chapters=chapters))
        nver = sum(len(c.verses) for c in chapters)
        exp = EXPECTED_CHAPTERS.get(book["osis"])
        flag = ""
        if exp and abs(len(chapters) - exp) > 2:
            flag = f" ⚠ caps {len(chapters)}≠{exp}"
        print(
            f"  {book['osis']:7} {book['livro']:<28} "
            f"L{start+1}-{end+1}  caps={len(chapters):3} vers={nver:5}{flag}"
        )

    payload = build_payload(books_out)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n→ {args.output}  ({payload['stats']['verses']} versículos)")

    if args.report:
        print("\nRelatório capítulos:")
        for b in books_out:
            exp = EXPECTED_CHAPTERS.get(b.meta["osis"])
            got = len(b.chapters)
            if exp and got != exp:
                print(f"  {b.meta['osis']}: {got} (esperado {exp})")


if __name__ == "__main__":
    main()
