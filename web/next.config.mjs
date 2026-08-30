/** @type {import('next').NextConfig} */

// Security-Header (Härtung aus dem Audit): zweite XSS-Verteidigungslinie + Clickjacking-Schutz.
// Die harmlosen Header laufen immer; die CSP nur in Production, damit `next dev` (HMR/eval/ws)
// lokal nicht bricht.
const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },                               // Clickjacking
  { key: "X-Content-Type-Options", value: "nosniff" },                     // MIME-Sniffing
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
  { key: "X-DNS-Prefetch-Control", value: "off" },
];

// Der Ursprung unserer Supabase-Instanz, aus der oeffentlichen Variable abgeleitet.
// `new URL(...).origin` schneidet Pfad und Schraegstrich ab — die CSP will genau die Herkunft.
const supabaseOrigin = (() => {
  try {
    return new URL(process.env.NEXT_PUBLIC_SUPABASE_URL ?? "").origin;
  } catch {
    return "";
  }
})();

if (process.env.NODE_ENV === "production") {
  // Pragmatische CSP: Next braucht inline-Bootstrap-Scripts + React-Inline-Styles → 'unsafe-inline'
  // für script/style. Der eigentliche XSS-Schutz bleibt das durchgängige esc() (Input-Escaping);
  // die CSP begrenzt zusätzlich Exfiltration (connect-src) und verbietet Framing/Objekte/Fremd-base.
  // Strengeres nonce-basiertes script-src ist der Folgeschritt.
  const csp = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    // ⚠ NUR UNSER PROJEKT, nicht `*.supabase.co`. Der Platzhalter stand hier und erlaubte
    // jedes fremde Supabase-Projekt als Ziel — also genau den Weg, den eine XSS zum
    // Hinausschaffen von Daten braucht: ein Angreifer legt sich ein eigenes, kostenloses
    // Projekt an und schreibt dorthin. Der Ursprung kommt aus derselben Variable, aus der
    // der Client seine Verbindung baut; faellt sie aus, bleibt es beim Platzhalter, denn
    // eine CSP, die die eigene Datenbank aussperrt, macht die Anwendung unbenutzbar.
    `connect-src 'self' ${supabaseOrigin || "https://*.supabase.co"}`,
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
  securityHeaders.push({ key: "Content-Security-Policy", value: csp });
}

const nextConfig = {
  reactStrictMode: true,
  // Das Dev-Overlay legt sich unten links GENAU über den Konto-Button (gemessen: das
  // `nextjs-portal`-Element liegt bei elementFromPoint über `.planbadge`) und schluckt
  // jeden Klick darauf — samt Sprachumschalter im Menü dahinter. Nur eine Dev-Anzeige,
  // in Production ohnehin nicht vorhanden; sie kostet hier aber die Bedienbarkeit einer
  // echten Schaltfläche und damit jede Prüfung von Hand.
  devIndicators: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
