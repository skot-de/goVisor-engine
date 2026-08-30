import type { MetadataRoute } from "next";

/* Was Suchmaschinen sehen duerfen.
 *
 * Bis zum 2026-08-30 gab es diese Datei nicht — ohne robots.txt ist alles erlaubt, was
 * erreichbar ist. Solange die Baustellen-Sperre laeuft, faellt das nicht auf: jeder Crawler
 * bekommt die schwarze Seite mit `x-robots-tag: noindex`. Mit dem Go-live faellt diese
 * Schicht weg, und dann zaehlt, was hier steht.
 *
 * Zwei Bereiche bleiben draussen:
 *   /t/   die token-adressierten Vertriebsseiten. Oeffentlich fuer den Empfaenger, nicht
 *         fuer den Index — sie zeigen eine firmenspezifische Auswertung und wann wir die
 *         Firma angeschrieben haben (s. `app/t/[token]/page.tsx`).
 *   /api/ Datenendpunkte. Nichts davon gehoert in ein Suchergebnis, und ein Crawler, der
 *         `/api/entity-search` durchprobiert, kostet nur Rechenzeit.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/t/", "/api/"] }],
    // Ohne diesen Verweis muss ein Abrufer die Seiten erraten. Mit ihm steht die Liste da.
    sitemap: `${process.env.NEXT_PUBLIC_SITE_URL ?? "https://govisor.eu"}/sitemap.xml`,
  };
}
