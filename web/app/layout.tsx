import type { Metadata } from "next";
import ProfilBanner from "./ProfilBanner";
import { Archivo, IBM_Plex_Mono } from "next/font/google";
import { copy } from "@/lib/copy";
import "./globals.css";
import { SprachProvider } from "@/lib/i18n";

const archivo = Archivo({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-archivo",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});

/* Woher die Seite sich selbst adressiert. Ohne diese Basis baut Next relative URLs in
 * Open-Graph-Karten ein, und relative URLs sind dort wertlos — jeder Abrufer sitzt woanders.
 * Aus der Umgebung, damit eine Vorschau-Bereitstellung nicht auf die Produktion zeigt. */
const SEITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://govisor.eu";

export const metadata: Metadata = {
  metadataBase: new URL(SEITE),
  title: {
    default: `${copy.brand} — ${copy.tagline}`,
    template: `%s · ${copy.brand}`,
  },
  description: copy.metaDescription,
  robots: { index: true, follow: true },
  // Eine Adresse ist die richtige. Ohne canonical zaehlen `?ref=…`, `//` und die
  // www-Variante als eigene Seiten und teilen sich auf, was eine haette sein sollen.
  alternates: { canonical: "/" },
  // ⚠ KEIN `alternates.languages`, UND DAS IST KEIN VERSAEUMNIS.
  //
  // Der naheliegende Grund waere: die Sprache liegt im `localStorage`, es gibt keine
  // sprachspezifischen URLs. Das stimmt, ist aber nur die halbe Wahrheit — und die
  // gefaehrlichere Haelfte kam erst beim Nachmessen heraus (2026-08-30):
  //
  //     Landing.tsx   35 deutsche Textstellen · 0 im Katalog · 0 t()-Aufrufe
  //     /start         3                      · 0            · 0
  //     /login         2                      · 0            · 0
  //
  // Die OEFFENTLICHEN Seiten sind gar nicht uebersetzbar. Ihr Text steht fest verdrahtet
  // im JSX; die Sprachumschaltung wirkt nur HINTER der Anmeldung, wo die Kataloge greifen.
  // Es gibt also keine englische oder franzoesische Startseite, auf die ein `hreflang`
  // zeigen koennte.
  //
  // Wer hier Sprach-Routen anlegt, ohne vorher die Texte uebersetzbar zu machen, liefert
  // unter `/en` und `/fr` denselben deutschen Inhalt aus. `hreflang` waere dann eine
  // Falschangabe, und drei URLs mit gleichem Text sind fuer die Auffindbarkeit schlechter
  // als eine saubere. Erst die Texte, dann die Routen.
  //
  // Sven am 2026-08-30, als die Messung vorlag: vorerst nur Deutsch.
  // `tests/test_auffindbarkeit.py` meldet sich, sobald der Grund entfaellt.
  openGraph: {
    type: "website",
    siteName: copy.brand,
    locale: "de_DE",
    url: SEITE,
    title: `${copy.brand} — ${copy.tagline}`,
    description: copy.metaDescription,
    images: [{ url: "/govisor-wordmark.png", width: 1200, height: 630, alt: copy.brand }],
  },
  twitter: {
    card: "summary_large_image",
    title: `${copy.brand} — ${copy.tagline}`,
    description: copy.metaDescription,
    images: ["/govisor-wordmark.png"],
  },
};

/* Was die Seite ueber sich selbst SAGT, in maschinenlesbarer Form.
 *
 * Titel und Beschreibung muss ein Abrufer aus dem Fliesstext deuten; hier steht es
 * ausdruecklich: was das Ding ist, wer es betreibt, wen es adressiert, was es kostet. Das
 * ist das einzige Signal auf der Seite, das sich ausschliesslich an Maschinen richtet.
 *
 * ⚠ NUR BELEGBARES. Keine Bewertungen, keine Nutzerzahlen, keine erfundenen Auszeichnungen —
 * strukturierte Daten sind eine Behauptung mit Anspruch auf Genauigkeit, und was hier nicht
 * stimmt, steht spaeter woertlich in fremden Antworten. */
const strukturdaten = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": `${SEITE}/#organisation`,
      name: copy.brand,
      url: SEITE,
      logo: `${SEITE}/govisor-wordmark.png`,
      areaServed: "EU",
    },
    {
      "@type": "WebSite",
      "@id": `${SEITE}/#website`,
      url: SEITE,
      name: copy.brand,
      inLanguage: ["de", "en", "fr"],
      publisher: { "@id": `${SEITE}/#organisation` },
    },
    {
      "@type": "SoftwareApplication",
      name: copy.brand,
      applicationCategory: "BusinessApplication",
      operatingSystem: "Web",
      url: SEITE,
      description: copy.metaDescription,
      inLanguage: ["de", "en", "fr"],
      publisher: { "@id": `${SEITE}/#organisation` },
      // Die kostenfreie Stufe ist belegt: „Dauerhaft kostenfrei, nicht vierzehn Tage"
      // steht so auf der Startseite. Preise der bezahlten Stufen stehen hier NICHT —
      // sie sind noch nicht entschieden (s. docs/pricing-modell.md).
      offers: { "@type": "Offer", price: "0", priceCurrency: "EUR" },
    },
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="de" className={`${archivo.variable} ${plexMono.variable}`}>
      {/* `lang` bleibt hier "de": das ist die Server-Ausgabe. Der SprachProvider setzt es
          nach dem ersten Rendern auf die gewaehlte Sprache um — so gibt es keinen
          Hydration-Konflikt zwischen Server- und Client-Markup. */}
      {/* Der Kundensicht-Hinweis haengt im Layout und damit auf JEDER Seite. Haenge ihn
          nie in eine einzelne Seite um — genau die Seite, die man dann vergisst, ist die,
          auf der man den Testzustand fuer echt haelt. */}
      <head>
        {/* Die Strukturdaten gehoeren in die Server-Ausgabe. Wuerden sie erst im Client
            entstehen, saehe sie kein Abrufer, der kein JavaScript ausfuehrt — und das sind
            die meisten. `JSON.stringify` statt einer Zeichenkette von Hand: so kann kein
            Anfuehrungszeichen aus `copy` das Skript aufbrechen. */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(strukturdaten) }}
        />
      </head>
      <body><SprachProvider><ProfilBanner />{children}</SprachProvider></body>
    </html>
  );
}
