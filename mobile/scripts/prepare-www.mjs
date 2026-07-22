/**
 * Copia biblia.db + databases.json para public/assets/databases
 * (requerido por @capacitor-community/sqlite copyFromAssets).
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repo = path.resolve(root, "..");
const dbSrc = path.join(repo, "data", "biblia.db");
const destDir = path.join(root, "public", "assets", "databases");

if (!fs.existsSync(dbSrc)) {
  console.error("Falta data/biblia.db — corre: python scripts/migrate.py --fixture");
  process.exit(1);
}

fs.mkdirSync(destDir, { recursive: true });
fs.copyFileSync(dbSrc, path.join(destDir, "biblia.db"));
fs.writeFileSync(
  path.join(destDir, "databases.json"),
  JSON.stringify({ databaseList: ["biblia.db"] }, null, 2) + "\n"
);
console.log("OK: public/assets/databases/biblia.db");
