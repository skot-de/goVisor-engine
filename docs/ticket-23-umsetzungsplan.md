# Ticket #23 — Vergabeunterlagen-Analyse & Bausteinbibliothek: Umsetzungsplan

> **Status (2026-07-31): alle 6 Phasen gebaut, 207 Tests grün.** Backend/Logik lokal-first
> vollständig + getestet; Deploy-Schicht (Supabase-Verschlüsselung Ebene B, Live-Verdrahtung von
> Quote/Zeitkanal, Malware-Scanner, Ebene-B-UI/Import-Flow) bleibt fürs Deployment. Commits
> `f328818` (P1) · `cbad85d` (P2) · `9bf9dd0` (P3) · `3fce1fd` (P4) · `90faa00` (P5) · `8eb9451` (P6).
> Neue Module: `govisor/{doctypes,doctax,docextract,docparse,docupload,pii,blocks,docsafety}.py`,
> `supabase/0006_doc_analysis.sql`, `scripts/eval_extraction.py`, umgebaute `analyze_docs.py`/
> `process_upload.py`, Checklisten-UI in `explorerCore.js`.


Spec: `INPUT/v1 Features/add/govisor-ticket-23-dokumentenanalyse.md`. Fundierung: Struktur-Studie
([dokument-struktur-studie.md](dokument-struktur-studie.md)) — **Q1b bindend: kein Standardformular-
Layer → Verarbeitung pro Dokument, kein Template-Cache.** Der Hebel ist Auswahl + Parser + Schema.

**Arbeitsweise (Projekt-Konvention):** local-first. Extraktion/Parser/Checklisten-Erzeugung laufen
gegen `data/docs/DE/doc_text.parquet` (241 Vorgänge liegen lokal) und sind sofort testbar. Das
Supabase-Datenmodell + Mehrbenutzer-Sicherheit (Ebene A/B, RLS, Verschlüsselung, Zeitkanal, Quote)
ist die **Deploy-Schicht** — gebaut und gegen das Dev-Sample geprüft, scharf erst beim Deployment.

## Ist-Stand (Prototyp, gemessen)
- `govisor/docpipe.py` — ZIP→Volltext (`iter_docs`, `_EXTRACT`, `_pdf_text`, `_KNOWN_NOEXTRACT`).
- `govisor/docsignals.py` — regelbasierte Signale (Bürgschaft/Bindefrist/Zuschlagsgewichte) → `doc_signals.parquet`.
- `scripts/analyze_docs.py` — **ein** generischer LLM-Call → {ampel, ko_kriterien, eignung, zuschlag, fristen, aufwand, vorausfuellbar} → `web/data/doc-analysis.json`.
- `scripts/process_upload.py` — Upload-ZIP → gleiche Analyse. `govisor/llm.py` — Multi-Key-Fallback (gemini-2.5-flash).
- Frontend: „Unterlagen"- + „Vergabe-Analyse"-Tab, `lead-docs`/`lead-detail`-API, `DetailPanel.tsx`.
- **Fehlt komplett:** typisiertes Schema je Doktyp, Zitat-Verifikation, Parser-Schiene (GAEB/Formfelder/XLSX), Priorisierung/Token-Deckel, das 7-Tabellen-Datenmodell, Upload-Guards, Bausteinbibliothek, Sicherheits-Ebenentrennung, Eval-Datensatz.

---

## Phase 1 — Extraktions-Kern (§6a) · Fundament, backend, testbar
**Ziel:** aus generischem LLM-Call → typisierte, belegpflichtige Extraktion je Dokumenttyp.

**Bau-Schritte:**
1. **Anforderungs-Taxonomie** (`govisor/doctax.py`): fester Enum `req_type` (`referenz_mindestwert`, `mindestumsatz`, `zertifikat`, `ausschlussgrund`, `zuschlagskriterium`, `frist`, `vertragsstrafe`, `haftung`, `laufzeit`, …) + `theme`-Mapping (§9.4). Speist #15.
2. **Typisierte Schemata je Doktyp** (§6a.3): fünf JSON-Schemata (Eignung/Bewerbungsbed., Zuschlag, LB, Vertrag, Aufforderung), je 2–3 Few-Shot-Beispiele aus echten Unterlagen. Mindestfelder: `req_type, value, unit, quote, source_file, source_page, marking`.
3. **`govisor/docextract.py`** — je Doktyp eine Aufgabe (eigener Prompt+Schema) statt Universalabfrage. Structured-Output erzwingen; schema-invalide Antwort → 1× wiederholen, sonst verwerfen (§6a.1).
4. **Zitat-Verifikation** (§6a.2, Pflicht): jedes `quote` normalisiert (Whitespace/Umbrüche) im Quelltext suchen; nicht gefunden → Eintrag **verwerfen**. `rejected_items`-Zähler je Analyse.
5. **`analyze_docs.py` umbauen** auf die typisierte Schiene; Ausgabe erweitert um `marking`, `quote`, `source_page`, `rejected_items`, `token_cost`.
6. **Tests:** Taxonomie-Vollständigkeit, Schema-Validierung, Zitat-Verifikation (echtes Zitat findet, erfundenes verwirft) an 3 lokalen Vorgängen.

**Deckt AK:** 24, 25, 26, 27. **Aufwand:** mittel (2–3 Bausteine + Tests). **Abhängig:** nichts.

## Phase 2 — Verarbeitungs-Pipeline (§6) · pure Code + gezielte LLM-Auswahl
**Ziel:** billige Schienen zuerst, LLM nur für die priorisierten ~5 Dokumente.

**Bau-Schritte:**
1. **Klassifikation** (§6.1-2): Dateiname-Regel (69 % Trefferquote, Doktyp-Muster aus der Studie) + Inhaltsprobe für den Rest. `doctype`-Feld existiert schon in `docpipe`, härten.
2. **Parser-Schiene** (§6.2): (a) **GAEB** D81/D83/X83 → Positionen/Mengen/Einheiten/Texte (84 % im Bau!); (b) **PDF-Formfelder** (pypdf `get_fields`, schon in der Studie genutzt) → Feldnamen/Typen/Pflicht; (c) **XLSX** → Tabellenstruktur/Positionen (**keine Werte eintragen**). Wo Parser greift, kein LLM.
3. **Priorisierte Extraktion** (§6.1): Reihenfolge Eignung→Zuschlag→LB→Vertrag→Aufforderung; **200k-Token-Deckel**, nach Priorität abschneiden, Abgeschnittenes ausweisen.
4. **Vollständigkeitsprüfung** (§4.3/§6.1): Erwartungswerte aus Q1a (4-Typen-Kern 70–91 %) → fehlende Typen benennen.

**Deckt AK:** 2, 13, 14. **Aufwand:** mittel-hoch (GAEB-Parser ist der Brocken). **Abhängig:** Phase 1 (Schema).

## Phase 3 — Datenmodell + Upload-Guards (§4/§5/§13) · Deploy-Gerüst
**Ziel:** die Produktions-Tabellen + sichere Aufnahme.

**Bau-Schritte:**
1. **7 Tabellen** in `scripts/export_supabase.py`-Registry: `doc_requirement_types`, `doc_packages`, `doc_files`, `doc_checklists`, `doc_checklist_items` (Ebene A) · `profile_text_blocks`, `profile_block_usage` (Ebene B). DDL aus Schema generiert (bestehendes Muster).
2. **RLS** (§13): Ebene A lesbar für `authenticated`, schreibbar nur Systemrolle; Ebene B profilgebunden. `originaldokumente werden nicht persistiert` — nur Hash/Metadaten/Ergebnis.
3. **Upload-Guards** (§4.2/§5): Grenzwerte (500 MB/250 Dateien/100:1/Tiefe 3/20 pro Std.), Malware-Scan, **Zip-Slip**-Prüfung, **Eigen-Angebot-Erkennung** (§5-3), Lead-Zuordnung (Titel/Vergabestelle/Aktenzeichen/CPV), **Paket-Hash-Dedup** (§5-5).
4. **Erkennungsansicht** (§4.3) + Quotenhinweis (§4.4).

**Deckt AK:** 1, 3, 4, 16. **Aufwand:** hoch. **Abhängig:** Phase 1/2 (doctype, token_cost).

## Phase 4 — Checklisten-UI (§7) · sichtbarer Nutzen
**Ziel:** die Extraktion als Bieter-Checkliste im Frontend.

**Bau-Schritte:** Eintrag mit Thema · Zitat+Fundstelle · editierbarem Feld · Kombi-Button (§7.1); 4 Kennzeichnungsstufen (§7.2); Kopf mit Dokumentenstand+Haftung (§7.3); Zuschlagskriterien-nicht-gefunden-Eintrag (§7.4); „Weitere Dokumente"+Einordnen (§7.5); Versionswarnung passiv+aktiv (eForms `ProcurementDocumentsChangeIndicator`, §7.6); Los-Abschnitte nur bei erkennbarem Bezug (§8).

**Deckt AK:** 6, 7, 8, 9, 10, 11, 12. **Aufwand:** mittel-hoch (Frontend). **Abhängig:** Phase 1/3.

## Phase 5 — Bausteinbibliothek + Import (§9-11) · Ebene B
**Ziel:** Firmentexte, Alt-Angebot-Import mit PII-Schwärzung, Ergebnisdaten.

**Bau-Schritte:** Bibliothek profilgebunden, ohne Analyse befüllbar, Bearbeitungszuschreibung (§9.1-2); Zuordnung Verwendungshistorie→Thema→Keywords (§9.3), feste Themen-Taxonomie (§9.4); **Import** mit `Original nie speichern` (§10.2) + **PII-Erkennung/Platzhalter vor Speichern** (§10.3, Pflicht) + neutrale Herkunft (§10.4); **Ergebnisdaten** nur nach gesonderter Zustimmung, Widerruf (§11, Zweckbindung).

**Deckt AK:** 15, 16, 17, 18, 19. **Aufwand:** hoch (PII-Schwärzung + Zweckbindung heikel). **Abhängig:** Phase 3.

## Phase 6 — Sicherheit + Free/Pro + Eval (§12/§14/§6a.4) · Härtung
**Ziel:** die Mehrbenutzer-Sicherheit + Qualitätssicherung.

**Bau-Schritte:** Ebenentrennung über getrennte Service-Identitäten (§12.1, Rechte statt Konvention); geteilte-Checkliste-Schutz — Plausibilitätsabgleich + **Bestätigungsschwelle** (§12.2); **Zeitkanal** angleichen (§12.4, 8–12 s); Prompt-Injection (§12.5, Doku als Daten, keine Tool-Rechte); nebenläufige Uploads sperren (§12.6); Envelope-Verschlüsselung Ebene B (§12.3); Free/Pro-Quote (§14); **Eval-Datensatz** (§6a.4): Teil 1 automatisch (Frist/Wert/Vergabestelle/CPV gegen TED), Teil 2 **30 Vorgänge manuell** (branchenverteilt) → Vollständigkeit/Korrektheit/Halluzination; jede Änderung läuft dagegen.

**Deckt AK:** 5, 20, 21, 22, 23, 28. **Aufwand:** hoch. **Abhängig:** alle.

---

## Empfohlene Reihenfolge & Meilensteine
1. **Phase 1** (Extraktions-Kern) — sofort local-first, macht die bestehende Analyse belastbar. **Größter Qualitätshebel, kleinste Abhängigkeit.**
2. **Phase 2** (Parser-Schiene) — senkt Kosten, GAEB im Bau ist der sichtbare Gewinn.
3. **Phase 4** (Checkliste-UI) vorgezogen vor Phase 3 möglich, wenn ein sichtbares Demo wichtiger ist als das Produktions-Datenmodell (UI kann zunächst auf die lokalen JSON-Overlays setzen).
4. **Phase 3 → 5 → 6** für die Produktions-/Deploy-Reife.

**Offen (Spec §16, vor Produktiv):** Modellwahl an §6a.4 messen; Rechtsprüfung Ebene-A-Wiederverwendung; Free-Grenze aus realen `token_cost`; Q4-52%-Vorbehalt mit LLM gegenprüfen.

**Nicht im Umfang (Spec §1):** Dokumente ausfüllen (AK 23).
