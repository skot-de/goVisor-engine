# goVisor — Implementierungsstand der Plattform

**Stand:** 2026-07-27
**Perspektive:** Anbieter-Sicht (Vergabestellen-Seite = Phase 3–4)
**Reifegrad:** Lokal-first im Prototyp gebaut und im Browser verifiziert — noch **nicht deployed** und **noch nicht an echten Nutzern getestet**.

> Prinzip: „fertig" heißt gebaut + gegengeprüft, nicht „müsste funktionieren". Gemessen, nicht behauptet.

**Bilanz:** 12 Features fertig & verifiziert · 2 teilweise (#15, #16) · 3 offene Blöcke bis Launch.

---

## Schicht 1 — Datenkern (Gold-Layer) · vollständig

Medallion Bronze→Silber→Gold über **1.832.998 DE-Notices, 2004–2026 lückenlos, 0 Dubletten**, gegen die TED-API verifiziert. Rollen-agnostisch — dieselben Tabellen tragen später beide Marktseiten.

| Baustein | Status | Inhalt |
|---|---|---|
| Lead-Master & Export | ✅ fertig | `lead_export`, `lead_detail`; Auslauf-Radar + prospektive Leads (F01/F02), Herkunfts-Flags durchgängig |
| Los-Ebene | ✅ fertig (neu) | `lead_lot` mit `lot_cpv_code` (99,6 %) — Fundament der per-Los-Relevanz |
| Fristen & Laufzeiten | ✅ fertig | `lead_deadline` (Angebotsfrist, echt/geschätzt), `lead_duration` (Vertragsende) |
| Nachfolge & Incumbent | ✅ fertig | 100.071 verifizierte Nachfolgen, Retention 28,3 %, `incumbent_tenure`, `head_to_head` |
| Entity-Auflösung & Gruppen | ✅ fertig | `entity_identity` (302k Identitäten), `dim_company_group`, gruppen-bewusstes Winner-Matching. Namens-Resolution gemessen ausgereizt |
| Markt-Intelligenz | ✅ fertig | `contractor_stats`, `market_opportunity` (511 Segmente), `retender_signal`, `cpv_adjacency` |
| Wert, Bänder & Pricing | ✅ fertig | `value_band_effektiv`, `value_anchor` (Billing-Wächter), `award_tender_link` (Attribution), 7-Band-Flat-Pricing |
| Geografie & Radius | ✅ fertig | `dim_plz`, `lead_geo` (99,8 %), `dim_nuts` — Umkreis- & Regionssuche, zwei Achsen |
| Strategie-Aggregate | ✅ fertig | `strategie.json` — vorberechnet je Branche (Pipeline, Felder, Vergabestellen, Wettbewerb, Bindung) |

---

## Schicht 2 — Logik (rollen-agnostisch) · ~80 % geteilt

Relevanz & Analyse als `relevance(entität, ausschreibung)` — nicht an den eingeloggten Anbieter fest verdrahtet. Bereit für die zweite Marktseite.

| Baustein | Status | Inhalt |
|---|---|---|
| Profil- & Match-Engine | ✅ fertig | `matchLead` mit erklärbarer Passung (Feld/Region/Volumen), K.-o.-Kriterien, Bund-Erkennung |
| Per-Los-Relevanz | ✅ fertig (neu) | `scoreLeadPerLot` — Ausschreibung erbt die Relevanz ihres besten Loses |
| Angriff / Verteidigung | ✅ fertig | `istEigen` real verdrahtet — Verdrängungs-Risiko vs. Wechsel-Chance je Lead |
| Sprachschicht | ✅ fertig (neu) | Export sprachneutral (nur Codes); Übersetzung im Frontend-Katalog `labels.js`. Zweite Sprache = zweiter Katalog |

---

## Schicht 3 — Frontend & Features (v1-Tickets)

| # | Feature | Status | Anmerkung |
|---|---|---|---|
| #1 | Lead Explorer | ✅ fertig | Liste, Filter, Herkunfts-Spalten, Suche, Merkliste |
| #2 | Personal-Fit | ✅ fertig | Firmenprofil → Relevanz; Bund-Käufer-Regel |
| #3 | Direktvergleich Du ↔ Incumbent | ✅ fertig | Feld-Zuschläge, Marktanteil/Rang/Trend, Verträge beim Buyer |
| #6 | Auth & Konto | ✅ fertig | Supabase-Auth, RLS, `profile_type` (rollen-agnostischer Anker, neu) |
| #7 | Onboarding-Flow | ✅ fertig | Vier Schritte; Kasten-Padding korrigiert (neu) |
| #8 | Analytics | ✅ fertig | Event-Layer verdrahtet · **PostHog-Transport = Stub** |
| #9 | Alerts | ✅ fertig | DB + UI + Trigger-Logik · **E-Mail-Transport = Stub** |
| #10 | Strategie | ✅ fertig | 8 Sektionen, echte Aggregate (Pipeline 8,27 Mrd €, Vergabestellen-Matrix) |
| #11 | Treffergüte | ✅ fertig | Erklärbare Match-Güte, Erhebung im Bedarfsmoment |
| #12 | Losebene | ✅ fertig (neu) | Per-Los-Relevanz, „passt über Los N" in Liste + Detail-Hervorhebung |
| #13 | Vergabeunterlagen-Link | ✅ fertig (neu) | Wasserfall docs→Plattform→kein Link (behob toten Link); Quelle unterschieden |
| #14 | Entity-Härtung | ✅ fertig (neu) | Backend + Konfidenz-Ehrlichkeit: unsicherer Incumbent ehrlich, statt „kein Amtsinhaber" |
| #15 | Anforderungs-Check | ◑ teilweise | Zuschlags-**Gewichtung** + Basis (CPV/Rechtsrahmen) fertig · Weg-A-Restfelder offen · Weg B vertagt |
| #16 | Verfahrenskalender | ◑ teilweise | Angebotsfrist mit Datum + Dringlichkeit im Detail (neu) · Kalenderseite + iCal offen |
| #6b | Billing | ◑ Abo offen | Erfolgsprämie **gestrichen 2026-08-21** (Code raus, Schema via 0012) · Abo-Transport = Stripe-Stub |
| #10s | Settings | ✅ fertig | Konto, Profil, Alert-Einstellungen, Datenexport, Löschung |

---

## In dieser Session geliefert (8 verifizierte Ergebnisse)

l.eigen real verdrahtet · profile_type-Anker · Rahmenvertrag-Bewertungssignal · Label-Smell → sprachneutraler Export · #13 Unterlagen-Link · #16 Angebotsfrist + Dringlichkeit · #12 Per-Los-Relevanz · #14 Konfidenz-Ehrlichkeit · (+ Onboarding-Padding).

---

## Offen bis Launch

- **#15 Weg A vervollständigen** — Bürgschaft, Nebenangebote, Eignung, Bietergemeinschaft aus `attributes` (ohne Reparse) in `lead_export` + UI. Weg B (Doku-Crawl + LLM mit Pflicht-Seitenbeleg) danach.
- **#16 Kalender-Übersicht + iCal-Feed** — chronologische Fristen der Watchlist; Uhrzeit & Bieterfragen-Frist aus dem XML.
- **Externe Transporte anschließen** — E-Mail (Resend/SES), PostHog, Stripe (nur Abo). Logik steht, es fehlen nur die Provider-Keys.
- **Deployment + Pflicht-Security-Review** — RLS, Secret-Key server-only, §9-Blur serverseitig, innerHTML-XSS; plus npm-Vulns (Next SSRF, PostCSS, sharp).
- **notice_id-Normalisierung** — Unterstrich/Bindestrich-Doppelformat verwaist bei jedem Monatswechsel ~551 Leads (bekannt, eigener Schritt).

---

## Preis-relevanter Kontext (für den Preismodell-Chat)

Die Bausteine, an denen ein Preismodell andockt — was die Datenlage **wirklich** hergibt:

- **⚠️ Pricing-Staffel: kein Code mehr.** `govisor/pricing.py` wurde am 2026-08-17 mit
  der Erfolgsgebühr gelöscht (Commit `dd1f290`); im Code stehen nur noch die Bandgrenzen
  in `gold._band_sql`. Die Beträge sind seither eine Geschäftsentscheidung auf Papier —
  reines **Flat-per-Band**, 7 Stufen, Pauschalen verdoppeln sich — `<100k`=600 / `100–250k`=1.200 / `250–500k`=2.400 / `500k–1,3M`=4.800 / `1,3–5M`=9.600 / `5–25M`=15.000 / `>25M`=25.000 €. `imputiert`/`default` → ×0,8.
- **Warum Flat statt %:** Wert-Schätzung trifft nur **~42 %** das richtige Band (gemessen) → Prozent auf geratenen Wert ist nicht verteidigbar. Abgerechnet wird auf echtem Wert (**~65 %** publiziert), der Rest via Kunden-Bestätigung.
- **Gebühren-Basis nie „unbekannt"** (`value_band_effektiv`): echter Wert 37 % / geschätzt 5 % / CPV-Median-imputiert 52 % / default 6 %, mit `band_source` als Fairness-Regler.
- **Erfolgsprämie — GESTRICHEN am 2026-08-21.** Sie war nie scharf (kein Rechnungslauf, kein Provider-Key) und versprach Nutzern in einem Dutzend Texten eine Abrechnung, die es nicht gab. Code entfernt, Schema räumt `supabase/0012_erfolgspraemie_entfernen.sql`. Was vom Unterbau übrig ist und heute niemand liest: `value_anchor` (Wert-Schätzer, ~42 % exakt) und `award_tender_link` (Attribution, wird anderweitig gebraucht).
- **Gate-Logik:** `entity_confidence` (confirmed/probable/none) kennzeichnet die Identität. Ein Abrechnungs-Gate hängt seit dem 2026-08-21 nicht mehr daran; der Klick auf den Bewertungs-Tab markiert nur noch den Fortschritt.
- **Free/Pro:** kostenlos = Liste + Basisdaten + Netzwerkteilnahme (Dichte/Vertrauen); bezahlt = Wettbewerbssicht, Strategie, Export, Fristen. Strategie ist rein Pro-gegated (sektionsweise), verbraucht keine Analysen.
- **Offen (Business, nicht Technik):** finale Beträge, Rabatt-Faktor, Attributions-/Rechnungs-Mechanik. Marktvalidierung liegt in der Pricing-Research-Notiz.

> Quelle der Zahlen: lokales Parquet/DuckDB (`docs/pricing-modell.md`, `docs/entscheidungen-und-kontext.md`).
>
> ⚠️ **Der Satz „In Supabase liegt nur ein Entwicklungs-Sample“ stand hier und war
> falsch.** Der Tageslauf schob zweimal täglich den VOLLEN Bestand hoch, bis am
> 2026-08-16 787 MB bei 500 MB Free-Limit standen. Seither sind die `gov_*`-Tabellen
> **absichtlich leer** und der Push liegt hinter `GOVISOR_SUPABASE_GOV_PUSH=1`
> (Vorgabe: aus) — sie liest ohnehin niemand, das Frontend holt seine Leads aus
> `web/data/*.json`. Gezählt werden kann nur lokal. Einzelheiten in CLAUDE.md,
> Abschnitt „lokal entwickeln, Supabase ist Deploy-Ziel“.
