# Bible S21 local (SD / Raspberry Pi / PC)

Consultation hors-ligne de la **Bible Segond 21** via SQLite en lecture seule, API FastAPI légère et UI HTML statique.

> **Licence du texte :** Segond 21 © Société Biblique de Genève. Ce dépôt **ne redistribue pas** le corpus complet. Place ton JSON (usage personnel / autorisation) dans `data/raw/s21.json`. Un fixture minimal (Gn 1, Dn 12, Jn 3) sert uniquement au développement.

Aligné conceptuellement avec YouVersion S21 (`version_id` 152) du projet clevenrec — références OSIS du type `Dan.12.4`.

## Architecture

| Couche | Choix |
|--------|--------|
| Données | SQLite (`data/biblia.db`) + FTS5 |
| API | FastAPI, DB ouverte en `mode=ro` |
| UI | HTML + CSS local + JS natif |
| Logs | stdout seulement (`access_log=False`) — pas d’écritures inutiles sur SD |

## Setup (PC)

```bash
cd C:\Users\Clevy\Projects\bible_s21_sd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# base de démo (fixture)
python scripts/migrate.py --fixture

# ou corpus complet que tu fournis
# copy ton fichier → data\raw\s21.json
# python scripts/migrate.py

python server.py
```

Ouvre [http://127.0.0.1:8765](http://127.0.0.1:8765).

Variables :

| Env | Défaut | Rôle |
|-----|--------|------|
| `BIBLIA_DB` | `data/biblia.db` | chemin SQLite |
| `BIBLIA_HOST` | `127.0.0.1` | bind (`0.0.0.0` sur Pi/LAN) |
| `BIBLIA_PORT` | `8765` | port |

## Import OCR Archive.org → JSON → SQLite

Fonte fulltext (OCR DjVu) — **uso pessoal / autorização**, © Société Biblique de Genève:

1. Descarregar o texto bruto:

```powershell
curl.exe -L -o data\raw\s21_full.txt "https://archive.org/download/la-bible-segond-21/La%20Bible%20-%20%20Segond%2021%20_djvu.txt"
```

2. Estruturar em livros / capítulos / versículos:

```powershell
.\.venv\Scripts\python.exe scripts\parse_s21_djvu.py --report
# → data\raw\s21.json
```

3. Migrar para a base:

```powershell
.\.venv\Scripts\python.exe scripts\migrate.py --input data\raw\s21.json
```

O OCR é imperfeito (números truncados, notas misturadas). O parser deteta os **66 livros** do cânone protestante e repara sequências óbvias; convém validar passagens críticas. Os ficheiros `data/raw/*` não entram no git.

## Format JSON d’import

```json
{
  "version": "S21",
  "books": [
    {
      "testamento": "AT",
      "livro": "Daniel",
      "livro_osis": "Dan",
      "chapters": [
        {
          "capitulo": 12,
          "verses": [
            { "versiculo": 4, "texto": "…" }
          ]
        }
      ]
    }
  ]
}
```

Liste plate aussi acceptée : objets avec `testamento`, `livro`, `livro_osis`, `capitulo`, `versiculo`, `texto`.

## API

| Route | Exemple |
|-------|---------|
| `GET /livros` | livres + nb chapitres |
| `GET /capitulo?livro=Daniel&capitulo=12` | tout le chapitre |
| `GET /versiculo?livro=Dan&capitulo=12&versiculo=4` | un verset |
| `GET /buscar?q=connaissance` | FTS5 / LIKE |
| `GET /ref/Dan.12.4` | style YouVersion |

## Cartão SD / Raspberry Pi

1. **Migrer sur le PC** (écritures + `VACUUM`), puis **copier seulement** `data/biblia.db` + le code sur la carte.  
2. Ne **jamais** relancer `migrate.py` sur le SD au quotidien.  
3. L’API ouvre la base en **read-only** (`file:…?mode=ro` + `PRAGMA query_only=ON`).  
4. Sur le Pi :

```bash
export BIBLIA_HOST=0.0.0.0
export BIBLIA_PORT=8765
python server.py
```

5. Logs : journald / console uniquement — pas de fichier d’access log sur la partition SD.  
6. Optionnel : monter `/tmp` en tmpfs si tu dois écrire des caches temporaires.

## Android (Capacitor, offline)

App `com.clevenrec.bibles21` — mesma UI, SQLite nativa (`@capacitor-community/sqlite`), sem rede nem FastAPI no telemóvel.

**Pré-requisitos:** Node.js, Android SDK, ADB, JDK (Android Studio JBR recomendado), LG com USB debugging.

**1.ª instalação / sync de alterações** (UI, CSS, JS ou `data/biblia.db`):

```powershell
cd C:\Users\Clevy\Projects\bible_s21_sd
.\scripts\android-deploy.ps1
# ou: .\scripts\android-deploy.ps1 -Serial LMK410HMYP8HSWCIUO
```

O script: copia a DB → build Vite → `cap sync` → `assembleDebug` → `adb install -r` → abre a app.

Só build sem instalar: `.\scripts\android-deploy.ps1 -SkipInstall`.

O corpus completo continua a ser o teu JSON local (`data/raw/s21.json`) — o repositório não o redistribui; o APK embute a `biblia.db` que tiveres gerado com `migrate.py`.

## Commandes utiles

```bash
python scripts/migrate.py --fixture
python scripts/parse_s21_djvu.py --report
python scripts/migrate.py --input data/raw/s21.json --db data/biblia.db
python server.py
.\scripts\android-deploy.ps1
```
