/**
 * Zentrale Textquelle (Übergabenotiz §10).
 * Sichtbare Beschriftungen gehören hierher; interne Schlüssel bleiben stabil.
 * So kostet eine Umbenennung eine Zeile statt vier Fundstellen.
 *
 * Ton: der Markenkern (§1) "Lieber unbekannt zeigen als falsch". Nüchtern,
 * präzise, keine Superlative. Wir verkaufen Ehrlichkeit — also klingen wir so.
 */
export const copy = {
  brand: "goVisor",
  tagline: "Öffentliche Ausschreibungen, ehrlich aufbereitet",
  metaDescription:
    "goVisor macht öffentliche Ausschreibungen (TED) für Bieter nutzbar — jeder Wert mit " +
    "seiner Herkunft. Gemessenes ist gemessen, Geschätztes ist markiert, Unbekanntes bleibt sichtbar.",

  // Markenkern — steht wörtlich in der Übergabenotiz §1
  creed: "Lieber unbekannt zeigen als falsch.",

  nav: {
    features: "Wie es funktioniert",
    pricing: "Preise",
    login: "Anmelden",
    signup: "Kostenlos starten",
  },

  hero: {
    kicker: "Lead-Engine für öffentliche Vergaben",
    // Die Antwort auf „warum sollte ich das benutzen" (Übergabenotiz §12)
    headline: "Jede Ausschreibung, die zu euch passt — und die Wahrheit darüber, was drinsteht.",
    sub:
      "Öffentliche Vergaben stehen alle in TED. Vollständig, und praktisch unbenutzbar: " +
      "roh, dubliert, ohne Kontext. goVisor bereitet sie auf — und markiert jeden Wert mit " +
      "seiner Herkunft. Gemessenes ist gemessen. Geschätztes trägt einen Punkt. Was fehlt, " +
      "bleibt sichtbar leer, statt plausibel erfunden zu werden.",
    ctaPrimary: "Kostenlos starten",
    ctaSecondary: "Wie es funktioniert",
    trust: "Ohne Kreditkarte. Lead-Liste, Suche und Filter dauerhaft frei.",
  },

  footer: {
    tagline: "Öffentliche Ausschreibungen, ehrlich aufbereitet.",
    impressum: "Impressum",
    datenschutz: "Datenschutz",
    pricing: "Preise",
    rights: "Alle Rechte vorbehalten.",
  },
} as const;

/** Herkunfts-Kategorien (§2). Interne Schlüssel — stabil, nie im UI. */
export type Herkunft = "echt" | "schaetz" | "unsicher" | "unbekannt" | "na";
