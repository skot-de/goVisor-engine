#!/usr/bin/env bash
# Dauer-Arbeiter fuer die Antwortauftraege (Fragebogen → belegte Entwuerfe → Dokument).
#
# ⛔ WARUM ES DIESEN MANTEL GIBT. `scripts/antwort_arbeiter.py` war am 2026-10-06 ein
# Dauerdienst, den NIEMAND startete: kein Prozess, keine plist, kein Aufruf im Tageslauf — und
# kein anderer Abnehmer der Tabelle `user_antwortauftrag`. Die Weboberflaeche
# (`Antwortvorschlaege.tsx`) legte Auftraege ab und fragte nach Ergebnissen, die nie entstanden.
# Kein Test schlug an, weil jeder Baustein fuer sich korrekt war. Gefunden hat es
# `scripts/pruefe_leichen.py` (Spur 4), Beleg in `docs/cleanup-bericht.md`.
#
# Der Arbeiter braucht drei Umgebungswerte und bricht sonst VOR dem ersten Auftrag ab. Genau
# deshalb ein Mantel und keine nackte plist: Geheimnisse gehoeren nicht in eine plist, die im
# Repository liegt.
#
#   SUPABASE_URL, SUPABASE_SERVICE_KEY   aus .secrets/supabase.txt (Zeile 1 URL, Zeile 2 Key)
#   BLOCKS_KEK                           aus web/.env.local
#
# ⚠ DAS LEERE GUTHABEN IST HIER KEIN PROBLEM, und das ist nachgelesen, nicht gehofft: bei
# `BudgetErschoepft` legt der Arbeiter den Auftrag ZURUECK in die Schlange und zaehlt `versuche`
# wieder herunter (`_zurueck_in_die_schlange`, Begruendung im Code). Ein wartender Auftrag geht
# also nicht verloren, wenn das OpenRouter-Guthaben leer ist — er laeuft, sobald aufgeladen ist.
#
# Aufruf:  scripts/antwort_arbeiter.sh
#          launchctl load ~/Library/LaunchAgents/eu.govisor.antwort.plist
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
cd "$ROOT"

# ⚠ VOLLER PFAD. Unter launchd ist `python3` das System-Python (/usr/bin/python3), und das hat
# die Abhaengigkeiten nicht — dieselbe Falle wie bei den anderen Arbeitern.
PY=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
[ -x "$PY" ] || PY=python3

# ── Umgebung aus den Geheimnisdateien, nicht aus der plist ────────────────────────────
GEHEIM="$ROOT/.secrets/supabase.txt"
if [ ! -r "$GEHEIM" ]; then
  echo "⛔ $GEHEIM fehlt oder ist nicht lesbar — ohne Zugang kein Arbeiter." >&2
  exit 1
fi
SUPABASE_URL="$(sed -n '1p' "$GEHEIM" | tr -d '[:space:]')"
SUPABASE_SERVICE_KEY="$(sed -n '2p' "$GEHEIM" | tr -d '[:space:]')"
export SUPABASE_URL SUPABASE_SERVICE_KEY

ENVDATEI="$ROOT/web/.env.local"
if [ -r "$ENVDATEI" ]; then
  BLOCKS_KEK="$(grep -m1 '^BLOCKS_KEK=' "$ENVDATEI" | cut -d= -f2- | tr -d '"' | tr -d "'")"
  export BLOCKS_KEK
fi

# Der Geldwache ihren Schluessel zeigen (sie sitzt in `llm.chat()`, nicht im Aufrufer).
[ -r "$ROOT/.secrets/openrouter.key" ] && export OPENROUTER_KEY_FILE="$ROOT/.secrets/openrouter.key"

for v in SUPABASE_URL SUPABASE_SERVICE_KEY BLOCKS_KEK; do
  if [ -z "${!v:-}" ]; then
    echo "⛔ $v ist leer — der Arbeiter wuerde vor dem ersten Auftrag abbrechen." >&2
    exit 1
  fi
done

# `EINMAL=1` fuer die Abnahme von Hand: ein Durchlauf, dann Schluss. Der Dienst setzt es nicht
# und laeuft im Takt. Ohne diesen Schalter gaebe es keine Moeglichkeit, die Umgebung zu pruefen,
# ohne einen Dauerlauf zu starten — und genau das will man vor dem ersten Mal wissen.
if [ -n "${EINMAL:-}" ]; then
  echo "── Antwort-Arbeiter, EIN Durchlauf $(date '+%Y-%m-%d %H:%M:%S') · Baum $ROOT"
  exec "$PY" "$ROOT/scripts/antwort_arbeiter.py" --einmal
fi

echo "── Antwort-Arbeiter startet $(date '+%Y-%m-%d %H:%M:%S') · Baum $ROOT"
exec "$PY" "$ROOT/scripts/antwort_arbeiter.py" --takt "${TAKT:-30}"
