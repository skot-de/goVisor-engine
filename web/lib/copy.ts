import { tk } from "@/lib/i18n";

/**
 * Zentrale Textquelle (Übergabenotiz §10).
 * Sichtbare Beschriftungen gehören hierher; interne Schlüssel bleiben stabil.
 * So kostet eine Umbenennung eine Zeile statt vier Fundstellen.
 *
 * Ton: der Markenkern (§1) "Lieber unbekannt zeigen als falsch". Nüchtern,
 * präzise, keine Superlative. Wir verkaufen Ehrlichkeit — also klingen wir so.
 *
 * Sprache: die Felder sind GETTER, keine Konstanten. Ein Modul-Objekt wird beim Import
 * ausgewertet — mit direkten `tk(...)`-Aufrufen stünde hier für immer die Sprache des
 * ersten Ladevorgangs. Als Getter übersetzt jeder Zugriff neu, und die Aufrufstellen
 * (`copy.tagline`) bleiben unverändert. `brand` ist ein Eigenname und wird nie übersetzt.
 *
 * Fußnote: `app/layout.tsx` liest das Objekt für die Metadaten — die rendert Next auf dem
 * Server. Dort ist die Sprache immer Deutsch (die Meta-Tags sind statisch, das ist richtig
 * so), und `tk` stammt aus einem `"use client"`-Modul: serverseitig ist es nur eine
 * Client-Referenz und darf nicht AUFGERUFEN werden. Deshalb der `ueb`-Wächter unten —
 * ohne ihn stirbt der Metadaten-Aufbau beim Build. Der Fallback ist ohnehin der deutsche
 * Text, es geht also nichts verloren.
 */
const ueb = (s: string) => (typeof window === "undefined" ? s : tk(s));

export const copy = {
  brand: "goVisor",
  get tagline() { return ueb("Öffentliche Ausschreibungen, ehrlich aufbereitet"); },
  get metaDescription() {
    return ueb(
      "goVisor macht öffentliche Ausschreibungen (TED) für Bieter nutzbar — jeder Wert mit " +
      "seiner Herkunft. Gemessenes ist gemessen, Geschätztes ist markiert, Unbekanntes bleibt sichtbar.");
  },

  // Markenkern — steht wörtlich in der Übergabenotiz §1
  get creed() { return ueb("Lieber unbekannt zeigen als falsch."); },

  nav: {
    get features() { return ueb("Wie es funktioniert"); },
    get pricing() { return ueb("Preise"); },
    get login() { return ueb("Anmelden"); },
    get signup() { return ueb("Kostenlos starten"); },
  },

  hero: {
    get kicker() { return ueb("Lead-Engine für öffentliche Vergaben"); },
    // Die Antwort auf „warum sollte ich das benutzen" (Übergabenotiz §12)
    get headline() { return ueb("Jede Ausschreibung, die zu euch passt, und die Wahrheit darüber, was drinsteht."); },
    get sub() {
      return ueb(
        "Öffentliche Vergaben stehen alle in TED. Vollständig, und praktisch unbenutzbar: " +
        "roh, dubliert, ohne Kontext. goVisor bereitet sie auf — und markiert jeden Wert mit " +
        "seiner Herkunft. Gemessenes ist gemessen. Geschätztes trägt einen Punkt. Was fehlt, " +
        "bleibt sichtbar leer, statt plausibel erfunden zu werden.");
    },
    get ctaPrimary() { return ueb("Kostenlos starten"); },
    get ctaSecondary() { return ueb("Wie es funktioniert"); },
    get trust() { return ueb("Ohne Kreditkarte. Lead-Liste, Suche und Filter dauerhaft frei."); },
  },

  footer: {
    get tagline() { return ueb("Öffentliche Ausschreibungen, ehrlich aufbereitet."); },
    get impressum() { return ueb("Impressum"); },
    get datenschutz() { return ueb("Datenschutz"); },
    get pricing() { return ueb("Preise"); },
    get rights() { return ueb("Alle Rechte vorbehalten."); },
  },
} as const;

/** Herkunfts-Kategorien (§2). Interne Schlüssel — stabil, nie im UI. */
export type Herkunft = "echt" | "schaetz" | "unsicher" | "unbekannt" | "na";
