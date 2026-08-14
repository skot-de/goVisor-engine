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

export const metadata: Metadata = {
  title: {
    default: `${copy.brand} — ${copy.tagline}`,
    template: `%s · ${copy.brand}`,
  },
  description: copy.metaDescription,
  robots: { index: true, follow: true },
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
      <body><SprachProvider><ProfilBanner />{children}</SprachProvider></body>
    </html>
  );
}
