# Internes Admin-Center — Konzept

Stand 2026-09-30. Vorgehen (Sven): erst Konzept & Inhalte, dann bauen. Zweck: **Insights
UND Troubleshooting** in einem internen Werkzeug.

## Grundstein (schon da)

`/intern` + `/api/intern/{claims,firmen,landing,lauf,outreach}`, abgesichert über `istAdmin`
(Env-Allowlist `ADMIN_EMAILS`, `web/lib/admin.ts`), 404-Gating in der Middleware, in
Produktion hart gesperrt (`INTERN_ENABLED`). Darauf baut das Admin-Center auf.

## Leitplanken

- **Läuft auf dem Worker-Dienst (Deploy-Weg C).** Fast alle Inhalte brauchen Datei-/Python-/
  DB-Zugriff (`intern/lauf` liest das Dateisystem, Firmensuche/Outreach starten Python). Das
  Admin-Center ist deshalb kein Teil der öffentlichen Edge-App, sondern lebt auf demselben
  Dauer-Host wie die schweren Routen. Es hängt damit am Deploy-Startschuss.
- **Sicherheit**: hinter `istAdmin`, eigenes Gate/Netz, nie Teil der öffentlichen App,
  Audit-Log für Aktionen.
- **Passwörter**: der Admin löst nur eine **Reset-Mail** aus (Supabase), setzt nie selbst ein
  Passwort.

## Bereiche (1-6)

| # | Bereich | Insights (sehen) | Aktionen (troubleshooting) | Quelle |
|---|---|---|---|---|
| 1 | **Betrieb** | Nachtlauf-Status, 8 Sonden/Wächterdienst, Dokument-Rückstau, Datenfrische je Land | Lauf/Sonde anstoßen, Rückstau erklären | `api/intern/lauf`, `waechterlauf.sh`, `letzter_lauf.txt` |
| 2 | **Datenqualität** | Review-Queue, Entity-Merge-Kandidaten, Dubletten, Quality-Flags, Abdeckung je Land/Portal | Merge bestätigen/ablehnen, Flag klären | Gold-Tabellen, `curated/` |
| 3 | **Konten & Profile** | Orgs, User, Profile, Seats, Pläne, Quote/Nutzung | **Firmensuche**, **Passwort-Reset (Mail)**, Plan/Seats setzen, Identitäts-Claim prüfen | Supabase, `api/intern/claims` |
| 4 | **Vertrieb & Outreach** | Zielliste, Schmerz-Signale, Outreach-Log, Trefferquote | Firmensuche, Landing/Token erzeugen, Ansprache loggen | `api/intern/{firmen,landing,outreach}` |
| 5 | **Kuratierung** | `curated/`-CSVs (Aliasse, Regionskorrekturen, gesperrte Hosts, Portale ohne Abrufer), Doktypen | Eintrag hinzufügen/ändern | `curated/`, `govisor/doctypes.py` |
| 6 | **LLM & Kosten** | OpenRouter-Guthaben & Ausgaben, Modellwahl, Geldwache-Reserve, Analyse-Rückstau | Modell umstellen, Reserve setzen | LLM-Konfig, `docs/modellwahl-und-anbieterboden.md` |

### Zusätze (Sven), eingeordnet
- **Firmensuche** — existiert (`intern/firmen`: Sitz/Name + Schmerzsignale), sichtbar in
  Bereich 3 und 4.
- **Passwort-Reset** — Bereich 3, als ausgelöste Reset-Mail (nie Passwort setzen).
- Ausrichtung **Insights + Troubleshooting** ist über alle Bereiche der Leitgedanke: jede
  Zeile hat eine „sehen"- und, wo sinnvoll, eine „handeln"-Spalte.

## Inhalte je Bereich (Detail)

Stand 2026-09-30, an den vorhandenen Artefakten festgemacht. `I` = Insight (lesen),
`A` = Aktion (handeln). Quelle ist die reale Datei/Tabelle/Skript, aus der der Punkt speist.

### 1 Betrieb & Monitoring

| Element | Typ | Inhalt | Quelle |
|---|---|---|---|
| Nachtlauf-Status | I | letzter Eintrag: fertig/ABGEBROCHEN, Dauer, Warnungen, Maschinenlast | `data/logs/letzter_lauf.txt`, `api/intern/lauf` (live) |
| Ertragsverlauf | I | Leads/Analysen je Nacht, Trend | `data/logs/ertrag.json`, `ertrag_verlauf.jsonl` |
| Maschinen-Last | I | Auslagerung, freier Speicher, Einlagerungs-Spitzen | `data/logs/maschine-*.tsv` |
| Sonden-Ampel | I | 8 Verdrahtungs-Sonden + Wächterdienst grün/rot | `scripts/waechterlauf.sh`, `pruefe_verdrahtung.py` |
| Dokument-Rückstau | I | echte offene Zahl je Abrufer (seit KENNUNG-Fix), zweite Liste (warum nicht geholt) | `scripts/rueckstau.py` |
| Qualitätsbericht | I | tägliche Kennzahlen mit Vortageswert | `scripts/qualitaet_bericht.py` |
| Lauf/Sonde/Abrufer anstoßen | A | einzelnen Schritt manuell auslösen (nur handeln, wenn Sperre frei) | Worker-Dienst |

### 2 Datenqualität

| Element | Typ | Inhalt | Quelle |
|---|---|---|---|
| Review-Queue | I | harte Fehler als Worklist mit Beleg-Link | `review_queue.parquet` |
| Entity-Merge-Kandidaten | I | vorgeschlagene/geflaggte Zusammenführungen + Urteil | `entity_merge_candidates`/`_urteil`/`_map.parquet` |
| Entity-Belege | I | kennnummer/anschrift/maildomain/widerspruch/unbelegt | `entity_beleg.parquet`, `entity_impressum_beleg.parquet` |
| Dubletten | I | Notice- und Dokument-Paare | `notice_duplicates`, `document_duplicates.parquet` |
| Quality-Flags | I | wert_sentinel, frist_vor_pub, datum_absurd … | `quality.parquet` |
| Abdeckung je Land/Portal | I | Text-/Dokumentabdeckung, Lücken | abgeleitet aus Gold + `pruefe_vollstaendigkeit.py` |
| Merge bestätigen/ablehnen | A | schreibt Urteil bzw. `curated/DE_entity_aliases.csv` (greift beim nächsten Gold-Lauf) | `curated/` |

### 3 Konten & Profile

| Element | Typ | Inhalt | Quelle |
|---|---|---|---|
| Orgs/User/Profile/Seats/Pläne | I | Übersicht nach dem Multi-Profil-Modell (s. `mehrfachprofile-konzept.md`) | `organizations`, `profiles`, `user_profiles` |
| Nutzung/Quote | I | Analyse-Kontingent, Bausteinnutzung je Konto | `profile_block_usage`, `user_*` |
| Identitäts-Claims | I | offene Prüfanträge + Domain-Belege | `identity_claims`, `domain_proof` |
| Nutzer-Aktivität (Support) | I | Watchlist, Lead-Status, Alerts — nur für Troubleshooting | `user_watchlist`, `user_lead_status`, `user_alerts` |
| Firmensuche | A | nach Sitz/Name + Schmerzsignale | `scripts/firmen_suche.py`, `api/intern/firmen` |
| Passwort-Reset | A | **Reset-Mail auslösen** (nie Passwort setzen) | Supabase Admin |
| Plan/Seats setzen, Claim bestätigen | A | Konto-Zustand ändern, Identitäts-Claim entscheiden | Supabase, `api/intern/claims` |
| DSGVO-Export anstoßen | A | Datenauskunft je Nutzer | `user_data_export` |

⚠ **Datenschutz**: fremde Nutzerdaten nur für Support, jeder Zugriff ins Audit-Log,
Minimalprinzip.

### 4 Vertrieb & Outreach

| Element | Typ | Inhalt | Quelle |
|---|---|---|---|
| Zielliste | I | Schmerz-Priorisierung (S1/S2 + Ad-hoc) | `scripts/zielliste.py`, `data/zielliste.csv` |
| Firmensuche | A | Sitz/Name + Signale (wie B3) | `scripts/firmen_suche.py` |
| Outreach-Log | I | 12-Monats-Sperre + Trefferquote | `scripts/outreach_log.py` |
| Landing/Token erzeugen | A | `/t/<token>` für eine Zielfirma | `scripts/export_outreach.py`, `api/intern/landing` |
| Ansprache loggen | A | Kontakt protokollieren (setzt Sperre) | `api/intern/outreach` |

### 5 Kuratierung

| Element | Typ | Inhalt | Quelle |
|---|---|---|---|
| Entity-Aliasse | I/A | belegte Umbenennungen/Fragmente | `curated/DE_entity_aliases.csv` |
| Regionskorrekturen | I/A | je Land | `curated/{DE,AT,CH}_region_korrektur.csv` |
| Kategorie-Korrekturen | I/A | Branchen-Zuordnung | `curated/DE_kategorie_korrektur.csv` |
| Gesperrte Hosts | I/A | robots/Anmeldung, kein Abruf | `curated/hosts_gesperrt.csv` |
| Portale ohne Abrufer | I/A | bekannte Lücken | `curated/portale_ohne_abrufer.csv` |
| Vergabestellen-Worklist | I/A | Kuratierungs-Aufgaben | `curated/vergabestellen_kuratierung_worklist.csv` |
| Löschprotokoll | I | Quarantäne/Löschungen (Audit) | `curated/geloescht_*.csv` |
| Doktyp-Regeln | I | Name/VHB/Inhaltsprobe | `govisor/doctypes.py` |

⚠ Änderungen wirken erst beim **nächsten Gold-/Silber-Lauf**; vor dem Speichern gegen das
CSV-Schema validieren.

### 6 LLM & Kosten

| Element | Typ | Inhalt | Quelle |
|---|---|---|---|
| OpenRouter-Guthaben & Reserve | I | Geldwache-Status (der aktuelle Blocker) | `govisor/llm.py`, `analyze_docs.py` |
| Ausgaben je Lauf/Modell | I | Kostenbuch, Bericht | `govisor/kostenbuch.py`, `scripts/kostenbericht.py` |
| Modellwahl + Anbieterboden | I | aktives Modell, `:floor`-Boden | `govisor/modellkatalog.py`, `docs/modellwahl-und-anbieterboden.md` |
| Analyse-Rückstau | I | wartende Auswertungen, Frische von `doc-analysis.json` | `scripts/analyze_docs.py` |
| Modell umstellen, Reserve/Limit setzen | A | Geldwache-Parameter | LLM-Konfig |

⚠ Der Secret-Key (`.secrets/openrouter.key`) bleibt serverseitig; das Admin-Center zeigt
Guthaben und Ausgaben, **nie den Schlüssel**.

## Geparkt: Bereich 7 — Agenten-Werkstatt (ausgeklammert am 2026-09-30)

Bewusst **vorerst nicht** im Umfang. Festgehalten für später, damit die Idee und ihre
Sicherheitsleitplanke nicht verloren gehen:

> Das Portal öffnet eine **Agenten-Sitzung gegen das Repo**, die einen Fix erarbeitet und als
> **Pull Request mit Tests** vorlegt; ein Mensch merged. **Nie Auto-Deploy**, streng gegated
> (nur Admin, eigenes Netz), Audit-Log. Setzt den Worker-Dienst (Weg C) voraus und wäre als
> **letztes** zu bauen, wenn 1-6 stehen.

## Bau-Reihenfolge

1. Umfang 1-6 bestätigt (dieses Dokument). ✓
2. Pro Bereich die konkrete Inhalts-/Aktionsliste ausdefiniert (Abschnitt „Inhalte je
   Bereich"). ✓ 2026-09-30
3. Bau. **Bereich 1 (Betrieb-Cockpit) GEBAUT 2026-09-30** auf der bestehenden `/intern`-
   Flaeche (istAdmin-gated), unabhaengig vom Deploy-Startschuss: Seite `app/intern/betrieb`,
   API `app/api/intern/betrieb` (Sonden-Ampel aus dem Waechter-Log + LLM-Guthaben aus
   `.llm_stand.json`) plus dem vorhandenen `/api/intern/lauf` (Nachtlauf, Ertrag/Bestand,
   Dokument-Trichter, Datenqualitaet). Datenschicht gegen die echten Dateien geprueft
   (12 Sonden/4 Befunde, Guthaben 0,93 $, 3.946 wartend); UI tsc-sauber. ⚠ Laufzeit-Ansicht
   braucht eine Admin-Session (Middleware sperrt /intern auf istAdmin) — von mir nicht
   einsehbar. Wandert mit Weg C spaeter auf den Worker-Dienst.
   **Bereich 3 (Konten & Profile) GEBAUT 2026-09-30**: Seite `app/intern/konten`, API
   `app/api/intern/konten` (Orgs mit Mitgliedern/Seats/Profilen/Plan; Seats/Profile/Plan
   setzen als manueller Hebel; Passwort-Reset-Mail) + die vorhandene `/api/intern/claims`
   (Identitaets-Ansprueche freigeben/ablehnen). Aggregation gegen die echte DB geprueft
   (13 Orgs, u. a. CANCOM SE). **Bereich 2 (Datenqualitaet) GEBAUT 2026-09-30**: Seite `app/intern/qualitaet`, API
   `app/api/intern/qualitaet` spawnt den Lese-Helfer `scripts/qa_uebersicht.py` (DuckDB
   ueber die Gold-QA-Parquets): Review-Queue + Flags, Quality-Flags im Bestand,
   Entity-Merge-Kandidaten/Urteile, Dubletten (Notice+Dokument), Laenderwaehler. Nur
   Ansicht; Merge-Entscheidungen schreiben nach curated/ und kommen mit Bereich 5.
   Naechste Bereiche: 6 (LLM&Kosten), 5 (Kuratierung), 4 (Vertrieb ausbauen).
