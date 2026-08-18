#!/usr/bin/env bash
# Dauerhafter Arbeiter am Dokumenten-Rückstau.
#
# WARUM ES IHN GIBT. Sven am 2026-08-18: „kannst du ein agenten permanent an der
# verarbeitung der dokumente arbeiten lassen? sonst werden wir den rückstau nie
# abarbeiten." Der Tageslauf holt je Abrufer 60 Vorgänge pro Nacht und läuft dabei
# regelmässig in seine Acht-Stunden-Grenze. Gemessen am 2026-08-18:
#
#     16.096  offene Leads
#     12.547  mit Unterlagen-Link      78 %
#      4.259  ZIP heruntergeladen      34 %   ← der Rückstau
#      3.974  Signale ausgelesen       93 %
#        239  LLM-Analyse               6 % der heruntergeladenen
#
# REIHENFOLGE NACH AKTUALITÄT. Sven: „fang mit den neuesten ausschreibungen an und
# arbeite dich zu den alten durch. bis ich in die erste demo gehe, sind die jetzt
# aktuellen ausschreibungen dann schon alt." Die Sortierung sitzt in `analyze_docs.py`
# (offene Leads zuerst, darin die späteste Frist); hier steht sie nur als Begründung,
# warum der Arbeiter NICHT stumpf alles der Reihe nach frisst.
#
# ⛔ ER WEICHT DEM TAGESLAUF. Beide würden in dieselben Manifeste und denselben
# Dokumentenbaum schreiben. Der Tageslauf schützt sich per Lock; dieser Arbeiter prüft
# ihn VOR JEDER RUNDE und legt sich sonst schlafen. Das ist der Grund, warum er als
# Endlosschleife läuft und nicht als einmaliger Lauf: er soll die Lücken zwischen den
# Tagesläufen füllen, nicht mit ihnen kämpfen.
#
# DREI STUFEN, billig zuerst:
#   1. index-docs    Text aus vorhandenen ZIPs   (lokal, kostenlos)
#   2. Abrufer       fehlende ZIPs holen         (Netz, kostenlos, portalschonend)
#   3. analyze_docs  LLM-Analyse                 (kostet Geld)
# So entsteht früh Wert: Stufe 1 hebt die Volltext-Abdeckung, ohne einen Cent zu kosten.
#
# Aufruf:  scripts/dokumente_arbeiter.sh            (Vordergrund, zum Zusehen)
#          launchctl load ~/Library/LaunchAgents/eu.govisor.dokumente.plist
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY=python3
LOCK="$ROOT/data/.daily_leads.lock"
EIGEN="$ROOT/data/.dokumente_arbeiter.lock"
LOG="$ROOT/data/logs/dokumente-arbeiter.log"

# ⚠ Die Daten liegen auf einer EXTERNEN Platte (data → /Volumes/goVisor). Ist sie nicht
# eingehaengt, darf der Arbeiter nicht loslaufen — er wuerde ins Leere greifen und im
# schlimmsten Fall ein leeres data/ neu anlegen. Warten statt scheitern.
while [ ! -d "$ROOT/data/gold" ]; do
  echo "[$(date '+%d.%m. %H:%M')] Datenplatte nicht eingehaengt — warte 5 min." \
    >> "$HOME/Library/Logs/govisor-arbeiter.out.log"
  sleep 300
done
mkdir -p "$(dirname "$LOG")"

# Nur EIN Arbeiter. Ohne das startet launchd nach einem Absturz einen zweiten daneben,
# und zwei Abrufer am selben Portal sind der schnellste Weg zu einer Sperre.
if [ -e "$EIGEN" ] && kill -0 "$(cat "$EIGEN" 2>/dev/null)" 2>/dev/null; then
  echo "Ein Arbeiter läuft bereits (PID $(cat "$EIGEN"))." ; exit 0
fi
echo $$ > "$EIGEN"
trap 'rm -f "$EIGEN"' EXIT

sag() { echo "[$(date '+%d.%m. %H:%M')] $*" | tee -a "$LOG"; }

sag "Arbeiter gestartet (PID $$)"
while true; do
  if [ -e "$LOCK" ]; then
    sag "Tageslauf aktiv — warte 15 min."
    sleep 900; continue
  fi

  # ── Stufe 1: Text aus dem, was schon da ist ────────────────────────────────────
  # Zuerst, weil es nichts kostet und sofort im Frontend ankommt.
  #
  # ⛔ NICHT NEBEN EINEM HAND-LAUF. Der Tageslauf schuetzt sich per Lock, ein von Hand
  # gestartetes `index-docs` nicht — und beide schreiben dieselbe `doc_text.parquet`.
  # Genau das drohte am 2026-08-18, als nach neuen Lesern (.doc/.xls/AI-AG) 492 Vorgaenge
  # zum erneuten Auslesen freigegeben wurden. Ein `pgrep` ist hier billiger als jede
  # Aufraeumarbeit hinterher.
  if pgrep -f "govisor.cli index-docs" >/dev/null 2>&1; then
    sag "Stufe 1 uebersprungen — es laeuft bereits ein index-docs."
  else
  sag "Stufe 1: Text auslesen"
  $PY -m govisor.cli index-docs --country DE >>"$LOG" 2>&1 \
    && $PY scripts/export_doc_text.py >>"$LOG" 2>&1 \
    && sag "  Volltext exportiert" || sag "  ⚠ Stufe 1 unvollständig"
  fi

  [ -e "$LOCK" ] && continue

  # ── Stufe 2: fehlende Unterlagen holen ─────────────────────────────────────────
  # Ein Abrufer je Runde, nicht alle gleichzeitig: die Portale sollen uns weiter
  # bedienen. `rueckstau.py` bringt Höflichkeitspausen und Deckel schon mit.
  sag "Stufe 2: Unterlagen holen"
  for c in evergabe_online cosinex subreport netserver ausschreibungsblatt; do
    [ -e "$LOCK" ] && break
    # ⚠ KEIN `timeout` — das ist GNU-coreutils und auf macOS nicht vorhanden (Exit 127).
    # Braucht es auch nicht: `rueckstau.py` bringt mit --stunden seine eigene Grenze mit.
    scripts/rueckstau.py --connector "$c" --stunden 1 --limit 40 >>"$LOG" 2>&1
  done

  [ -e "$LOCK" ] && continue

  # ── Stufe 3: LLM-Analyse, neueste zuerst ───────────────────────────────────────
  # LIMIT je Runde, damit zwischen den Runden der Lock wieder geprüft wird und ein
  # Abbruch nur die angefangene Runde kostet. `analyze_docs` ist idempotent: was schon
  # in doc-analysis.json steht, wird übersprungen.
  sag "Stufe 3: LLM-Analyse (neueste zuerst)"
  LIMIT=40 $PY scripts/analyze_docs.py >>"$LOG" 2>&1 && sag "  Runde fertig" || sag "  ⚠ Analyse-Runde abgebrochen"

  # Ausgaben sichtbar machen, ohne ins Anbieter-Dashboard zu müssen.
  $PY scripts/dokumente_stand.py >>"$LOG" 2>&1 || true
  sag "Runde beendet — 10 min Pause"
  sleep 600
done
