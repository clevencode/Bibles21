import { livros as apiLivros, capitulo as apiCapitulo, buscar as apiBuscar } from "./api.js";

(() => {
  const $ = (id) => document.getElementById(id);
  const selT = $("sel-testamento");
  const selL = $("sel-livro");
  const selC = $("sel-capitulo");
  const selV = $("sel-versiculo");
  const titulo = $("titulo-cap");
  const box = $("versiculos");
  const status = $("status");
  const resultados = $("resultados");
  const form = $("form-busca");
  const qInput = $("q");
  const btnSearch = $("btn-search");
  const btnClear = $("btn-clear-search");
  const btnCloseResults = $("btn-close-results");
  const searchPanel = $("search-panel");
  const searchMeta = $("search-meta");
  const searchHint = $("search-hint");
  const btnPrev = $("btn-prev");
  const btnNext = $("btn-next");
  const reader = document.querySelector(".reader");

  const MIN_Q = 2;
  const DEBOUNCE_MS = 360;
  const SEARCH_LIMIT = 50;
  const STORAGE_KEY = "bibles21.lastRef";

  let books = [];
  let currentVerses = [];
  let currentOsis = "";
  let currentLivro = "";
  let currentCap = 0;
  let searchSeq = 0;
  let loadSeq = 0;
  let debounceTimer = null;
  let suppressHash = false;

  function norm(s) {
    return String(s || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/['’]/g, "'")
      .replace(/\s+/g, " ")
      .trim();
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function setReading(busy) {
    reader?.setAttribute("aria-busy", busy ? "true" : "false");
    reader?.classList.toggle("is-loading", busy);
    [selT, selL, selC, selV, btnPrev, btnNext].forEach((el) => {
      if (el) el.disabled = busy;
    });
  }

  function savePosition(ver) {
    try {
      const payload = {
        osis: currentOsis,
        livro: currentLivro,
        cap: currentCap,
        ver: ver ? Number(ver) : null,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch {
      /* ignore quota / private mode */
    }
  }

  function readSavedPosition() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  function bookIndex(livro) {
    return books.findIndex((b) => b.livro === livro);
  }

  function fillTestamentos(prefer) {
    const set = [...new Set(books.map((b) => b.testamento))];
    selT.innerHTML = set
      .map(
        (t) =>
          `<option value="${t}">${t === "AT" ? "Ancien Testament" : "Nouveau Testament"}</option>`
      )
      .join("");
    if (prefer && set.includes(prefer)) selT.value = prefer;
  }

  function fillLivros(preferLivro) {
    const t = selT.value;
    const list = books.filter((b) => b.testamento === t);
    selL.innerHTML = list
      .map(
        (b) =>
          `<option value="${b.livro}" data-osis="${b.livro_osis}" data-caps="${b.n_capitulos}">${b.livro}</option>`
      )
      .join("");
    if (preferLivro && list.some((b) => b.livro === preferLivro)) {
      selL.value = preferLivro;
    }
    fillCapitulos();
  }

  function fillCapitulos(preferCap) {
    const opt = selL.selectedOptions[0];
    const n = opt ? Number(opt.dataset.caps || 1) : 1;
    selC.innerHTML = Array.from({ length: n }, (_, i) => {
      const c = i + 1;
      return `<option value="${c}">${c}</option>`;
    }).join("");
    if (preferCap && preferCap >= 1 && preferCap <= n) {
      selC.value = String(preferCap);
    }
    fillVersiculos([]);
  }

  function fillVersiculos(verses, prefer) {
    currentVerses = verses || [];
    selV.innerHTML = ['<option value="">Tout</option>']
      .concat(
        currentVerses.map(
          (v) => `<option value="${v.versiculo}">${v.versiculo}</option>`
        )
      )
      .join("");
    if (
      prefer != null &&
      currentVerses.some((v) => String(v.versiculo) === String(prefer))
    ) {
      selV.value = String(prefer);
    } else {
      selV.value = "";
    }
  }

  function updateChapterButtons() {
    const idx = bookIndex(selL.value);
    const cap = Number(selC.value) || 1;
    const book = books[idx];
    const maxCap = book ? Number(book.n_capitulos) : 1;
    btnPrev.disabled = idx <= 0 && cap <= 1;
    btnNext.disabled = idx >= books.length - 1 && cap >= maxCap;
  }

  function clearVerseHighlight() {
    box
      .querySelectorAll("p.is-active")
      .forEach((el) => el.classList.remove("is-active"));
  }

  function setHash(osis, cap, ver) {
    if (suppressHash) return;
    const next = ver ? `#${osis}.${cap}.${ver}` : `#${osis}.${cap}`;
    if (location.hash !== next) {
      history.replaceState(null, "", next);
    }
  }

  function goToVerse(ver, { scroll = true, updateHash = true } = {}) {
    clearVerseHighlight();
    if (!ver) {
      if (updateHash && currentOsis && currentCap) {
        setHash(currentOsis, currentCap, null);
      }
      savePosition(null);
      return;
    }
    const el = document.getElementById(`v-${ver}`);
    if (!el) return;
    el.classList.add("is-active");
    if (scroll) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    if (updateHash && currentOsis && currentCap) {
      setHash(currentOsis, currentCap, ver);
    }
    savePosition(ver);
  }

  async function loadCapitulo(preferVerse, { scrollTop = true } = {}) {
    const livro = selL.value;
    const capitulo = Number(selC.value);
    if (!livro || !capitulo) return;

    const seq = ++loadSeq;
    setReading(true);
    status.textContent = "Chargement…";
    updateChapterButtons();

    try {
      const data = await apiCapitulo(livro, capitulo);
      if (seq !== loadSeq) return;

      currentOsis = data.livro_osis;
      currentLivro = data.livro;
      currentCap = data.capitulo;

      titulo.textContent = `${data.livro} ${data.capitulo}`;
      box.innerHTML = data.versiculos
        .map(
          (v) =>
            `<p id="v-${v.versiculo}" data-ver="${v.versiculo}" tabindex="0"><sup class="v-num" aria-hidden="true">${v.versiculo}</sup><span class="v-text">${escapeHtml(v.texto)}</span></p>`
        )
        .join("");
      fillVersiculos(data.versiculos, preferVerse);
      status.textContent = `${data.versiculos.length} versets · ${data.livro_osis}.${data.capitulo}`;
      updateChapterButtons();

      if (preferVerse) {
        // attendre layout
        requestAnimationFrame(() =>
          goToVerse(preferVerse, { scroll: true, updateHash: true })
        );
      } else {
        setHash(data.livro_osis, data.capitulo, null);
        savePosition(null);
        if (scrollTop) window.scrollTo({ top: 0, behavior: "smooth" });
      }
    } catch (e) {
      if (seq !== loadSeq) return;
      status.textContent = String(e.message || e);
      box.innerHTML = "";
      fillVersiculos([]);
      currentOsis = "";
      currentLivro = "";
      currentCap = 0;
    } finally {
      if (seq === loadSeq) setReading(false);
    }
  }

  async function gotoRef(livro, cap, ver) {
    const tBook = books.find((b) => b.livro === livro);
    if (!tBook) return;
    fillTestamentos(tBook.testamento);
    fillLivros(livro);
    fillCapitulos(Number(cap));
    await loadCapitulo(ver || undefined, { scrollTop: !ver });
  }

  async function stepChapter(delta) {
    const idx = bookIndex(selL.value);
    if (idx < 0) return;
    let cap = Number(selC.value) || 1;
    let nextIdx = idx;
    let nextCap = cap + delta;
    const book = books[idx];
    const maxCap = Number(book.n_capitulos);

    if (nextCap < 1) {
      if (idx === 0) return;
      nextIdx = idx - 1;
      nextCap = Number(books[nextIdx].n_capitulos);
    } else if (nextCap > maxCap) {
      if (idx >= books.length - 1) return;
      nextIdx = idx + 1;
      nextCap = 1;
    }

    const next = books[nextIdx];
    fillTestamentos(next.testamento);
    fillLivros(next.livro);
    fillCapitulos(nextCap);
    await loadCapitulo(undefined, { scrollTop: true });
  }

  /** Jean 3:16 / Dan.12.4 / 1 Jean 2:1 */
  function parseReference(raw) {
    const q = raw.trim();
    if (!q) return null;

    let m = q.match(/^([A-Za-z0-9]+)\.(\d+)(?:\.(\d+))?$/);
    if (m) {
      const book = books.find(
        (b) => b.livro_osis.toLowerCase() === m[1].toLowerCase()
      );
      if (!book) return null;
      return {
        book,
        cap: Number(m[2]),
        ver: m[3] ? Number(m[3]) : null,
        kind: "osis",
      };
    }

    m = q.match(
      /^((?:[123]\s*)?[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’\-]*(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’\-]*)*)\s+(\d+)(?:\s*[:\.]\s*(\d+))?$/u
    );
    if (!m) return null;

    const name = norm(m[1]);
    const cap = Number(m[2]);
    const ver = m[3] ? Number(m[3]) : null;

    const book =
      books.find((b) => norm(b.livro) === name) ||
      books.find((b) => norm(b.livro_osis) === name) ||
      books.find((b) => norm(b.livro).startsWith(name)) ||
      books.find((b) => name.startsWith(norm(b.livro)));

    if (!book) return null;
    if (cap < 1 || cap > Number(book.n_capitulos)) return null;
    return { book, cap, ver, kind: "human" };
  }

  function highlightSnippet(text, q) {
    const safe = escapeHtml(text);
    const tokens = (q.match(/[\wàâäéèêëïîôùûüçœæ'-]+/gi) || []).slice(0, 6);
    if (!tokens.length) return safe;
    let out = safe;
    for (const t of tokens) {
      const re = new RegExp(
        `(${t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`,
        "gi"
      );
      out = out.replace(re, "<mark>$1</mark>");
    }
    return out;
  }

  function setClearVisible() {
    btnClear.hidden = !qInput.value.trim();
  }

  function closeSearchPanel() {
    searchPanel.hidden = true;
    resultados.innerHTML = "";
    searchMeta.textContent = "";
  }

  function openSearchPanel() {
    searchPanel.hidden = false;
  }

  function setSearching(on) {
    btnSearch.disabled = on;
    btnSearch.textContent = on ? "…" : "Chercher";
    qInput.setAttribute("aria-busy", on ? "true" : "false");
  }

  function renderResults(q, data) {
    const list = data.results || [];
    openSearchPanel();
    if (!list.length) {
      searchMeta.textContent = `Aucun résultat pour « ${q} »`;
      resultados.innerHTML =
        "<li class='muted'>Essayez un autre mot ou une référence (ex. Jean 3:16).</li>";
      return;
    }
    const truncated = list.length >= SEARCH_LIMIT;
    searchMeta.textContent = truncated
      ? `${list.length}+ résultats`
      : `${list.length} résultat${list.length > 1 ? "s" : ""}`;

    resultados.innerHTML = list
      .map((r) => {
        const snippet = highlightSnippet(r.texto.slice(0, 140), q);
        const label = `${escapeHtml(r.livro)} ${r.capitulo}:${r.versiculo}`;
        return `<li role="option"><button type="button" class="result-item" data-livro="${escapeHtml(r.livro)}" data-cap="${r.capitulo}" data-ver="${r.versiculo}"><span class="result-ref">${label}</span><span class="result-snip">${snippet}${r.texto.length > 140 ? "…" : ""}</span></button></li>`;
      })
      .join("");
  }

  async function runTextSearch(q) {
    const seq = ++searchSeq;
    setSearching(true);
    openSearchPanel();
    searchMeta.textContent = "Recherche…";
    resultados.innerHTML = "<li class='muted'>…</li>";
    try {
      const data = await apiBuscar(q, SEARCH_LIMIT);
      if (seq !== searchSeq) return;
      renderResults(q, data);
    } catch (e) {
      if (seq !== searchSeq) return;
      openSearchPanel();
      searchMeta.textContent = "Erreur";
      resultados.innerHTML = `<li class="error">${escapeHtml(e.message || e)}</li>`;
    } finally {
      if (seq === searchSeq) setSearching(false);
    }
  }

  async function runSearch({ fromSubmit = false } = {}) {
    const q = qInput.value.trim();
    setClearVisible();

    if (!q) {
      closeSearchPanel();
      searchHint.textContent = "Référence ou texte (≥ 2 lettres).";
      return;
    }

    const ref = parseReference(q);
    if (ref) {
      searchHint.textContent = ref.ver
        ? `Référence : ${ref.book.livro} ${ref.cap}:${ref.ver}`
        : `Référence : ${ref.book.livro} ${ref.cap}`;
      if (fromSubmit || ref.kind === "osis" || ref.ver != null) {
        closeSearchPanel();
        await gotoRef(ref.book.livro, ref.cap, ref.ver);
        return;
      }
      if (!fromSubmit) return;
      closeSearchPanel();
      await gotoRef(ref.book.livro, ref.cap, null);
      return;
    }

    if (q.length < MIN_Q) {
      closeSearchPanel();
      searchHint.textContent = `Encore ${MIN_Q - q.length} caractère(s)…`;
      return;
    }

    searchHint.textContent = "Recherche dans le texte…";
    await runTextSearch(q);
  }

  function scheduleSearch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => runSearch({ fromSubmit: false }), DEBOUNCE_MS);
  }

  function applyHash() {
    const h = location.hash.replace(/^#/, "");
    const m = h.match(/^([A-Za-z0-9]+)\.(\d+)(?:\.(\d+))?$/);
    if (!m || !books.length) return false;
    const book = books.find(
      (b) => b.livro_osis.toLowerCase() === m[1].toLowerCase()
    );
    if (!book) return false;
    suppressHash = true;
    fillTestamentos(book.testamento);
    fillLivros(book.livro);
    fillCapitulos(Number(m[2]));
    suppressHash = false;
    loadCapitulo(m[3] || undefined, { scrollTop: !m[3] });
    return true;
  }

  async function boot() {
    try {
      books = await apiLivros();
      if (!books.length) {
        status.textContent = "Base vide — lancez migrate.py";
        return;
      }

      fillTestamentos();
      fillLivros();

      selT.addEventListener("change", () => {
        fillLivros();
        loadCapitulo(undefined, { scrollTop: true });
      });
      selL.addEventListener("change", () => {
        fillCapitulos();
        loadCapitulo(undefined, { scrollTop: true });
      });
      selC.addEventListener("change", () =>
        loadCapitulo(undefined, { scrollTop: true })
      );
      selV.addEventListener("change", () => {
        const ver = selV.value;
        goToVerse(ver || null, { scroll: Boolean(ver), updateHash: true });
      });

      btnPrev.addEventListener("click", () => stepChapter(-1));
      btnNext.addEventListener("click", () => stepChapter(1));

      box.addEventListener("click", (e) => {
        const p = e.target.closest("p[data-ver]");
        if (!p) return;
        selV.value = p.dataset.ver;
        goToVerse(p.dataset.ver);
      });
      box.addEventListener("keydown", (e) => {
        if (e.key !== "Enter" && e.key !== " ") return;
        const p = e.target.closest("p[data-ver]");
        if (!p) return;
        e.preventDefault();
        selV.value = p.dataset.ver;
        goToVerse(p.dataset.ver);
      });

      form.addEventListener("submit", (e) => {
        e.preventDefault();
        clearTimeout(debounceTimer);
        runSearch({ fromSubmit: true });
      });
      qInput.addEventListener("input", () => {
        setClearVisible();
        scheduleSearch();
      });
      qInput.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          closeSearchPanel();
          qInput.blur();
        }
      });
      btnClear.addEventListener("click", () => {
        qInput.value = "";
        setClearVisible();
        closeSearchPanel();
        searchHint.textContent = "Référence ou texte (≥ 2 lettres).";
        qInput.focus();
      });
      btnCloseResults.addEventListener("click", closeSearchPanel);
      resultados.addEventListener("click", async (e) => {
        const btn = e.target.closest(".result-item");
        if (!btn) return;
        closeSearchPanel();
        await gotoRef(btn.dataset.livro, btn.dataset.cap, btn.dataset.ver);
      });

      window.addEventListener("hashchange", () => {
        applyHash();
      });

      // prioridade: hash URL > dernière position > Genèse 1
      if (applyHash()) return;

      const saved = readSavedPosition();
      if (saved?.livro || saved?.osis) {
        const book =
          books.find((b) => b.livro === saved.livro) ||
          books.find(
            (b) =>
              saved.osis &&
              b.livro_osis.toLowerCase() === String(saved.osis).toLowerCase()
          );
        if (book) {
          await gotoRef(book.livro, saved.cap || 1, saved.ver || undefined);
          return;
        }
      }

      await loadCapitulo(undefined, { scrollTop: false });
    } catch (e) {
      status.textContent = String(e.message || e);
      setReading(false);
    }
  }

  boot();
})();
