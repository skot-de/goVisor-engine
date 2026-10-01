import type { MetadataRoute } from "next";
import { indexierbareSlugs } from "@/lib/oeffentlich";

/* Welche Seiten es gibt — die Liste, die `robots.txt` sonst vergeblich sucht.
 *
 * ⚠ NUR OEFFENTLICHE, INHALTSTRAGENDE SEITEN. Alles hinter dem Anmelde-Tor gehoert nicht
 * hierher: eine Sitemap, die auf `/leads` zeigt, schickt jeden Abrufer auf die
 * Anmeldemaske und lehrt ihn, dass hinter unseren Adressen nichts steht. `/t/` steht
 * ohnehin in der Sperrliste der robots.txt — token-adressierte Vertriebsseiten sind fuer
 * ihren Empfaenger da, nicht fuer einen Index.
 *
 * Die Ausschreibungs-One-Pager (Ticket #17) kommen dazu, sobald sie freigeschaltet sind —
 * und auch dann NUR die indexierbaren (seitenspezifische Exklusivschicht, §11). Solange der
 * Schalter aus ist oder das Export-Feld `exklusivSchicht` fehlt, liefert `indexierbareSlugs()`
 * eine leere Liste: eine Sitemap, die auf noindex-Seiten zeigt, waere schlechter als eine
 * kurze. Darum ist diese Funktion async.
 */
const SEITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://govisor.eu";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const jetzt = new Date();
  const basis: MetadataRoute.Sitemap = [
    { url: `${SEITE}/`, lastModified: jetzt, changeFrequency: "daily", priority: 1 },
    { url: `${SEITE}/start`, lastModified: jetzt, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SEITE}/login`, lastModified: jetzt, changeFrequency: "yearly", priority: 0.3 },
  ];
  const ausschreibungen: MetadataRoute.Sitemap = (await indexierbareSlugs()).map((slug) => ({
    url: `${SEITE}/ausschreibung/${slug}`,
    lastModified: jetzt,
    changeFrequency: "daily",
    priority: 0.7,
  }));
  return [...basis, ...ausschreibungen];
}
