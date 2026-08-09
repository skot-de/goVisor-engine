import { readFile } from "node:fs/promises";
import path from "node:path";

/* Serverseitiger Lieferanten-Index (Onboarding-Matching). Einmal geladen, gecacht. */

export type Member = { name: string; conf: "belegt" | "unsicher"; method: string; wins: number };
export type Supplier = {
  id: string; name: string; aliases: string[]; wins: number;
  buyers: number | null; seit: number | null;
  fields: { cpv4: string; label: string | null; wins: number }[];
  fields6?: { cpv6: string; wins: number }[];   // CPV-6-Volltreffer-Menge (nur Codes, fürs Matching)
  regions: string[]; regionTyp?: 'regional'|'teilregional'|'bundesweit';
  volMedian: number | null;
  topBuyers?: { name: string; wins: number; seit: number; bis: number }[];
  topShare?: number | null;   // Anteil des größten Auftraggebers (Klumpenrisiko)
  // NUR SERVERSEITIG — nie ins Suchergebnis, sonst sind die Kontaktdomains aller
  // Firmen über die Suche abgreifbar. Auswertung ausschließlich in /api/entity-verify.
  domain?: string | null; domainBelege?: number;
  // sha256(Adresse), auf 16 Hex-Zeichen gekürzt — Klartext liegt nirgends.
  mailHashes?: string[];
  members: Member[];
};

let CACHE: Supplier[] | null = null;

export async function loadSuppliers(): Promise<Supplier[]> {
  if (CACHE) return CACHE;
  try {
    const raw = await readFile(path.join(process.cwd(), "data", "suppliers.json"), "utf-8");
    CACHE = JSON.parse(raw) as Supplier[];
  } catch {
    CACHE = [];
  }
  return CACHE;
}
