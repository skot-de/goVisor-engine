#!/bin/bash
# ============================================================================
# goVisor — Tages-Lead-Runner (lokal auf dem Mac, Daten auf der externen Platte).
#
# Holt täglich die frischen unterschwelligen DE-Leads (DÖE-Live-API), baut die
# Lead-Schicht mit heutigem Stichtag neu (Fristen/Auslauf, abgelaufene Leads raus)
# und pusht den Lead-Ausschnitt in Supabase (Upsert + Prune) → die Kunden-App auf
# Vercel sieht die frischen Leads. Die Roh-/Volldaten bleiben komplett lokal.
#
# Kadenz-Erwartung: DÖE (unterschwellig) + as-of täglich frisch. Oberschwellig
# (TED-Monatspakete) NICHT — das läuft weiter monatlich über `ingest`.
#
# Aufruf manuell:  scripts/daily_leads.sh
# Scheduler:       ~/Library/LaunchAgents/de.skot.govisor.daily.plist (launchd)
# ============================================================================
set -uo pipefail

ROOT="/Users/svko_macmini/PROJEKTE/claude_code/C09_govisor"
cd "$ROOT" || { echo "Repo-Verzeichnis fehlt: $ROOT"; exit 1; }

LOG_DIR="$ROOT/data/logs"
LOCK="$ROOT/data/.daily_leads.lock"
PY="python3"
MONTH="$(date +%Y-%m)"
TODAY="$(date +%Y-%m-%d)"

# --- Lock: keine Überlappung, falls ein Lauf noch dreht (atomar via mkdir) ---
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date '+%F %T') Lauf läuft bereits (Lock $LOCK) — abgebrochen." >&2
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

# --- Daten-Guard: externe Platte / Symlink muss aufgelöst sein ---
if [ ! -e "$ROOT/data/gold/DE/lead_export.parquet" ]; then
  echo "$(date '+%F %T') FEHLER: data/ nicht verfügbar (externe Platte nicht gemountet?) — abgebrochen." >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/daily-$TODAY.log"
exec > >(tee -a "$LOG") 2>&1
echo "════════════════════════════════════════════════════════════════"
echo "goVisor Tageslauf  $(date '+%F %T')  (Monat $MONTH, Stichtag $TODAY)"
echo "════════════════════════════════════════════════════════════════"

step() { echo ""; echo "▶ $(date '+%T')  $*"; }
SECONDS=0

# --- Supabase-Creds aus .secrets laden (URL Zeile 1, Service-Key Zeile 2) ---
if [ -f "$ROOT/.secrets/supabase.txt" ]; then
  export SUPABASE_URL="$(sed -n '1p' "$ROOT/.secrets/supabase.txt" | tr -d '[:space:]')"
  export SUPABASE_SERVICE_KEY="$(sed -n '2p' "$ROOT/.secrets/supabase.txt" | tr -d '[:space:]')"
fi

# 1) ALLE Quellen tagesfrisch. Vorher lief hier NUR DÖE — und weil DÖE fast
#    ausschließlich kommunalen Bau/Wartung abdeckt, sah nur der Bau-Grundraum gesund aus.
#    Gemessen am 2026-08-10: DÖE bis 2026-08-07, TED nur bis 2026-07-22 (19 Tage alt),
#    CH und AT bei 2026-07-28. Der „Vorrat" an offenen Ausschreibungen (offen ÷ Veröffent-
#    lichungen pro Monat, sollte ~1 sein) lag entsprechend: Bau 1,53 · IT 0,42 · Ingenieur
#    0,26. Kein Anzeigefehler — die Leads kamen schlicht zu spät herein.
step "TED-Live DE (Search API, schließt die Monatspaket-Lücke)"
if $PY scripts/fetch_ted_live.py --workers 3; then
  echo "  TED-Live ok."
else
  echo "  ⚠ TED-Live fehlgeschlagen — Bestand bleibt auf dem Stand des Monatspakets."
fi

step "DÖE-Ingest (unterschwellig DE, --fetch laufend+Vormonat)"
if $PY -m govisor.cli ingest-doe --country DE --fetch --fetch-back 1 --force; then
  echo "  DÖE ok."
else
  echo "  ⚠ DÖE-Ingest fehlgeschlagen (API?) — fahre mit Gold/Export fort (as-of-Refresh bleibt wertvoll)."
fi

# CH bekommt BEIDE Quellen: simap (nationale Plattform, breiter) und TED-CHE (WTO-GPA-
# Kanal). Gemessen überschneiden sie sich zu 93,5 % — der Abgleich unten trennt den echten
# Zugewinn von der Dublette, sonst verdoppelte sich die Schweizer Liste ohne mehr Markt.
step "TED-Live CH"
$PY scripts/fetch_ted_live.py --country CH --workers 3 \
  && echo "  TED-CHE ok." || echo "  ⚠ TED-CHE fehlgeschlagen — CH bleibt auf simap allein."

step "simap.ch (CH)"
$PY -m govisor.cli ingest-simap --country CH --max-pages 30 --silver \
  && echo "  simap ok." || echo "  ⚠ simap.ch fehlgeschlagen — CH bleibt auf altem Stand."

# AT bekommt wie CH beide Kanäle: OffeneVergaben.at (national, auch unterschwellig) und
# TED-AT (EU-Schwelle). Anders als bei CH braucht es hier KEINEN Backfill — die TED-AT-
# Historie liegt über die Monatsarchive vollständig vor (180.061 Notices ab 2004, gegen die
# TED-API auf 99,8–100 % geprüft). Gefehlt hat allein der Tagesabruf: das Monatsarchiv
# erscheint mit Verzug, dadurch stand TED-AT auf dem Stand vom 29. Juni.
step "TED-Live AT"
$PY scripts/fetch_ted_live.py --country AT --workers 3 \
  && echo "  TED-AT ok." || echo "  ⚠ TED-AT fehlgeschlagen — AT bleibt auf OffeneVergaben allein."

step "OffeneVergaben.at (AT)"
$PY -m govisor.cli ingest-atverg --country AT --silver \
  && echo "  atverg ok." || echo "  ⚠ OffeneVergaben.at fehlgeschlagen — AT bleibt auf altem Stand."

# DTVP (Deutsches Vergabeportal) — WIEDER AKTIV seit 2026-08-13.
#
# Der Connector lag auskommentiert, weil er beim ersten Vollauf rund zwei Drittel Dubletten
# in die Lead-Liste geschrieben haette (gemessen an den ersten 60 Vorgaengen: 44 echte
# Dubletten, hoechstens 4 neu). Die Notiz von damals verlangte ein `dedupe_dtvp_sources.py`
# nach dem Muster von AT/CH. Das gibt es bewusst NICHT — die zentrale Firewall unten deckt
# den Fall generisch ab, und ein viertes quellenspezifisches Skript waere genau die
# Zersplitterung, die sie ersetzen soll.
#
# ⚠ REIHENFOLGE: DTVP muss VOR der Firewall laufen. Sie liest Silber; kommt der Import
# danach, sieht sie die neuen Saetze erst am Folgetag und der Ausschluss greift einen Lauf
# zu spaet — also genau dann, wenn die Dubletten schon im Produkt stehen.
#
# Ausgeschlossen wird in `gold._redundante_zweitquelle_sql`, und nur unter der Bedingung,
# dass der Master heute noch ein brauchbarer Lead ist. Gemessen an den 60 vorhandenen
# Saetzen: 45 mit Kaeufer-Beleg als Dublette erkannt, alle 45 mit laufendem Master, 15
# bleiben als eigene Leads. Die Master-Pruefung greift bei dieser Menge also ins Leere —
# sie ist fuer den Vollausbau (~6.800 Vorgaenge) da.
#
# NOCH NICHT geholt: der VOL-Bereich (8.640 offene Treffer) braucht CPV-Codes, die die
# Suche als 2-stellige Division ablehnt; dazu SEKTVO (779), OTHER (214), ExAnte, ExPost.
step "DTVP-Bekanntmachungen (VOB, unterschwellig)"
$PY -m govisor.dtvp --regeln VOB --typen Tender --max-seiten 40 --stop-nach-bekannten 40 --silber \
  || echo "  ⚠ DTVP-Import fehlgeschlagen — fremdes Portal, der Lauf geht ohne weiter."

# NETSERVER (Administration Intelligence) — vier Laenderportale mit einer Software:
# Bremen, Sachsen, Mecklenburg-Vorpommern, Baden-Wuerttemberg. Hessen/HAD ist vorgesehen,
# aber der Suchendpunkt antwortet unter dem ueblichen Servlet-Namen mit 404 (offen).
#
# Was diese Quelle liefert und was nicht: die TREFFERLISTE ist oeffentlich (Titel,
# Verfahrensart, Rechtsrahmen, Frist, bei drei von vier auch die Vergabestelle). Die
# DETAILSEITE und damit die Vergabeunterlagen liegen hinter einer Anmeldung — der einzige
# Klick-Handler in der Bremer Liste ist `LoginControllerServlet`. Das Modul holt deshalb
# ausschliesslich Bekanntmachungen; Unterlagen waeren eine Vertrags-, keine Technikfrage.
#
# ⚠ REIHENFOLGE wie bei DTVP: VOR der Firewall. Sie liest Silber; kaeme der Import danach,
# griffe der Dubletten-Ausschluss einen Lauf zu spaet.
#
# ⚠ `--neu-einlesen` gehoert NICHT in den Tageslauf. Bronze speichert die geparste Zeile,
# nicht das rohe HTML — nach einer PARSER-Aenderung muss der Schalter einmal von Hand
# laufen, sonst bleiben die alten Saetze unveraendert stehen (genau so meldete MV nach dem
# Vergabestellen-Fix weiter 0 % Stellen). Im Tageslauf waere er nur unnoetige Last.
step "NetServer-Bekanntmachungen (HB/SN/MV/BW, ober- und unterschwellig)"
$PY -m govisor.netserver --portale hb,sn,mv,bw --kategorien tender,vorinfo,zuschlag --silber \
  || echo "  ⚠ NetServer-Import fehlgeschlagen — fremde Portale, der Lauf geht ohne weiter."

# DUBLETTEN-FIREWALL. Eine Pruefung fuer ALLE Quellen eines Landes. Sie hat am 2026-08-13
# `dedupe_at_sources.py` und `dedupe_ch_sources.py` abgeloest — beide geloescht, ihre
# Verbraucher (Marktpuls, die zwei Alt-Bruecken) lesen jetzt `notice_duplicates`.
#
# `--alle-arten` ist Pflicht: mit nur `cn`/`pin` fehlen die ZUSCHLAEGE, und die machten in
# AT 3.403 von 4.345 der Treffer aus, die frueher nur das Quellskript fand. Marktpuls zaehlt
# Publikationen je Jahr und wuerde AT/CH sonst doppelt zaehlen.
#
# `--ab-jahr 2004` = VOLLE HISTORIE fuer alle drei Laender. Bis 2026-08-14 stand hier ein
# Notfenster (DE:2026 AT:2024 CH:2024), weil die Historie nicht durchlief — AT ab 2019 brach
# nach 45 Minuten ab. Das lag nicht an der Datenmenge, sondern daran, dass das
# ±FENSTER_TAGE-Fenster erst NACH der Kandidatenbildung griff: gepaart wurde quer ueber 22
# Jahrgaenge. Seit dem Zeitscheiben-Umbau laeuft der Abgleich jahrgangsweise:
#
#   AT   413.872 Saetze   >45 min Abbruch →   40 s ·  128.216 Paare
#   CH   120.434 Saetze                   →    8 s ·   18.465 Paare
#   DE 2.215.840 Saetze                   →  827 s ·  115.198 Paare
#
# DE kostet also rund 14 Minuten je Nacht. Das ist der Preis dafuer, dass die
# Marktpuls-Jahresschichten ueberhaupt bereinigt sind — mit dem Notfenster blieben AT
# 2019-2023 und DE 2023-2025 unbereinigt, und zwar lautlos.
#
# Der WUNSCHWERT waere der Quellenstart (atverg 2019, DOeE 2023, simap 2024, DTVP ~2024) —
# davor kann es keine Quellen-Dublette geben. CH erreicht ihn, DE und AT nicht.
#
# ⚠ FOLGE, offen und bewusst in Kauf genommen: in den Marktpuls-Jahresschichten bleiben
# AT 2019–2023 und DE 2023–2025 unbereinigt, dort zaehlen Quellen-Dubletten doppelt. Der
# echte Fix ist nicht ein groesseres Zeitfenster, sondern der Umbau des Abgleichs von der
# Python-Schleife auf DuckDB-SQL (Kandidaten + Enthaltung als Join). Bis dahin ist die
# Zahl hier die Grenze des Machbaren, nicht die des Gewollten.
#
# Gemessen 2026-08-13, Paare mit Kaeufer-Beleg / gesammelte Anreicherungswerte:
#   DE   6.116 Paare ·   976 mit Kaeufer-Beleg ·    21 Anreicherungswerte
#   AT   5.421 Paare · 3.282 mit Kaeufer-Beleg · 3.703 Werte (2.614 NUTS, 1.072 Fristen)
#   CH   2.874 Paare · 2.525 mit Kaeufer-Beleg ·   811 Werte
# AT/CH liegen weit vor DE, weil TED und die nationale Quelle sich dort zu ~93 % ueberlappen
# UND den Kaeufer fast gleich schreiben (98 % Beleg gegen 57 % in DE).
#
# ⚠ REIHENFOLGE: MUSS vor dem Gold-Rebuild laufen. `build_lead_deadline` liest
# `notice_enrichment.parquet`; laeuft die Firewall danach, sind die uebernommenen Fristen
# erst am naechsten Tag im Produkt. Die Datei ist optional — fehlt sie, verhaelt sich der
# Wasserfall wie vorher, es gibt also keine harte Abhaengigkeit, nur eine zeitliche.
#
# Sie MARKIERT und reichert an; geloescht wird an genau EINER Stelle, naemlich in
# `gold._redundante_zweitquelle_sql` (siehe DTVP weiter unten) — und dort nur, wenn der
# Master heute noch ein brauchbarer Lead IST. Ein Ausschluss ohne diese Bedingung wurde
# gemessen und verworfen: er haette 64 gueltige Leads gekostet, weil bei 61 davon die Frist
# des Masters abgelaufen ist und nur die der Dublette laeuft. Feld-Reichtum ist nicht
# Aktualitaet.
step "Dubletten-Firewall + Anreicherung (DE/AT/CH)"
for L in DE AT CH; do
  $PY -m govisor.dedupe --country "$L" --ab-jahr 2004 --alle-arten --anreichern \
    || echo "  ⚠ Dublettencheck $L fehlgeschlagen — Anreicherung bleibt auf altem Stand."
done

step "AT/CH-Gold (volle Pipeline, 26 Schritte je Land)"
$PY scripts/build_dach_gold.py --laender AT,CH --as-of "$TODAY" \
  && echo "  AT/CH-Gold ok." \
  || echo "  ⚠ AT/CH-Gold unvollstaendig — beide Laender bleiben auf dem letzten Stand."

# 2) Gold neu mit heutigem Stichtag — refresht Leads, Fristen, months_to_expiry. FATAL bei Fehler.
step "Gold-Rebuild (Leads mit Stichtag $TODAY)"
if ! $PY -m govisor.cli gold --country DE --as-of "$TODAY"; then
  echo "  ✖ Gold-Rebuild fehlgeschlagen — KEIN Supabase-Push (kein Halb-Stand nach oben)."
  echo "Abbruch nach ${SECONDS}s."
  exit 2
fi
echo "  Gold ok."

# 2b) VERGABEUNTERLAGEN — holen UND auswerten. Beides fehlte im Tageslauf: `fetch-docs` und
#     `signals-docs` gab es nur von Hand, entsprechend waren am 2026-08-13 gemessen 303
#     Vorgänge heruntergeladen, aber nur 13 ausgewertet. Herunterladen allein bringt nichts.
#     Beide Schritte sind unkritisch (|| true): die Portale sind fremde Systeme, ein Ausfall
#     dort darf den Tageslauf nicht abbrechen. Der Fetch ist idempotent (bereits geladene
#     Vorgänge werden übersprungen) und rate-limitiert; die Auswertung ist regelbasiert,
#     ohne LLM und ohne Kosten, also bedenkenlos täglich.
#     ⚠ NUR DE: der Fetcher deckt cosinex/DTVP ab. CH (simap.ch) verlangt für den Download
#     eine Registrierung — dort kommen wir legitim nicht heran; AT liefert als
#     `documents_url` nur die TED-Bekanntmachung. Siehe CLAUDE.md, EU-weit-Grundsatz.
step "Vergabeunterlagen holen (DE/cosinex, höflich + idempotent)"
$PY -m govisor.cli fetch-docs --country DE || echo "  ⚠ Fetch unvollständig — Auswertung läuft über den vorhandenen Bestand."
# ⚠ DIESER SCHRITT FEHLTE (gemessen 2026-08-13: 2.114 Vorgänge heruntergeladen, 241 mit Text).
#   `signals-docs` liest doc_text.parquet — das erzeugt AUSSCHLIESSLICH `index-docs`. Ohne
#   diese Zeile lief der Tageslauf formal durch: Fetch grün, Signale grün, aber die Signale
#   entstanden aus dem Textbestand des letzten Handlaufs. Genau die Falle, die wir beim
#   Fetch schon einmal hatten — Herunterladen allein bringt nichts, Auswerten ohne
#   Aufbereiten aber genauso wenig.
step "Unterlagen entpacken → Volltext-Index"
$PY -m govisor.cli index-docs --country DE || echo "  ⚠ Index unvollständig — Auswertung läuft über den vorhandenen Textbestand."
step "Unterlagen auswerten → Anforderungs-Signale"
if $PY -m govisor.cli signals-docs; then
  $PY scripts/export_doc_signals.py || echo "  ⚠ doc-signals.json nicht geschrieben."
else
  echo "  ⚠ Signal-Extraktion übersprungen."
fi

# Struktur AUS den Unterlagen: Leistungsverzeichnis (GAEB + Preisblatt) und Kriterienmatrix.
# Anders als die Signale oben ist das keine Ableitung aus Fließtext, sondern die Tabelle
# selbst — „wie viel wovon" und „woran werde ich gemessen". Läuft über den vorhandenen
# Archiv-Bestand, braucht kein Netz und keine LLM, also täglich unproblematisch.
# Reihenfolge ist Pflicht: extract_criteria liest doc_lv.parquet aus extract_positions.
step "Leistungsverzeichnisse + Kriterienmatrizen aus den Unterlagen"
if $PY scripts/extract_positions.py --country DE; then
  $PY scripts/extract_criteria.py --country DE || echo "  ⚠ Kriterien-Extraktion übersprungen."
  $PY scripts/export_doc_struktur.py --country DE || echo "  ⚠ doc-struktur.json nicht geschrieben."
else
  echo "  ⚠ LV-Extraktion übersprungen — doc-struktur.json bleibt auf dem letzten Stand."
fi

# 3) FRONTEND-DATEN — das ist, was die App tatsächlich liest (web/data/*.json über
#    lib/dataSource.ts). Fehlte bis 2026-08-10 im Tageslauf: Ingest und Gold liefen täglich,
#    aber die Oberfläche zeigte den Stand des letzten Handlaufs (zuletzt 10 Tage alt).
#    Läuft VOR dem Supabase-Push, weil das Frontend nicht davon abhängt.
# Marktpuls (Saisonalitaet + Jahres-Layer + aktuelle Lage) — laeuft VOR dem Frontend-Export,
# damit marktpuls.json denselben Stand traegt wie der Rest von web/data. Rein lesend auf
# Gold, kein Netz. Nicht fatal: ein Fehler hier darf den Tageslauf nicht abbrechen —
# die Anzeige kennzeichnet einen veralteten Stand ab 2 Tagen selbst.
#
# `--ab-jahr 2004` ist hier PFLICHT, nicht Kuer: der Schalter ist bewusst kein Default
# (Historie kostet Laufzeit), aber ohne ihn schriebe der Tageslauf die 5-Jahres-Fassung
# ueber die Historie — die Jahresansicht im Frontend fiele dann taeglich auf das kurze
# Fenster zurueck. Gemessen kostet die volle Achse 2004-2025 nur +4 s (40 s -> 44 s),
# weil der teure Attribut-Scan auf die eForms-Jahre gepinnt ist.
step "Marktpuls berechnen (Saison + Jahre 2004-2025 + Lage)"
$PY scripts/build_marktpuls.py --ab-jahr 2004 || echo "  ⚠ marktpuls.json bleibt auf dem letzten Stand — die Anzeige weist das aus."

step "Frontend-Daten exportieren (web/data)"
if $PY scripts/export_web_leads.py; then
  # ACHTUNG: export_web_leads.py schreibt plz-geo.json komplett neu und wirft dabei den
  # Stadt-Index `_cities` weg (Umkreissuche über Stadtnamen). Der Index MUSS direkt danach
  # neu gebaut werden, sonst findet die Stadtsuche im Frontend nichts mehr.
  $PY scripts/build_city_index.py || echo "  ⚠ Stadt-Index nicht gebaut — Umkreissuche über Städte fällt aus."
  $PY scripts/export_suppliers.py || echo "  ⚠ Lieferanten-Index nicht gebaut — Onboarding-Matching bleibt auf altem Stand."
  # Strategie-Aggregate: eigener Export, weil er 36 Monate braucht (unternehmerische
  # Planung), während die Lead-Liste auf 24 gedeckelt ist (Handlungsrelevanz). Fehlte
  # bisher im Tageslauf — /api/strategie las deshalb einen Stand vom 28. Juli.
  $PY scripts/export_strategie.py >/dev/null \
    || echo "  ⚠ Strategie-Aggregate nicht gebaut — die Strategie-Ansicht bleibt auf altem Stand."
  echo "  Frontend-Daten ok."
else
  echo "  ✖ Frontend-Export fehlgeschlagen — die App zeigt weiter den alten Stand."
fi

# 4) Schema selbstheilend migrieren (neue Parquet-Spalten → gov_*-Tabellen) via psql, dann pushen.
if [ -n "${SUPABASE_URL:-}" ] && [ -n "${SUPABASE_SERVICE_KEY:-}" ]; then
  step "Supabase-Schema-Migration (DDL aus aktuellem Parquet, idempotent via psql)"
  $PY scripts/export_supabase.py --table all --ddl-only
  REF="$(echo "$SUPABASE_URL" | sed -E 's#https?://([a-z0-9]+)\.supabase\.co.*#\1#')"
  if [ -f "$ROOT/.secrets/supabase_db.txt" ] && command -v psql >/dev/null 2>&1; then
    if PGPASSWORD="$(tr -d '[:space:]' < "$ROOT/.secrets/supabase_db.txt")" psql \
         -h "db.$REF.supabase.co" -p 5432 -U postgres -d postgres \
         -v ON_ERROR_STOP=1 -q -f docs/supabase_schema.sql >/dev/null; then
      # PostgREST hält einen eigenen Schema-Cache. Nach DDL kennt es neue Spalten erst
      # nach einem Reload — sonst PGRST204 („column not found in the schema cache"),
      # obwohl die Spalte in der Datenbank längst existiert (genau der Fehler am 09.08.).
      PGPASSWORD="$(tr -d '[:space:]' < "$ROOT/.secrets/supabase_db.txt")" psql \
        -h "db.$REF.supabase.co" -p 5432 -U postgres -d postgres -q \
        -c "NOTIFY pgrst, 'reload schema';" >/dev/null 2>&1 || true
      sleep 2
      echo "  Schema aktuell (Drift nachgezogen, PostgREST-Cache neu geladen)."
    else
      echo "  ⚠ psql-Migration fehlgeschlagen — versuche Push trotzdem."
    fi
  else
    echo "  ⚠ psql/DB-Passwort fehlt — Schema-Migration übersprungen (Push kann an Drift scheitern)."
  fi

  step "Supabase-Export (Upsert + Prune)"
  if $PY scripts/export_supabase.py --table all --prune; then
    echo "  Supabase-Push ok."
  else
    # KEIN exit: das Frontend liest gov_leads nicht (es liest web/data/*.json), und ein
    # gescheiterter Upload darf die nachfolgenden Schritte nicht mitreißen — vorher brach
    # der Lauf hier ab und gap_effects lief deshalb nie.
    echo "  ✖ Supabase-Push fehlgeschlagen — lokale Leads und Frontend-Daten sind aktuell, nur der Upload nicht."
    SUPA_FEHLER=1
  fi

  # 5) Lücken-Wirkung je Nutzer vorberechnen (#11 §7) — nicht fatal, Frontend hat On-Demand-Fallback.
  step "gap_effects vorberechnen (#11 §7)"
  $PY scripts/gap_effects.py || echo "  ⚠ gap_effects übersprungen (nicht kritisch)."
else
  echo "  ⚠ Keine Supabase-Creds (.secrets/supabase.txt) — Export übersprungen."
fi

echo ""
if [ "${SUPA_FEHLER:-0}" = "1" ]; then
  echo "✔ Tageslauf fertig in ${SECONDS}s — MIT Fehler beim Supabase-Upload  ($(date '+%F %T'))"
else
  echo "✔ Tageslauf fertig in ${SECONDS}s  ($(date '+%F %T'))"
fi
# Alte Logs aufräumen (>30 Tage)
find "$LOG_DIR" -name 'daily-*.log' -type f -mtime +30 -delete 2>/dev/null || true
