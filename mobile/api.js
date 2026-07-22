/**
 * Camada SQLite nativa (Android / Capacitor).
 * Queries alinhadas com server.py.
 */
import {
  CapacitorSQLite,
  SQLiteConnection,
} from "@capacitor-community/sqlite";

const TOKEN_RE = /[\wàâäéèêëïîôùûüçœæ'-]+/gi;

let dbConn = null;
let sqliteReady = null;

async function getDb() {
  if (dbConn) return dbConn;
  if (sqliteReady) return sqliteReady;

  sqliteReady = (async () => {
    const sqlite = new SQLiteConnection(CapacitorSQLite);
    try {
      const cons = await sqlite.checkConnectionsConsistency();
      const isConn = (await sqlite.isConnection("biblia", false)).result;
      if (cons.result && isConn) {
        dbConn = await sqlite.retrieveConnection("biblia", false);
      } else {
        await sqlite.copyFromAssets(true);
        dbConn = await sqlite.createConnection(
          "biblia",
          false,
          "no-encryption",
          1,
          false
        );
      }
    } catch {
      await sqlite.copyFromAssets(true);
      dbConn = await sqlite.createConnection(
        "biblia",
        false,
        "no-encryption",
        1,
        false
      );
    }
    await dbConn.open();
    return dbConn;
  })();

  return sqliteReady;
}

function rows(res) {
  return res?.values || [];
}

export async function livros() {
  const db = await getDb();
  const res = await db.query(`
    SELECT livro, livro_osis, testamento,
           COUNT(*) AS n_versiculos,
           MAX(capitulo) AS n_capitulos
    FROM versiculos
    GROUP BY livro, livro_osis, testamento
    ORDER BY
      CASE testamento WHEN 'AT' THEN 0 ELSE 1 END,
      MIN(id)
  `);
  return rows(res);
}

export async function capitulo(livro, cap) {
  const db = await getDb();
  const res = await db.query(
    `
    SELECT id, testamento, livro, livro_osis, capitulo, versiculo, texto
    FROM versiculos
    WHERE (livro = ? OR livro_osis = ?) AND capitulo = ?
    ORDER BY versiculo
    `,
    [livro, livro, Number(cap)]
  );
  const verses = rows(res);
  if (!verses.length) throw new Error("capítulo não encontrado");
  return {
    livro: verses[0].livro,
    livro_osis: verses[0].livro_osis,
    testamento: verses[0].testamento,
    capitulo: Number(cap),
    versiculos: verses,
  };
}

export async function buscar(q, limit = 50) {
  const db = await getDb();
  const tokens = (q.match(TOKEN_RE) || []).slice(0, 8);
  let list = [];

  if (tokens.length) {
    const ftsQ = tokens.map((t) => `"${t.replace(/"/g, "")}"`).join(" ");
    try {
      const res = await db.query(
        `
        SELECT v.id, v.testamento, v.livro, v.livro_osis,
               v.capitulo, v.versiculo, v.texto
        FROM versiculos_fts f
        JOIN versiculos v ON v.id = f.rowid
        WHERE versiculos_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        `,
        [ftsQ, limit]
      );
      list = rows(res);
    } catch {
      list = [];
    }
  }

  if (!list.length) {
    const res = await db.query(
      `
      SELECT id, testamento, livro, livro_osis, capitulo, versiculo, texto
      FROM versiculos
      WHERE texto LIKE ?
      LIMIT ?
      `,
      [`%${q}%`, limit]
    );
    list = rows(res);
  }

  return { q, count: list.length, results: list };
}
