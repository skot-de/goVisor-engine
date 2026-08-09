/* #27 §5 — Anforderungskatalog: manueller Startkatalog (§5.2, Offener Punkt #1).
 *
 * Nicht aus TED-Metadaten ableitbar (Struktur-Studie: Zertifikate 0,1–0,4 %, Kriterien 52 %
 * nicht keyword-auffindbar). Erste Fassung daher als Anker-Set, das sich später aus dem
 * analysierten Unterlagen-Korpus erweitert (Typen ab 10 % Auftreten je Segment → Katalog, §5.2).
 *
 * Vier Typen (§5.3, bindend): binär · schwelle · sammlung · kennung.
 * Manche Anforderungen werden NICHT neu erfragt, sondern aus Stammdaten/Referenzen abgeleitet
 * (Akzeptanz #3 „einmal erfasst"): `quelleStammdaten`. */

import type { AnforderungsArt } from "@/lib/supabase/unternehmen";

export type CatalogItem = {
  id: string;
  label: string;
  art: AnforderungsArt;
  einheit?: string;              // schwelle: Anzeige-Einheit
  branchen: string[];            // ["*"] = alle, sonst CPV-Divisionen (2-stellig)
  ko?: boolean;                  // K.-o.-Kriterium (Ausschlussgrund/Pflicht) — Nein ermöglicht Abraten (#26)
  hinweis?: string;
  // Anforderung wird aus vorhandenen Daten befüllt statt neu erfragt:
  quelleStammdaten?: "umsatz" | "mitarbeiter" | "jahre" | "kmu" | "referenzen";
};

// CPV-Divisionen als grobe Branchenschlüssel (2-stellig).
const BAU = ["45"];                     // Bauleistungen
const IT = ["48", "72"];                // Software + IT-Dienste
const REINIGUNG_ENTSORGUNG = ["90"];    // Abwasser/Abfall/Reinigung/Umwelt
const INDUSTRIE_WARTUNG = ["50", "51"]; // Reparatur/Wartung/Installation

export const STARTKATALOG: CatalogItem[] = [
  // ── K.-o.-Kriterien / Eignungsgrundlagen (alle Branchen) ──
  { id: "ausschluss_123_124", label: "Keine Ausschlussgründe nach §§ 123/124 GWB", art: "binaer", branchen: ["*"], ko: true,
    hinweis: "Zwingende und fakultative Ausschlussgründe (u. a. Straftaten, Steuern, Sozialabgaben)." },
  { id: "sanktion_5k", label: "Keine Russland-Bezüge nach Art. 5k VO (EU) 833/2014", art: "binaer", branchen: ["*"], ko: true,
    hinweis: "Sanktions-Eigenerklärung — in nahezu jedem Verfahren gefordert." },
  { id: "tariftreue", label: "Tariftreue- / Mindestlohnerklärung abgebbar", art: "binaer", branchen: ["*"],
    hinweis: "Landesspezifische Tariftreuegesetze; Erklärung meist Pflicht." },

  // ── Wirtschaftliche Leistungsfähigkeit ──
  { id: "mindestumsatz", label: "Jahresumsatz (jüngstes Geschäftsjahr)", art: "schwelle", einheit: "€", branchen: ["*"],
    quelleStammdaten: "umsatz", hinweis: "Gegen geforderten Mindestumsatz geprüft — aus Stammdaten." },
  { id: "berufshaftpflicht", label: "Berufs-/Betriebshaftpflicht — Deckungssumme", art: "schwelle", einheit: "€", branchen: ["*"],
    hinweis: "Deckungssumme je Schadensfall; oft ≥ 1–3 Mio € gefordert." },

  // ── Technische Leistungsfähigkeit ──
  { id: "referenzen", label: "Vergleichbare Referenzen", art: "sammlung", branchen: ["*"], quelleStammdaten: "referenzen",
    hinweis: "Anzahl und Wert werden aus den erfassten Referenzen gerechnet (#26 §3.2a)." },
  { id: "mitarbeiterzahl", label: "Beschäftigte", art: "schwelle", einheit: "Personen", branchen: ["*"],
    quelleStammdaten: "mitarbeiter", hinweis: "Gegen geforderte Mindest-Mitarbeiterzahl — aus Stammdaten." },
  { id: "jahre_am_markt", label: "Jahre am Markt", art: "schwelle", einheit: "Jahre", branchen: ["*"],
    quelleStammdaten: "jahre", hinweis: "Aus dem Gründungsjahr berechnet." },

  // ── Präqualifikation / Register (Kennungen) ──
  { id: "praequalifikation", label: "Präqualifikation (PQ-VOB / PQ-VOL)", art: "kennung", branchen: ["*"],
    hinweis: "PQ-Nummer eintragen = vorhanden; leer = nein. Bei Bau meist PQ-VOB." },
  { id: "verbandsmitgliedschaft", label: "Verbandsmitgliedschaft", art: "kennung", branchen: ["*"],
    hinweis: "Fachverband/Innung — teils als Eignungsindiz gefordert." },

  // ── Zertifikate (branchenabhängig; als binär hier, Details in der Zertifikate-Sektion) ──
  { id: "iso_9001", label: "ISO 9001 (Qualitätsmanagement)", art: "binaer", branchen: ["*"] },
  { id: "iso_14001", label: "ISO 14001 (Umweltmanagement)", art: "binaer", branchen: [...BAU, ...REINIGUNG_ENTSORGUNG, ...INDUSTRIE_WARTUNG] },
  { id: "iso_27001", label: "ISO 27001 (Informationssicherheit)", art: "binaer", branchen: IT,
    hinweis: "Bei IT-Vergaben zunehmend K.-o." },
  { id: "scc", label: "SCC / SCP (Arbeitssicherheit)", art: "binaer", branchen: [...BAU, ...INDUSTRIE_WARTUNG, ...REINIGUNG_ENTSORGUNG] },
];

// CPV4-Codes der Branchenzuordnung → Menge der 2-stelligen Divisionen.
function divisions(cpv4: string[]): Set<string> {
  const s = new Set<string>();
  for (const c of cpv4) if (c && c.length >= 2) s.add(c.slice(0, 2));
  return s;
}

// Katalog für die aktive Branchenzuordnung (§5.1: je Segment ~20–30 Punkte).
// Ohne Branchenzuordnung → nur die „*"-Anker (Eignungsgrundlagen gelten immer).
export function catalogFor(cpv4: string[]): CatalogItem[] {
  const divs = divisions(cpv4);
  return STARTKATALOG.filter((it) => it.branchen.includes("*") || it.branchen.some((b) => divs.has(b)));
}

// Schlüssel für die Wirkung-Rechnung (§7.4). Aus-Stammdaten-Items zählen nicht als „offen",
// weil sie bereits anderswo erfasst sind.
export function requiredKeysFor(cpv4: string[]): string[] {
  return catalogFor(cpv4).filter((it) => !it.quelleStammdaten).map((it) => it.id);
}

export function catalogItem(id: string): CatalogItem | undefined {
  return STARTKATALOG.find((it) => it.id === id);
}
