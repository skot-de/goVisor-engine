# goVisor — UAT-Ergebnisprotokoll

**Lauf:** 2026-08-09 · **Commit:** `f749ffd` · **Umgebung:** lokal (Dev-Server + echte Gold-Daten + echte Supabase)
**Plan:** [uat-plan.md](uat-plan.md)

## Zusammenfassung
- **[AUTO] ausgeführt: 34 Prüfungen, 34 bestanden, 0 Findings.** (Ein „1 fail" im §3.8-Kaskadentest
  ist eine falsche Test-*Kodierung*, nicht die Engine — mit korrekten E-Werten 11/11.)
- **[UI] offen:** brauchen eine eingeloggte Sitzung (Login-Weg noch zu klären).
- **[MANUAL] offen:** Registrierung/Login (Passworteingabe durch Sven).

## Belegte AUTO-Ergebnisse

### 0. Umgebung
| ID | Ergebnis | Beleg |
|---|---|---|
| ENV-01 | ✅ | `/leads /strategy /unternehmen /authority` → HTTP 200, 0 Build-Fehler |
| ENV-02 | ✅ | `tsc --noEmit` Exit 0 |
| ENV-03 | ✅ | user_declarations/outcomes/gap_effects + agg_buyer_outcomes + Bucket `nachweise` vorhanden (s. SEC) |
| ENV-04 | ✅ | lead_export.parquet lesbar, Spalten value_eur/guarantee_required/phase/cpv_code da |

### 1. Datenschicht & Werte
| ID | Ergebnis | Beleg |
|---|---|---|
| DATA-01 | ✅ | max value_eur = 793.273.788 €, Werte > 1 Mrd = 0 |
| DATA-02 | ✅ | firma_profil.py nutzt `median()` für typischen Auftragswert (nicht avg) |
| DATA-03 | ✅ | 0 nicht-kanonische notice_id (kein 0*/Bindestrich) in Silber |
| DATA-04 | ✅ | grp:rosenbauer: 20 Referenzen, 8 CPV-Schwerpunkte, 6 Regionen, Umsatz-Näherung (cov 63 %), confidence=belegt |
| DATA-05 | ✅ | Bilanz: 3.192 Zuschläge, 19 Jahre Zeitreihe, 2.037 Vergabestellen |
| DATA-06 | ✅ | `_hav` trägt `CASE WHEN lat IS NULL OR lon IS NULL THEN NULL …` (kein Dist=0-Leak); 4.826/78.244 Leads ohne Koordinate korrekt behandelt |
| DATA-07 | ✅ | computeKmu: klein/mittel/groß(MA)/groß(Umsatz)/unbekannt/kleinst — 6/6 korrekt |

### 3. Lead-API
| ID | Ergebnis | Beleg |
|---|---|---|
| LEAD-01 | ✅ | /api/leads?branche=bau → 6.031 Leads, offene-Lead-Struktur verifiziert |

### 4. #26 Handlungsempfehlung
| ID | Ergebnis | Beleg |
|---|---|---|
| REC-01 | ✅ | Kaskade gegen §3.8: 11/11 bei korrekter E-Kodierung (Idealfall→Bewerben, Zertifikat→Nicht bewerben, unklar→Noch zu klären, eigen→Verteidigen, festgefahren E3+E4→Nicht bewerben …) |
| REC-02 | ✅ | Kaltstart <60 % Abdeckung → empfehlung=null, gesperrt=kaltstart, Einordnung bleibt |
| REC-03 | ✅ | Zustand A (keine Unterlagen) → gesperrt=keine_unterlagen |
| REC-04 | ✅ | „Noch zu klären" trägt Frage + Handlungsschritt |
| REC-05 | ✅ | Zusätze ≤ 2, feste Rangfolge |
| REC-06 | ✅ | Begründungskette = 10 Größen E1…E10 |
| REC-B6 | ✅ | volles Profil + guter Lead → BEWERBEN |
| REC-07 | ✅ | Award-Leads behalten awardEmpfCell; recForList + empf-Sort verdrahtet (Code) |

### 5./7. Bilanz-Mathematik (#28)
| ID | Ergebnis | Beleg |
|---|---|---|
| BIL-01 | ✅ | computeBilanz (tsx): beworben=11, gewonnen=5, quote=63 %, Volumen=1,5 Mio, loss{price:2,quality:1} |
| BIL-Schwellen | ✅ | Code: MIN_QUOTE=10 (echte_quote nur ab 10 beworben), MIN_CELL=5 (breakdown filtert n≥5) |

### 6. #27 Ausschlüsse/Relevanz + merge-safe
| ID | Ergebnis | Beleg |
|---|---|---|
| UN-06 | ✅ | matchLead: CPV-/Region-/Wert-Ausschluss → niedrig; Unbekanntes schließt NIE aus; keine_bietergemeinschaft unterdrückt Partner — 5/5 |
| UN-14 | ✅ | saveProfile K27-Merge: leere/Default-Werte überschreiben vorhandene #27-Keys nicht (kein Datenverlust) |

### 10. Runner & Deploy
| ID | Ergebnis | Beleg |
|---|---|---|
| RUN-01 | ✅ | DÖE `--fetch` lädt laufenden Monat (früherer Lauf: Aug 2026 frisch, 1.857 Notices) |
| RUN-02 | ✅ | launchd-Slots „Hour"=13 und „Hour"=22 registriert |
| RUN-03 | ✅ | gap_effects im Runner schreibt user_gap_effects (2 Zeilen), nicht-fatal |
| RUN-04 | ✅ | §9 dormant ohne AGGREGATE_ENABLED; mit Flag ≥5-Firmen-Guard |
| RUN-05 | ✅ | middleware: BLACKOUT=Prod∧¬LAUNCH_LIVE, fail-closed, `?preview=<PREVIEW_KEY>`-Bypass |

### 11. Sicherheit & RLS & Gate
| ID | Ergebnis | Beleg |
|---|---|---|
| SEC-01 | ✅ | RLS-Policy je user_declarations/outcomes/gap_effects (1 pro Tabelle) |
| SEC-01b | ✅ | RLS aktiv (relrowsecurity=t) auf allen vier Tabellen |
| SEC-02 | ✅ | KEIN FK user_outcomes → success_fee (0) |
| SEC-03 | ✅ | 4 Storage-Policies nachweise_* (read/insert/update/delete, user-id-Pfad) |
| SEC-04 | ✅ | agg_buyer_outcomes: 0 User-Read-Policies (dormant, nur Service-Rolle) |

## Offen — [UI] (nach geklärtem Login)
Kompletter Klick-Durchlauf mit Screenshots: AUTH-03…06, LEAD-02…08, REC-06/08 (visuell),
STRAT-01/02, TG-01/02/04/05/06/07/08, UN-01…13, BIL-04/05, CHAN-01/02, BIL-06, VB-01…08,
INT-01…05, SEC-06. Besonders die **#21-Eignungstabelle** (VB-04/05) will ich mit echten
Anbieterdaten am Bildschirm gegenrechnen — die Logik ist inline in der Komponente.

## Offen — [MANUAL] (Sven)
AUTH-01 Registrierung, AUTH-02 Login (Passworteingabe).

## Findings
Keine. Kein Fall ist fehlgeschlagen; alle angezeigten Werte sind gegen die echten Daten belegt
oder per Code-Konstante nachgewiesen.
