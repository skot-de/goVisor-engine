import type { MetadataRoute } from "next";

/* Welche Seiten es gibt — die Liste, die `robots.txt` sonst vergeblich sucht.
 *
 * ⚠ NUR OEFFENTLICHE, INHALTSTRAGENDE SEITEN. Alles hinter dem Anmelde-Tor gehoert nicht
 * hierher: eine Sitemap, die auf `/leads` zeigt, schickt jeden Abrufer auf die
 * Anmeldemaske und lehrt ihn, dass hinter unseren Adressen nichts steht. `/t/` steht
 * ohnehin in der Sperrliste der robots.txt — token-adressierte Vertriebsseiten sind fuer
 * ihren Empfaenger da, nicht fuer einen Index.
 *
 * Bleibt wenig: die Startseite, der Einstieg und die Anmeldung. Das ist ehrlich — mehr
 * Oeffentliches gibt es zurzeit nicht. (Ein Impressum stand hier zuerst im Text, es gibt
 * aber nur die Route `/api/impressum`, keine Seite — eine Sitemap, die auf eine nicht
 * existierende Adresse zeigt, ist schlechter als eine kurze.)
 */
const SEITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://govisor.eu";

export default function sitemap(): MetadataRoute.Sitemap {
  const jetzt = new Date();
  return [
    { url: `${SEITE}/`, lastModified: jetzt, changeFrequency: "daily", priority: 1 },
    { url: `${SEITE}/start`, lastModified: jetzt, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SEITE}/login`, lastModified: jetzt, changeFrequency: "yearly", priority: 0.3 },
  ];
}
