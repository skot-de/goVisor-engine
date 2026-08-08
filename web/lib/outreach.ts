import { readFile } from "node:fs/promises";
import path from "node:path";

/* Vorberechnete Outreach-Landings (scripts/export_outreach.py), nach Token verschlüsselt.
 * Statisch + serverless-fähig — die Landing /t/<token> braucht kein Python im Deploy. */

export type Contract = { titel: string; buyer: string; vol: string | null; geschaetzt?: boolean; ende: string | null; soon?: boolean };
export type Landing = {
  id: string; name: string; stand: string;
  finding: { headline: string; em: string | null };
  kpi: { wins36: number; volSum: string | null; aus18N: number; aus18Vol: string | null };
  vertraege: Contract[];
  wettbewerber: { name: string; wins: number; vertraege: Contract[] } | null;
};

let CACHE: Record<string, Landing> | null = null;

export async function loadLanding(token: string): Promise<Landing | null> {
  if (!CACHE) {
    try {
      CACHE = JSON.parse(await readFile(path.join(process.cwd(), "data", "outreach.json"), "utf-8"));
    } catch { CACHE = {}; }
  }
  return CACHE?.[token] ?? null;
}
