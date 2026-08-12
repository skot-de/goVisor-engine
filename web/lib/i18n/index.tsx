"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import de from "./messages/de.json";
import en from "./messages/en.json";
import fr from "./messages/fr.json";
import flatEn from "./messages/flat.en.json";
import flatFr from "./messages/flat.fr.json";

/* Sprachebene der Oberfläche.
 *
 * **Warum ohne Bibliothek.** `next-intl` & Co. bringen eine eigene Locale-Middleware und
 * ein Sprach-Segment in der URL mit. Beides kollidiert hier: `middleware.ts` ist ein
 * fail-closed Blackout mit Vorschau-Bypass, und eine zweite Middleware davor oder dahinter
 * zu hängen ist genau die Art Änderung, bei der aus „öffentlich schwarz" versehentlich
 * „öffentlich sichtbar" wird. Die Sprache ist deshalb eine NUTZEREINSTELLUNG, kein
 * URL-Segment — kein Routing berührt, kein Deployment-Risiko.
 *
 * **Zwei unabhängige Achsen.** Diese hier ist die Sprache der OBERFLÄCHE. Die Sprache des
 * DOKUMENTS (eine belgische Ausschreibung liegt auf FR und NL vor) ist eine andere Wahl und
 * sitzt am Lead — s. `sprachen`/`sprachfassungen` im Lead-JSON.
 *
 * **Zwei Schlüsselarten, mit Absicht.**
 *  1. Punkt-Schlüssel (`nav.akquise`) für das Gerüst — Navigation, Sprachnamen, alles, was
 *     strukturiert benannt gehört.
 *  2. DER DEUTSCHE SATZ SELBST als Schlüssel für den Fließtext der Oberfläche. Gemessen sind
 *     das 1.229 Texte; für jeden einen Schlüssel zu erfinden brächte zwei Fehlerquellen mit,
 *     die es sonst nicht gäbe: der Schlüssel driftet vom Text ab, und ein Tippfehler zeigt
 *     dem Nutzer `detail.luecke.buergschaft` statt eines Satzes. Mit dem deutschen Satz als
 *     Schlüssel ist die deutsche Fassung IMMER korrekt — auch ganz ohne Katalog — und eine
 *     fehlende Übersetzung fällt auf Deutsch zurück, nie auf Kauderwelsch.
 *
 * **Fallback ist Deutsch, nicht der Schlüssel.** Fehlt eine Übersetzung, erscheint der
 * deutsche Text — nicht `nav.akquise`. Ein unübersetztes Wort ist unschön, ein technischer
 * Schlüssel ist kaputt.
 */

export const SPRACHEN = ["de", "en", "fr"] as const;
export type Sprache = (typeof SPRACHEN)[number];

const KATALOG: Record<Sprache, unknown> = { de, en, fr };
// Flachkataloge: deutscher Satz → Übersetzung. `de` fehlt bewusst — dort IST der
// Schlüssel die Antwort, ein Identitäts-Katalog wäre nur Pflegeaufwand.
const FLACH: Partial<Record<Sprache, Record<string, string>>> = { en: flatEn, fr: flatFr };
const SPEICHER = "gv_lang";

function pfad(obj: unknown, key: string): string | undefined {
  const wert = key.split(".").reduce<unknown>(
    (o, k) => (o && typeof o === "object" ? (o as Record<string, unknown>)[k] : undefined), obj);
  return typeof wert === "string" ? wert : undefined;
}

/** Mehrzeilige Vorlagen-Literale tragen ihre Einrückung mit; als Schlüssel muss der
 *  Weißraum vereinheitlicht sein, sonst bricht jede Neuformatierung die Übersetzung. */
export function schluessel(s: string): string {
  return s.replace(/\s+/g, " ").trim();
}

/** Der eigentliche Nachschlag — ohne React, damit ihn auch `explorerCore` benutzen kann. */
export function uebersetze(key: string, lang: Sprache,
                           vars?: Record<string, string | number>): string {
  const flach = FLACH[lang]?.[schluessel(key)];
  const text = flach ?? pfad(KATALOG[lang], key) ?? pfad(KATALOG.de, key) ?? key;
  return vars
    ? text.replace(/\{(\w+)\}/g, (_m, n) => String(vars[n] ?? `{${n}}`))
    : text;
}

/* ── Brücke zu `explorerCore` ──────────────────────────────────────────────────
 * Die Prototyp-Renderer sind pures JS ohne React-Kontext. Sie können keinen Hook
 * aufrufen, brauchen die Sprache aber genauso. Deshalb hält das Modul sie zusätzlich
 * als Modul-Zustand; der Provider schreibt sie bei jedem Wechsel hinein.
 * Bewusst kein zweiter Speicher: `localStorage` bleibt die einzige Quelle, das hier
 * ist nur die Weitergabe innerhalb eines Ladevorgangs. */
let aktuelleSprache: Sprache = "de";
export function setzeKernSprache(s: Sprache) { aktuelleSprache = s; }
/** `t()` für Nicht-React-Module (explorerCore). Gleiche Semantik, gleiche Kataloge. */
export function tk(key: string, vars?: Record<string, string | number>): string {
  return uebersetze(key, aktuelleSprache, vars);
}

type Ctx = { lang: Sprache; setLang: (s: Sprache) => void; t: (k: string, v?: Record<string, string | number>) => string };
const SprachKontext = createContext<Ctx | null>(null);

export function SprachProvider({ children }: { children: React.ReactNode }) {
  // Start IMMER auf Deutsch, auch wenn der Browser etwas anderes meldet: sonst rendert der
  // Server Deutsch und der Client sofort etwas anderes — React meldet das als Hydration-
  // Fehler. Die gespeicherte Wahl greift erst nach dem ersten Rendern.
  const [lang, setLangState] = useState<Sprache>("de");

  useEffect(() => {
    const gespeichert = window.localStorage.getItem(SPEICHER);
    if (gespeichert && (SPRACHEN as readonly string[]).includes(gespeichert)) {
      setLangState(gespeichert as Sprache);
    }
  }, []);

  useEffect(() => {
    // Das `lang`-Attribut ist kein Schmuck: Screenreader wählen danach die Aussprache,
    // und der Browser die Silbentrennung.
    document.documentElement.lang = lang;
    setzeKernSprache(lang);            // Prototyp-Renderer mitziehen
  }, [lang]);

  const setLang = useCallback((s: Sprache) => {
    setzeKernSprache(s);               // VOR dem Rendern setzen, sonst rendert der
    setLangState(s);                   // Detail-Körper noch einmal in der Altsprache
    try { window.localStorage.setItem(SPEICHER, s); } catch { /* privater Modus */ }
  }, []);

  const t = useCallback((key: string, vars?: Record<string, string | number>) =>
    uebersetze(key, lang, vars), [lang]);

  return <SprachKontext.Provider value={{ lang, setLang, t }}>{children}</SprachKontext.Provider>;
}

export function useSprache(): Ctx {
  const ctx = useContext(SprachKontext);
  // Ohne Provider (z. B. eine Komponente im Test) still auf Deutsch arbeiten statt zu
  // werfen — eine fehlende Übersetzung darf keine Seite abstürzen lassen.
  if (!ctx) return { lang: "de", setLang: () => {}, t: (k, v) => uebersetze(k, "de", v) };
  return ctx;
}

/** Sprachname in der aktuellen Oberflächensprache („fr" → „Französisch"). */
export function sprachName(code: string, t: Ctx["t"]): string {
  const name = t(`sprache.${code}`);
  return name === `sprache.${code}` ? code.toUpperCase() : name;
}
