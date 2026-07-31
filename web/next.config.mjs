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
    "connect-src 'self' https://*.supabase.co",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
  securityHeaders.push({ key: "Content-Security-Policy", value: csp });
}

const nextConfig = {
  reactStrictMode: true,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
