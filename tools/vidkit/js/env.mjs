// .env loading shared by the vidkit scripts. Keys are read from files and NEVER printed.
import { readFileSync, existsSync } from "node:fs";

/** Parse KEY=VALUE lines (quotes stripped, # lines ignored). Missing file -> {}. */
export function parseEnv(file) {
  if (!existsSync(file)) return {};
  return Object.fromEntries(
    readFileSync(file, "utf8").split(/\r?\n/)
      .filter((l) => /^[A-Z0-9_]+=/.test(l))
      .map((l) => {
        const i = l.indexOf("=");
        return [l.slice(0, i), l.slice(i + 1).trim().replace(/^["']|["']$/g, "")];
      }),
  );
}

/** Later files win. Falls back to process.env for anything the files do not define. */
export function loadEnv(...files) {
  return { ...process.env, ...Object.assign({}, ...files.map(parseEnv)) };
}

/** Throw naming the missing variables, never their values. */
export function requireKeys(env, ...names) {
  const missing = names.filter((n) => !env[n]);
  if (missing.length) throw new Error(`missing in env: ${missing.join(", ")}`);
}
