# Security-Review goVisor Web (2026-07-28)

Pflicht-Gate vor breiterem Launch. Stand nach der CH/AT-Quellen-Integration (externe Daten
im Frontend).

## ✅ Behoben
- **Stored-XSS im Lead-Renderer** (`f406c44`). Der Explorer rendert Lead-Daten via
  `dangerouslySetInnerHTML` — externe Werte (TED/simap/DÖE: Titel, Käufer, Gewinner-Namen,
  Beschreibung, Rechtsmittel, Los-Titel, Kommentare) wurden roh eingesetzt → ein Käufer/Titel
  mit `<img onerror>` hätte im Browser anderer Nutzer ausgeführt. Fix: `esc()` an ALLEN
  Datenwert-Einsetzungen (Value-Wrapper, Such-Highlight, direkte Felder, title-Attribute).

## ✅ Sauber
- **Secret-Key nicht im Client-Bundle**: `SUPABASE_SECRET_KEY` nur in `lib/supabase/admin.ts`
  mit `import "server-only"`; alle Importeure sind API-Routes (server). Kein NEXT_PUBLIC-Verwechsler.
- **RLS**: alle 8 User-Tabellen (profiles/watchlist/alert_settings/contracts/charges/interactions/
  calendar_feed/data_export) mit `enable row level security` + Policies. Analyse-Tabellen bewusst ohne
  Policy (Paywall serverseitig).

## 🔴 Offen — VOR Monetarisierung zwingend
- **Paywall ist rein kosmetisch (§9-Blur).** Für Free-Nutzer werden die **echten** Premium-Werte
  (Markt-Konzentration, Retention, Gewinner-Anteile, Bieterzahlen, Käufer-Mix) ins DOM gesendet und
  nur per CSS `class="blur"` verwischt → per DevTools „Element untersuchen" **im Klartext lesbar**.
  Betroffen: `explorerCore.js` (blur/blur-num-Spans), `/api/leads` + `/api/markt` liefern das volle
  JSON an alle.
  - **Kein Datenleck von Secrets** (Aggregate aus öffentlichen Vergabedaten), aber **Monetarisierungs-
    Bypass** — der Pro-Wert ist gratis abgreifbar.
  - **Fix:** server-seitige, tier-abhängige Redaktion in den Daten-Routes — für Free-Nutzer die
    Premium-Felder VOR dem Senden entfernen (nicht clientseitig blurren). Braucht die echte
    Subscription-Tier-Info (aus Supabase-Session), die es erst mit echtem Billing gibt.
  - **Dringlichkeit:** aktuell **null** (Billing ist Stub, keine zahlenden Nutzer) — wird kritisch,
    sobald Pro live geht. Nicht vor Launch der Bezahlschranke vergessen.

## 🟡 Bekannt / akzeptiert
- **npm-Vulns**: kritische Next.js-SSRF/RCE gepatcht (15.5.22). 3 verbleibende „high" (PostCSS/sharp)
  sind Build-Tooling-transitiv, kein Runtime-Risiko (kein Verarbeiten fremder CSS/Bilder).
