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
# AT läuft weiter nur über den eigenen Connector; dort liegt die TED-Historie ohnehin
# vollständig vor, es fehlt nur die Locale für den Live-Abruf.
step "TED-Live CH"
$PY scripts/fetch_ted_live.py --country CH --workers 3 \
  && echo "  TED-CHE ok." || echo "  ⚠ TED-CHE fehlgeschlagen — CH bleibt auf simap allein."

step "simap.ch (CH)"
$PY -m govisor.cli ingest-simap --country CH --max-pages 30 --silver \
  && echo "  simap ok." || echo "  ⚠ simap.ch fehlgeschlagen — CH bleibt auf altem Stand."

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

# 2) Gold neu mit heutigem Stichtag — refresht Leads, Fristen, months_to_expiry. FATAL bei Fehler.
step "Gold-Rebuild (Leads mit Stichtag $TODAY)"
if ! $PY -m govisor.cli gold --country DE --as-of "$TODAY"; then
  echo "  ✖ Gold-Rebuild fehlgeschlagen — KEIN Supabase-Push (kein Halb-Stand nach oben)."
  echo "Abbruch nach ${SECONDS}s."
  exit 2
fi
echo "  Gold ok."

# 3) FRONTEND-DATEN — das ist, was die App tatsächlich liest (web/data/*.json über
#    lib/dataSource.ts). Fehlte bis 2026-08-10 im Tageslauf: Ingest und Gold liefen täglich,
#    aber die Oberfläche zeigte den Stand des letzten Handlaufs (zuletzt 10 Tage alt).
#    Läuft VOR dem Supabase-Push, weil das Frontend nicht davon abhängt.
step "Frontend-Daten exportieren (web/data)"
if $PY scripts/export_web_leads.py; then
  # ACHTUNG: export_web_leads.py schreibt plz-geo.json komplett neu und wirft dabei den
  # Stadt-Index `_cities` weg (Umkreissuche über Stadtnamen). Der Index MUSS direkt danach
  # neu gebaut werden, sonst findet die Stadtsuche im Frontend nichts mehr.
  $PY scripts/build_city_index.py || echo "  ⚠ Stadt-Index nicht gebaut — Umkreissuche über Städte fällt aus."
  $PY scripts/export_suppliers.py || echo "  ⚠ Lieferanten-Index nicht gebaut — Onboarding-Matching bleibt auf altem Stand."
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
