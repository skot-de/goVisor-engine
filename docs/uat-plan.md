# goVisor — UAT-Plan (User Acceptance Testing)

**Zweck:** Jede Funktion und jeden angezeigten Wert einmal bewusst prüfen — von der Datenschicht
bis zur UI, Kundenseite + Vergabestellenseite + internes Tool. Grundlage: die gebauten Tickets
#6/#8/#9/#10/#11(+§7/§9)/#16/#17/#20/#21/#26/#27/#28 sowie die Kern-Engine.

**Erstellt:** 2026-08-09 · **Stand Commit:** `f749ffd`

## Prinzipien der Abnahme (aus CLAUDE.md)
- **Messen statt annehmen** — jeder Wert wird gegen die echten Daten geprüft, nie „sieht plausibel aus".
- **Kein erfundener Wert** — wo die Datenlage dünn ist, muss die UI das ehrlich benennen (Fallzahl,
  „unbekannt", „zu wenig Vergleich"), nicht raten.
- **Band statt Punkt** — Wertaussagen als Band (`value_band_effektiv`), Median statt Mittelwert.

## Ausführungsmodus je Fall
- **[AUTO]** — ich fahre es headless jetzt (Python-Endpunkte, DuckDB-Gegenrechnung, DB/RLS via psql,
  tsc/SWC-Compile, Engine-Unit-Tests). Beleg = Ausgabe/Zahl.
- **[UI]** — braucht eine eingeloggte Sitzung im Browser. Läuft, sobald der Login-Weg geklärt ist.
- **[MANUAL]** — nur du kannst es (Passwort eingeben, Zahlungsmittel, echte E-Mail empfangen).

## Testdaten / Referenz-Identität
Für datenseitige Fälle nutze ich eine belegte Identität mit reicher Historie:
`grp:rosenbauer` (3.192 Zuschläge, Bayern-Schwerpunkt, CPV Schwerlastfahrzeuge). Für Quoten/Bilanz
lege ich per Service-Key temporäre `user_outcomes`-Testzeilen an und räume sie hinterher weg.

---

## 0. Umgebung & Rauchtest

| ID | Modus | Prüfung | Erwartetes Ergebnis |
|---|---|---|---|
| ENV-01 | AUTO | Dev-Server läuft, alle neuen Routen kompilieren | `/leads /strategy /unternehmen /authority` → HTTP 200, 0 Build-Fehler |
| ENV-02 | AUTO | `tsc --noEmit` über `web/` | Exit 0, keine Typfehler |
| ENV-03 | AUTO | Supabase erreichbar, neue Tabellen existieren | `user_declarations/outcomes/gap_effects`, `agg_buyer_outcomes`, Storage-Bucket `nachweise` vorhanden |
| ENV-04 | AUTO | Gold-Datenschicht vorhanden | `lead_export.parquet` lesbar, Spalten `value_eur/guarantee_required/phase/cpv_code` da |

---

## 1. Datenschicht & Werte (Fundament)

| ID | Modus | Prüfung | Erwartetes Ergebnis |
|---|---|---|---|
| DATA-01 | AUTO | `final_value_clean` gedeckelt & EUR | keine Werte > 1 Mrd, nur EUR fließt in Aggregate |
| DATA-02 | AUTO | Median statt Mittelwert bei Volumenaussagen | Firmenprofil/Bilanz nutzen `median()`, nicht `avg()` |
| DATA-03 | AUTO | `notice_id` kanonisch (kein Bindestrich/Zero-Pad-Drift) | 0 nicht-kanonische TED-IDs in Silber/Gold |
| DATA-04 | AUTO | Vorbefüllung `profil_vorbefuellung.py` | für `grp:rosenbauer`: name/confidence=belegt, ≥15 Referenzen, CPV-Schwerpunkt, Regionen, Umsatz-Näherung + coverage |
| DATA-05 | AUTO | Öffentliche Bilanz `bilanz_public.py` | wins_total>0, wins_by_year monoton mit Jahren, buyers_worked>0 |
| DATA-06 | AUTO | Haversine-Distanz NULL-Guard | Leads ohne Koordinate → dist=NULL (nicht 0), fallen nicht fälschlich in den Umkreis |
| DATA-07 | AUTO | KMU-Berechnung (EU-Definition) | ma<250 ∧ umsatz≤50Mio → KMU; Grenzfälle Kleinst/Klein/Mittel korrekt |

---

## 2. Auth, Onboarding, Session

| ID | Modus | Prüfung | Erwartetes Ergebnis |
|---|---|---|---|
| AUTH-01 | MANUAL | Registrierung mit neuer E-Mail | Konto angelegt, Bestätigungsflow |
| AUTH-02 | MANUAL | Login mit gültigen Daten | Weiterleitung in die App, Session gesetzt |
| AUTH-03 | UI | Login-Fehler bei falschem Passwort | Fehlermeldung, kein Zugang |
| AUTH-04 | UI | Onboarding: Firmensuche → Entity-Zuordnung | getippter Name → Fuzzy-Treffer, Bestätigung setzt `identity_id` + `entity_confidence` |
| AUTH-05 | UI | Onboarding: Schwerpunkte + Regionen | Auswahl landet in `user_profiles` (cpv_fields, regions) |
| AUTH-06 | UI | Logout | Session weg, `/leads` leitet auf Login |
| AUTH-07 | AUTO | RLS: fremde Profile unsichtbar | anon/anderer User liest `user_profiles` einer fremden id nicht |

---

## 3. Lead-Liste, Suche, Filter, Sortierung

| ID | Modus | Prüfung | Erwartetes Ergebnis |
|---|---|---|---|
| LEAD-01 | AUTO | `/api/leads?branche=bau` liefert echte Leads | Array > 0, Felder id/cpv/buyer/volumen/frist |
| LEAD-02 | UI | Spalten vollständig (goVisor-X-RAY) | Status/Auftraggeber/Gegenstand/Dienstleister/Volumen/Vergabe/Fällig/TED/Empfehlung |
| LEAD-03 | UI | Volltextsuche + Token-Facetten (Ort/CPV/…) | Treffer filtern korrekt, Token-Chips aktiv |
| LEAD-04 | UI | Umkreissuche (Stadt + Radius) | z. B. München 25 km → Ergebnis + „bundesweit" ans Ende sortiert |
| LEAD-05 | UI | Fachgebiet-Zähler auf aktiven Filter bezogen | Zähler ändert sich mit gesetztem Filter |
| LEAD-06 | UI | Filter Relevanz/Empfehlung (Multi-Kriterien) | Liste reduziert sich, ausgeblendete Zahl sichtbar |
| LEAD-07 | UI | Phase-Filter (offen/auslaufend/Zuschlag #24) | Award-Leads erscheinen in der Phase, korrekt markiert |
| LEAD-08 | UI | Sortierung Frist / Ranking / **Empfehlung (#26)** | Empfehlung-Sort: Bewerben/Hohe Passung zuerst, Nicht bewerben zuletzt |

---

## 4. Lead-Detail & #26 Handlungsempfehlung

| ID | Modus | Prüfung | Erwartetes Ergebnis |
|---|---|---|---|
| REC-01 | AUTO | Engine gegen alle 11 §3.8-Beispiele | Idealfall→Bewerben, Zertifikat fehlt→Nicht bewerben, unklar→Noch zu klären, eigen→Verteidigen, … (11/11 bei korrekter E-Kodierung) |
| REC-02 | AUTO | Kaskade B ausgesetzt < 60 % Abdeckung | Kaltstart-Profil → nur Einordnung (Kaskade A), Empfehlung=null |
| REC-03 | AUTO | Zustand A (keine Unterlagen) → keine Empfehlung | `gesperrt='keine_unterlagen'`, Hinweistext |
| REC-04 | AUTO | „Noch zu klären" nie ohne Frage | jeder B5/B7-Fall trägt `frage` + Handlungsschritt |
| REC-05 | AUTO | Zusätze max. 2, feste Rangfolge | Partner→Los→Frist→Bieter→Rahmen→Erstvergabe→Stelle |
| REC-06 | UI | Detail: Begründungskette E1–E10 sichtbar | Tabelle mit Zustand+Quelle je Größe |
| REC-07 | UI | Liste-Spalte = eine Zelle, zwei Inhalte, farbig | kein Blur, kein Rot, Award-Leads behalten awardEmpfCell |
| REC-08 | UI | Widerspruch speicherbar | „bewerben wir uns trotzdem" wird gespeichert, nicht kommentiert |

---

## 5. Strategie & Treffergüte (#11)

| ID | Modus | Prüfung | Erwartetes Ergebnis |
|---|---|---|---|
| STRAT-01 | UI | Sektionen Markt (Pipeline/Felder/Stellen/Wettbewerb) | Aggregate laden, Fallzahlen ausgewiesen |
| STRAT-02 | UI | Sektionen Wir (Position/Fähigkeiten/Bindung/Profil) | Pro-Gates greifen, Werte mit Fallzahl |
| TG-01 | UI | Treffergüte-Nav vorhanden (Gruppe „Wir", über Profil) | Sektion erreichbar |
| TG-02 | UI/AUTO | Block 1 Lücken nach betroffener Lead-Zahl | „betrifft N Leads", ≥3-Schwelle, absteigend |
| TG-03 | AUTO | gap_effects vorberechnet bevorzugt | user_gap_effects-Werte werden statt On-Demand genutzt |
| TG-04 | UI | Block 1 Inline-Erfassung → Wirkung sofort | Angabe hinterlegt → „N Leads ändern Relevanzstufe", Zeile verschwindet |
| TG-05 | UI | Block 2 gemessen vs. erklärt + „Stimmt so" | Sammelbestätigung setzt confirmed_at, ⚠ bei >6 M |
| TG-06 | UI | Block 3 privates Tracking + Bilanz | Quote/Volumen nur eigene; Meldung ≠ Erfolgsprämie steht im Text |
| TG-07 | UI/AUTO | Ergebnis melden (won/lost/rank/reason) | Zeile in user_outcomes, Bilanz aktualisiert |
| TG-08 | UI | Block 4 Datenlage-Grenzen | 35 %/49 %/63 %-Zeilen vorhanden |
| TG-09 | AUTO | Kein Prozentscore / keine Gamifizierung | keine Balken/Badges/„Gut gemacht" |

---

## 6. Unser Unternehmen (#27 Eignungsprofil)

| ID | Modus | Prüfung | Erwartetes Ergebnis |
|---|---|---|---|
| UN-01 | UI | Nav-Eintrag „Unser Unternehmen" | erreichbar |
| UN-02 | UI/AUTO | Vorbefüllung aus eigenen Zuschlägen | Referenzen als „abgeleitet", CPV-Schwerpunkte übernommen |
| UN-03 | UI | Entity-Korrektur (Firmensuche → wählen) | `identity_id` neu gesetzt, Vorbefüllung neu berechenbar |
| UN-04 | UI | Stammdaten + Live-KMU | KMU-Badge ändert sich mit Umsatz/MA |
| UN-05 | UI | Zielrichtung (Bestand/Ausgewogen/Expandieren) | Auswahl gespeichert |
| UN-06 | AUTO | Zielrichtung/Ausschlüsse wirken auf Relevanz | matchLead: Ausschluss→niedrig; keine_bietergemeinschaft unterdrückt Partner |
| UN-07 | UI | Anforderungskatalog (4 Typen, 3 Zustände) | binär/schwelle/sammlung/kennung; angegeben/belegt/abgeleitet sichtbar |
| UN-08 | UI | Referenzen (Sammlung, abgeleitet→bestätigen) | Bestätigung zählt, K.-o.-Flag |
| UN-09 | UI | Zertifikate + 90-T-Ablauf | abgelaufen zählt nicht, Ablauf-Badge |
| UN-10 | UI/AUTO | Nachweis-Upload (Storage) | Upload→„belegt", ansehen via signierte URL, RLS pro user-Pfad |
| UN-11 | UI | Ausschlusskriterien | Wertgrenzen/Regionen/CPV/keine-BG gespeichert |
| UN-12 | UI | Rolle (Ansprechpartner) | nur eigene, keine Dritten |
| UN-13 | UI | Export JSON + PDF | JSON-Download vollständig; PDF-Druckansicht |
| UN-14 | AUTO | „Kein Datenverlust": saveProfile merge-sicher | Onboarding-Save überschreibt #27-Keys nicht |

---

## 7. Bilanz & Chancen (#28)

| ID | Modus | Prüfung | Erwartetes Ergebnis |
|---|---|---|---|
| BIL-01 | AUTO | Echte Quote erst ab 10 Meldungen | <10 → „N Meldungen fehlen"; ≥10 → Prozent + Vollständigkeitshinweis |
| BIL-02 | AUTO | Aufschlüsselung Stelle/Größe ab Fallzahl 5 | Kategorien <5 erscheinen nicht; angezeigte immer mit Fallzahl |
| BIL-03 | AUTO | bekannte vs. neue Stellen | Namensabgleich gegen buyers_worked, Quote je Gruppe |
| BIL-04 | UI | Volumen öffentlicher Aufträge (Balken) | berechnet aus Zuschlägen, „—" wo kein EUR-Wert |
| BIL-05 | UI | Verweise statt Duplikate | Links in #10/#25, keine nachgebauten Tabellen |
| CHAN-01 | UI | Anforderungs-Coverage (erfüllt/nicht/offen) | nicht-erfüllt+häufig oben |
| CHAN-02 | UI | Markthäufigkeit ehrlich korpus-abhängig | keine Aussage über andere Firmen, Mindestfallzahl-Hinweis |
| BIL-06 | UI | Gate: eigene Bilanz frei, Marktvergleich Pro | Bilanz sichtbar ohne Pro; Chancen-Häufigkeit Pro/++ |

---

## 8. Vergabeblick (#20/#21, Käuferseite)

| ID | Modus | Prüfung | Erwartetes Ergebnis |
|---|---|---|---|
| VB-01 | UI | Ausschreibungscheck: Feld/Lose/Bürgschaft/Preis | Bieter-Prognose reagiert direktional |
| VB-02 | UI | #20 Wert-Plausibilität | Schätzwert ↔ Band vergleichbarer Verfahren, unter/über/im, Fallzahl, kein Punktpreis |
| VB-03 | UI | #20 „zu wenig Vergleich"-Fallback | dünne Basis → ehrlicher Hinweis statt erfundenem Band |
| VB-04 | UI/AUTO | #21 Eignung Mehr-Kriterien-Tabelle | je Kriterium % erfüllender Anbieter (Umsatz/Referenzen), ●●●○○ |
| VB-05 | UI/AUTO | #21 kumulativer Effekt vs. Median-Bieterfeld | „alle erfüllen: N Anbieter" vs bieterMedian; <8 Anbieter → keine Aussage |
| VB-06 | UI | #21 ISO ehrlich als „dünn" | ISO-Zeile ohne quantifizierten Erfüllungsgrad |
| VB-07 | UI | Nachweisdichte-Check (Upload Entwurf #23) | Entwurf-Nachweiszahl vs Feld-Median, nicht persistiert |
| VB-08 | UI | Controlling/Pflichten (KMU §97, Preis/Qualität) | Werte mit Fallzahl, § 97-Andockpunkt |

---

## 9. Internes Vertriebstool (/intern)

| ID | Modus | Prüfung | Erwartetes Ergebnis |
|---|---|---|---|
| INT-01 | UI | Segmente A–G + Priorisierung | Tabs, §8-Einmalzuordnung, weitere_Segmente |
| INT-02 | UI | Firmensuche (PLZ/Radius/Ort/Name) | Treffer mit belegter Entität |
| INT-03 | UI/AUTO | Firmendetail: Leads (CPV-6/Umkreis) + Wettbewerber | passende offene Ausschreibungen regional, ehrlicher Wettbewerber-Proxy, TED-Link |
| INT-04 | UI | Outreach protokollieren + Cooldown | angesprochen/interessiert/gewonnen, 12-M-Cooldown |
| INT-05 | UI | CSV-Export | Segment/Signal/Rahmen-Quote-Spalten |

---

## 10. Runner & Deploy-Pfad

| ID | Modus | Prüfung | Erwartetes Ergebnis |
|---|---|---|---|
| RUN-01 | AUTO | DÖE `--fetch` lädt laufenden Monat | frische Notices, konsolidiert |
| RUN-02 | AUTO | launchd: zwei Slots 13:00 + 22:00 | Kalender-Slots registriert |
| RUN-03 | AUTO | gap_effects im Runner (nicht-fatal) | schreibt user_gap_effects, bricht Lauf nicht ab |
| RUN-04 | AUTO | §9 Aggregation dormant | ohne AGGREGATE_ENABLED kein Lauf; mit Flag ≥5-Firmen-Guard |
| RUN-05 | AUTO | Middleware Blackout + Preview-Bypass | Prod ohne LAUNCH_LIVE → schwarze Seite; `?preview=<key>` öffnet |

---

## 11. Sicherheit, RLS, Gate

| ID | Modus | Prüfung | Erwartetes Ergebnis |
|---|---|---|---|
| SEC-01 | AUTO | RLS user_outcomes/declarations/gap_effects | nur eigene Zeilen (auth.uid()=user_id) |
| SEC-02 | AUTO | KEIN FK user_outcomes → success_fee | Schema ohne Verbindung (AC12) |
| SEC-03 | AUTO | Storage-RLS Nachweise | nur eigener user-id-Pfadpräfix les-/schreibbar |
| SEC-04 | AUTO | agg_buyer_outcomes ohne User-Read-Policy | authenticated liest nicht (dormant) |
| SEC-05 | AUTO | Analyse-Tabellen ohne Policy (Paywall) | keine Policy → nur Service-Key |
| SEC-06 | UI | §9-Blur / interne Kontaktdaten nicht public | INTERN_ENABLED steuert, nie zusammen mit LAUNCH_LIVE |

---

## Durchführung
Reihenfolge: erst alle **[AUTO]** (Datenschicht → Engine → RLS → Runner), dann **[UI]** nach
geklärtem Login, **[MANUAL]** durch Sven. Jeder Fall wird mit Ist-Ergebnis + Beleg (Zahl/Ausgabe/
Screenshot) protokolliert; Abweichungen werden als Findings mit Schweregrad notiert und behoben.
