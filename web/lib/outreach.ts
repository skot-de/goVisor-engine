import { readFile } from "node:fs/promises";
import path from "node:path";

/* Vorberechnete Outreach-Landings (scripts/export_outreach.py), nach Token verschlüsselt.
 * Statisch + serverless-fähig — die Landing /t/<token> braucht kein Python im Deploy. */

/* Die Landing besteht aus BAUSTEINEN, nicht aus festen Feldern.
 *
 * Jeder Baustein hat sich im Generator selbst als belegt erwiesen, sonst wäre er nicht
 * hier. Die Oberfläche darf deshalb keinen bestimmten Baustein voraussetzen und keinen
 * durch einen Platzhalter ersetzen: fehlt einer, fehlt er, weil wir es für diese Firma
 * nicht wissen. Ein Ersatz an dieser Stelle wäre wieder das, was die alte Fassung tat.
 *
 * `art` je Zeile statt einer pauschalen Überschrift: nur Rahmen- und Wiederholungs-
 * verträge laufen im Wortsinn aus (gemessen 19,3 %); Bauleistungen werden fertig. */
export type Zahl = { wert: string | null; label: string };
export type Zeile = {
  titel: string; buyer: string; vol: string | null; ende: string | null;
  art: "auslauf" | "fertigstellung" | "unklar";
};
export type Baustein = {
  id: string; staerke: number; titel: string;
  zahlen?: Zahl[]; zeilen?: Zeile[]; namen?: string[];
  n_auslauf?: number; n_fertigstellung?: number;
  /** Was diese Zahlen NICHT abdecken. Pflichtfeld, kein Beiwerk. */
  grenze: string;
  /** Anschluss an einen Produktbereich (Strategie, Unternehmen, Planung). */
  bruecke: { produkt: string; text: string };
};
export type Landing = {
  id: string; name: string; stand: string;
  bausteine: Baustein[];
  belegt: string[];
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
