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

# 1) DÖE-Live (unterschwellig DE): laufenden + Vormonat FRISCH LADEN (--fetch), dann parsen.
#    Der laufende Monat wächst täglich → so kommen neue Ausschreibungen tages-frisch rein (kein 30-Tage-Lag).
step "DÖE-Ingest (unterschwellig DE, --fetch laufend+Vormonat)"
if $PY -m govisor.cli ingest-doe --country DE --fetch --fetch-back 1 --force; then
  echo "  DÖE ok."
else
  echo "  ⚠ DÖE-Ingest fehlgeschlagen (API?) — fahre mit Gold/Export fort (as-of-Refresh bleibt wertvoll)."
fi

# 2) Gold neu mit heutigem Stichtag — refresht Leads, Fristen, months_to_expiry. FATAL bei Fehler.
step "Gold-Rebuild (Leads mit Stichtag $TODAY)"
if ! $PY -m govisor.cli gold --country DE --as-of "$TODAY"; then
  echo "  ✖ Gold-Rebuild fehlgeschlagen — KEIN Supabase-Push (kein Halb-Stand nach oben)."
  echo "Abbruch nach ${SECONDS}s."
  exit 2
fi
echo "  Gold ok."

# 3) Schema selbstheilend migrieren (neue Parquet-Spalten → gov_*-Tabellen) via psql, dann pushen.
if [ -n "${SUPABASE_URL:-}" ] && [ -n "${SUPABASE_SERVICE_KEY:-}" ]; then
  step "Supabase-Schema-Migration (DDL aus aktuellem Parquet, idempotent via psql)"
  $PY scripts/export_supabase.py --table all --ddl-only
  REF="$(echo "$SUPABASE_URL" | sed -E 's#https?://([a-z0-9]+)\.supabase\.co.*#\1#')"
  if [ -f "$ROOT/.secrets/supabase_db.txt" ] && command -v psql >/dev/null 2>&1; then
    if PGPASSWORD="$(tr -d '[:space:]' < "$ROOT/.secrets/supabase_db.txt")" psql \
         -h "db.$REF.supabase.co" -p 5432 -U postgres -d postgres \
         -v ON_ERROR_STOP=1 -q -f docs/supabase_schema.sql >/dev/null; then
      echo "  Schema aktuell (Drift automatisch nachgezogen)."
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
    echo "  ✖ Supabase-Push fehlgeschlagen — lokale Leads sind aktuell, nur der Upload nicht."
    exit 3
  fi
else
  echo "  ⚠ Keine Supabase-Creds (.secrets/supabase.txt) — Export übersprungen."
fi

echo ""
echo "✔ Tageslauf fertig in ${SECONDS}s  ($(date '+%F %T'))"
# Alte Logs aufräumen (>30 Tage)
find "$LOG_DIR" -name 'daily-*.log' -type f -mtime +30 -delete 2>/dev/null || true
