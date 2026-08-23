# Länder-Onboarding — Checkliste / Playbook

> ⚠ **ABGELÖST (2026-08-23).** Die vollständige Anleitung ist jetzt
> [`docs/land-onboarding.md`](land-onboarding.md) mit den Kapiteln in `docs/laender/`.
> Dieses Dokument bleibt stehen, weil sein **Kurz-Steckbrief** (Abschnitt 0) noch die
> besten Erstfragen an ein unbekanntes Land stellt — der Rest ist dort ausführlicher und
> mit gemessenen Zahlen belegt.

Was wir prüfen, bevor wir ein neues Land in goVisor aufnehmen. Reihenfolge = grob die
Bau-Reihenfolge. Jeder Punkt ist eine **Messung an echten Daten**, keine Annahme
(Arbeitsweise-Prinzip). Die DACH-Referenz unten zeigt, wie unterschiedlich die Antworten
ausfallen — genau deshalb lohnt die Checkliste.

---

## 0. Kurz-Steckbrief (zuerst beantworten)
- [ ] **Land + ISO-Code**, Amtssprache(n) der Bekanntmachungen (DE/FR/IT/EN …).
- [ ] **Währung** (für Wert/Bänder/Pricing).
- [ ] **EU-Mitglied?** → in TED oder nicht (CH z. B. nur teils, über bilaterale Abkommen).
- [ ] **Grober Marktumfang**: wie viele Bekanntmachungen/Jahr erwartbar? (Skalierung, Sinnhaftigkeit)

## 1. Datenquellen (Notice-Ebene)
- [ ] **TED-Abdeckung** (oberschwellig): trägt TED das Land vollständig? Ab wann? Welche
      `schema_gen` (eforms/legacy/…)? → deckt nur EU-Schwellenwert-Vergaben.
- [ ] **Nationale/lokale Plattform(en) für UNTERSCHWELLIGE Vergaben** — der eigentliche Hebel,
      TED sieht sie nicht. Gibt es eine zentrale Plattform oder viele? Namen notieren.
- [ ] **API-Zugang je Quelle**:
  - [ ] Offene JSON/REST-API? Oder nur CSV-Bulk / HTML-Scraping?
  - [ ] Key/Login/Registrierung nötig? Rate-Limits? User-Agent-Pflicht?
  - [ ] **Lizenz** (CC0 / offen / eingeschränkt)? Automatisiertes Abrufen erlaubt (ToS)?
  - [ ] Paging-Mechanik (Cursor / Offset / Datumsfenster)? Bulk-Download?
- [ ] **Aktualität**: Live-Feed vs. Monatsarchiv? Ersetzt ein Archiv den Live-Stand
      (→ notice_id-Drift, s. DE-Fallstrick)?

## 2. Feld-Mapping / Schema
- [ ] **notice_kind-Mapping** der Quelle → unser Vokabular (`cn`=Ausschreibung, `can`=Zuschlag,
      `pin`=Vorinfo). Welche pubTypes/Formulartypen gibt es?
- [ ] **notice_id-Namespace**: kollidiert er mit dem TED-`publication_number`-Raum? (UUIDs/reine
      Zahlen sind sicher; `NNNNNN-YYYY` kollidiert → eigener Präfix/Normalisierung nötig.)
- [ ] **Losstruktur** vorhanden? (Manche eForms-Dialekte kennen keine Lose → Ø 1,0 Los.)
- [ ] Kernfelder belegt: Titel, Beschreibung, **CPV**, Käufer, Wert+Währung, **Frist**,
      Region, Verfahrensart, Rechtsrahmen. Coverage je Feld messen.
- [ ] **Beschreibungstiefe**: wie viel Freitext trägt die Quelle wirklich? (Titel-Zweizeiler
      vs. echte Leistungsbeschreibung — s. `docs/data-sources.md`.) Quellen **nie zusammen
      zitieren** ohne die Tiefe je Quelle auszuweisen.

## 3. Geo (Umkreis-/Regionssuche)
- [ ] **PLZ→Koordinate-Quelle** (GeoNames o. ä.). Stellenanzahl der PLZ notieren —
      ⚠️ **AT und CH sind beide 4-stellig und kollidieren** (1010 = Wien/Lausanne) → Auflösung
      über den aktiven Länderfilter (s. `plzLookup` im Frontend).
- [ ] **NUTS-Codes** vorhanden/mapbar? Für Regionsfilter + Namens-Autocomplete.
- [ ] **Stadt-Index** für die Umkreissuche per Stadtnamen (s. `scripts/build_city_index.py`).
- [ ] **Bundesweit/ortsungebunden**-Kennzeichen (DE: `Region=anyw*`) → sonst fallen diese Leads
      aus jeder Umkreissuche.

## 4. Vergabedokumente (Leistungsbeschreibung/Unterlagen) — die schwierigste Achse
Hier fällt die Entscheidung **automatisierbar / on-demand / nur Metadaten**. Je Quelle prüfen:
- [ ] Trägt die Quelle überhaupt einen **`documents_url`** je Notice? (DE ja, **AT fast nie —
      nur TED-Links**.)
- [ ] **Zugang login-frei oder gegated?** Konkret testen: ZIP/Datei-URL ohne Login abrufen →
      HTTP-Status + Content-Type. (HTML zurück = Login-/Teilnahme-Wand.)
- [ ] **Kostenlos oder kostenpflichtig?** (simap: Metadatenfeld `documentsWithCosts`.)
- [ ] **Nur während offener Frist** verfügbar? (simap: nach Fristablauf 404 → nur offene Leads.)
- [ ] **Download-Mechanik**: direktes ZIP? Token-Flow (Token holen → download)? SPA-API
      (Netzwerk-Calls im Browser lesen / JS-Bundle nach Endpoints grepen)?
- [ ] **Eine Plattform oder viele Portale?** (DE: Dutzende cosinex/DTVP-Instanzen; CH: eine.)
- [ ] **Bot-Schutz/CAPTCHA?** (Bund-DE: Wicket/Anti-Bot → nicht skriptbar.)
- [ ] **Metadaten-Ebene**: auch ohne Datei-Zugang — sagt die API, *ob* Docs existieren,
      Sprache, Kosten? (→ Verfügbarkeits-Indikator im Lead ohne Download.)
- [ ] **Registrierungs-Reibung** für den On-Demand-/Upload-Weg: einmalig (eine Plattform) oder
      pro Portal/pro Ausschreibung? (Bestimmt, ob „du lädst, wir verwerten" praktikabel ist.)

> **Regel/Grenze:** Login, Account-Anlage und CAPTCHA-Lösen macht die Automatik **nicht** —
> das ist eine harte Grenze. Wo Download Login braucht, ist der Weg: Nutzer lädt (sein Recht als
> Interessent), Pipeline verwertet (`index-docs → signals-docs → Anzeige`).

## 5. Entity-Resolution (Bieter & Vergabestellen)
- [ ] **Nationales Firmen-/Handelsregister** für Bieter-Auflösung? (DE: HR/HRB.)
- [ ] **Behördenverzeichnis** (AGS-Äquivalent) für Vergabestellen-Konsolidierung?
- [ ] **Eindeutige Käufer-ID** (Leitweg-ID-Äquivalent, E-Rechnung)? Der stärkste Hebel gegen
      Vergabestellen-Fragmentierung.
- [ ] Externe Anreicherung möglich (Wikidata, nationales Statistikamt)?

## 6. Rechtlicher & regulatorischer Rahmen
- [ ] **Vergaberecht + Schwellenwerte** (was ist ober-/unterschwellig?).
- [ ] **Verfahrensarten** → `regulatory_regime`-Mapping.
- [ ] **Datenschutz**: Personendaten in den Daten (Kontaktpersonen)? Blur-/Redaktions-Regel
      (§9-Äquivalent) nötig?

## 7. Frontend / Produkt
- [ ] **Länderfilter** (`staaten`) + Label ohne „bald", sobald Daten fließen.
- [ ] **Währungs-/Zahlenformat**, Sprache der Beschreibungen.
- [ ] **Pricing/Bänder** in Landeswährung sinnvoll?
- [ ] Quell-Icons/Herkunft im Lead (welche Plattform).

## 8. Pipeline-Integration (Bau)
- [ ] Connector schreiben + in **`govisor/sources.py`** registrieren (Connector × Land × Tier).
- [ ] **`ingest-<land>`**-CLI (Bronze) → `silver` → `gold`.
- [ ] **web-Export** (`export_web_leads.py`) inkl. Land in `leads-*.json` (`land`-Feld).
      ⚠️ Reexport überschreibt `plz-geo.json` ohne `_cities` → `build_city_index.py` nachziehen.
- [ ] **Tests** (Plumbing/Vokabular) + `verify` gegen die Quelle (Zählung, 0 Dubletten).

## 9. Qualitäts-/Vollständigkeits-Gate
- [ ] Bestandszählung gegen die Quell-API verifiziert.
- [ ] Dubletten-Check (v. a. TED × nationale Quelle — dasselbe Verfahren doppelt?).
- [ ] Coverage je Feld dokumentiert (ehrlich, mit `*_source`-Flags).
- [ ] Auffällige Aggregatzahlen als Warnsignal geprüft.

---

## DACH-Referenz (gemessen 2026-07-30)

| Achse | 🇩🇪 DE | 🇦🇹 AT | 🇨🇭 CH |
|---|---|---|---|
| TED | vollständig | vollständig | teils (bilateral) |
| Unterschwellig-Quelle | DÖE / oeffentlichevergabe.de (CC0-API) | OffeneVergaben.at (CSV-Bulk) | **simap.ch** (offene JSON-REST-API) |
| Leads (Frontend) | ~21.000 | ~1.100 | ~1.700 |
| `documents_url` je Lead | 98 % (gemischt) | **nur ~10 %, alle → TED** | **100 % → simap.ch** |
| Doku-**Metadaten** | dünn | keine | **offen & reich** (Kosten/Sprache/vorhanden) |
| Doku-**Download** | 🔴 gegated (Dutzende cosinex/DTVP-Portale, Registrierung, ~0 login-frei) | 🟠 kein direkter Link | 🟠 **gratis, aber Login** (Token nur via `/vendors/my/…`, 302) |
| Registrierungs-Reibung | pro Portal + oft pro Ausschreibung | — | **einmal**, eine Plattform |
| Fazit Doku | on-demand/Upload | eigene Quelle nötig | Metadaten-Indikator + On-Demand-Upload (Einmal-Login) |

**Kernlektion:** „In TED = erledigt" ist falsch. Der Mehrwert steckt unterschwellig + in den
Leistungsbeschreibungen — und *deren* Zugänglichkeit ist je Land völlig verschieden. Die
Doku-Achse (Abschnitt 4) früh und hart testen, nicht am Ende.
