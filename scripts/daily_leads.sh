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

# Nach BEIDEN CH-Quellen: welche TED-Notice ist eine simap-Dublette? Muss hier laufen,
# nicht früher — der Abgleich braucht den frischen Stand beider Seiten.
#
# Er prüft selbst, ob die TED-Seite vollständig genug ist (≥90 % der laut TED-API
# erwarteten Notices je Monat) und überspringt sich sonst mit Exit 2. Ein Abgleich auf
# halbem Bestand wäre schlimmer als keiner: er stuft ungeholte Notices als „neu" ein, und
# wer das benutzt, nimmt Dubletten auf. Deshalb drei Ausgänge statt zwei.
step "CH-Quellenabgleich (TED gegen simap)"
$PY scripts/dedupe_ch_sources.py
case $? in
  0) echo "  Abgleich ok." ;;
  2) echo "  ⏭ Abgleich übersprungen (Bestand noch unvollständig) — voriges Ergebnis bleibt gültig." ;;
  *) echo "  ✖ CH-Abgleich fehlgeschlagen — Dubletten möglich." ;;
esac

# Dasselbe für AT, aus demselben Grund — TED-AT und OffeneVergaben.at überschneiden sich
# gemessen zu 93 %. Der vorhandene OSB-Flag-Filter in build_at_gold reicht nicht: von den
# atverg-Notices mit nachweislicher TED-Entsprechung tragen nur 42,8 % das Flag, 53,8 %
# tragen gar keinen Schwellenwert. 57,2 % der echten Dubletten überlebten ihn.
# Muss VOR dem Gold-Rebuild laufen — build_at_gold liest die erzeugte Tabelle.
step "AT-Quellenabgleich (TED gegen OffeneVergaben)"
$PY scripts/dedupe_at_sources.py \
  && echo "  Abgleich ok." \
  || echo "  ⚠ AT-Abgleich fehlgeschlagen — voriger Stand bleibt gültig, Dubletten möglich."

# AT- und CH-Gold: bis 2026-08-13 liefen hier zwei Schmalspur-Bruecken, die laut eigenem
# Docstring "bewusst KEINE volle DE-Gold-Pipeline" bauten. Folge: der Auslauf-Radar — in DE
# 86 % aller Leads — existierte fuer AT und CH ueberhaupt nicht, obwohl 227.117 bzw. 51.262
# Zuschlaege im Silber lagen (AT sogar mit BESSERER Vertragsende-Abdeckung als DE: 27,4 %
# gegen 14,9 %). Gemessen beim Umstellen: AT 595 → 17.124 Leads, CH 1.591 → 8.608.
#
# ⚠ Die alten Aufrufe duerfen NICHT wieder hierher: `gold --country AT --bridge` und
# `simap.build_ch_gold` ueberschreiben lead_export mit der 595-Zeilen-Fassung. Wer sie
# reaktiviert, setzt beide Laender ueber Nacht zurueck, ohne dass ein Test anschlaegt.
#
# Nicht-fatal: AT/CH sind Zusatzmaerkte, ein Problem dort darf den deutschen Kern nicht
# mit herunterreissen. Laeuft VOR dem DE-Gold, weil der Frontend-Export spaeter alle drei
# Laender in einem Durchgang liest.
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
# DTVP-Bekanntmachungen (DE, unterschwellig). Gemessen 2026-08-13 an einer ueber
# 05/2024–08/2026 GESTREUTEN Stichprobe: 38 % der VOB/A-Ausschreibungen fehlten uns.
#
# ⚠ NUR VOB/A. Der VOL-Bereich (VgV/VOL/A/UVgO) ist mit 8.640 offenen Treffern noch
#   groesser, liefert aber KEINEN CPV — und `build_prospective_leads` verlangt
#   `cpv_main IS NOT NULL`. Bei VOB/A ist die Branche die Definition der Vorschrift
#   (Vergabe- und Vertragsordnung fuer BAUleistungen → CPV 45); bei VOL gibt es keine
#   solche Ableitung, das kann IT, Beratung oder Medizintechnik sein. Der CPV-Filter der
#   Suche nimmt keine zweistelligen Divisionen (geprueft: Seite haengt, 0 Treffer), er
#   erwartet vollstaendige Codes aus einem Dialog. Bis das geloest ist, waeren VOL-Leads
#   ohne Branche und damit im Produkt unsichtbar — offener Punkt, kein stiller Verzicht.
#
# Braucht Playwright + chromium-headless-shell (die Trefferliste entsteht clientseitig).
# Nicht fatal: eine fremde Website darf den Tageslauf nicht abbrechen.
step "DTVP-Bekanntmachungen (DE unterschwellig, VOB/A)"
$PY -m govisor.dtvp --regeln VOB --typen Tender --max-seiten 40 --stop-nach-bekannten 40 --silber \
  || echo "  ⚠ DTVP-Abruf fehlgeschlagen — Bestand bleibt auf dem letzten Stand."

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
