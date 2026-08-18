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
# ZWEI STUFEN, billig zuerst:
#   1. index-docs    Text aus vorhandenen ZIPs   (lokal, kostenlos)
#   2. Abrufer       fehlende ZIPs holen         (Netz, kostenlos, portalschonend)
#   (3. analyze_docs — ausgezogen nach scripts/analyse_arbeiter.sh, s. unten)
# So entsteht früh Wert: Stufe 1 hebt die Volltext-Abdeckung, ohne einen Cent zu kosten.
#
# Aufruf:  scripts/dokumente_arbeiter.sh            (Vordergrund, zum Zusehen)
#          launchctl load ~/Library/LaunchAgents/eu.govisor.dokumente.plist
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
# ⚠ VOLLER PFAD, s. analyse_arbeiter.sh: unter launchd ist `python3` das System-Python
# ohne duckdb. Dass es hier bisher lief, lag am geerbten PATH der Terminal-Sitzung, aus der
# geladen wurde — nach einem Neustart der Maschine waere es stumm gescheitert.
PY=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
[ -x "$PY" ] || PY=python3
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
  # ALLE ZWOELF ABRUFER, aber drei je Runde im Wechsel.
  #
  # Seit dem 2026-08-18 holt der Tageslauf keine Unterlagen mehr (s. daily_leads.sh,
  # `_ABRUF_AUS`): gemessen gingen dort rund fuenf der acht Stunden dafuer drauf, und
  # 6 von 10 Laeufen endeten deshalb an ihrer eigenen Zeitgrenze. Damit liegt die
  # Beschaffung vollstaendig hier — also muessen auch alle Abrufer hier vorkommen, nicht
  # nur die fuenf vom ersten Entwurf.
  #
  # ⚠ NICHT ALLE ZWOELF JE RUNDE. Bei einer Stunde je Abrufer waere eine Runde zwoelf
  # Stunden lang, und dazwischen wird der Tageslauf-Lock nicht geprueft. Drei je Runde,
  # rotierend ueber einen Zaehler: nach vier Runden war jeder einmal dran, und zwischen
  # den Runden ist der Weg frei fuer alles andere.
  ALLE=(evergabe_online cosinex subreport netserver ausschreibungsblatt healyhudson
        staatsanzeiger vergabeportal_at aumass bimedien evergabe simap_docs)
  # Der Zaehler lebt in einer Datei, nicht in einer Variablen: sonst faengt der Arbeiter
  # nach jedem Neustart wieder beim selben Abrufer an — und die hinteren kaemen nie dran.
  ZAEHLER="$ROOT/data/.abrufer_runde"
  RUNDE=$(( $(cat "$ZAEHLER" 2>/dev/null || echo 0) + 1 ))
  echo "$RUNDE" > "$ZAEHLER" 2>/dev/null || true
  START=$(( (RUNDE * 3) % ${#ALLE[@]} ))
  for i in 0 1 2; do
    c=${ALLE[$(( (START + i) % ${#ALLE[@]} ))]}
    [ -e "$LOCK" ] && break
    # ⚠ KEIN `timeout` — das ist GNU-coreutils und auf macOS nicht vorhanden (Exit 127).
    # Braucht es auch nicht: `rueckstau.py` bringt mit --stunden seine eigene Grenze mit.
    scripts/rueckstau.py --connector "$c" --stunden 1 --limit 40 >>"$LOG" 2>&1
  done

  [ -e "$LOCK" ] && continue

  # ── Stufe 3 IST AUSGEZOGEN ──────────────────────────────────────────────────────
  # Sie liegt seit dem 2026-08-18 in `scripts/analyse_arbeiter.sh` mit eigenem launchd-Dienst.
  #
  # Der Grund ist gemessen: Stufe 2 fragt fuenf Portale ab, je bis zu einer Stunde und
  # bewusst langsam. Solange sie laeuft, stand die Analyse still — um 20:15 waren es
  # 9 Vorgaenge in 34 Minuten, obwohl sie im Alleinlauf rund 200 in der Stunde schafft.
  # Die schnelle Aufgabe hinter der langsamen anzustellen war die eigentliche Bremse,
  # nicht die Rundengroesse und nicht die Parallelitaet.
  #
  # Beide Arbeiter weichen weiterhin dem Tageslauf aus und pruefen sich gegenseitig ueber
  # `pgrep`; sie fassen verschiedene Dateien an (hier Archive, dort doc-analysis.json).

  # Ausgaben sichtbar machen, ohne ins Anbieter-Dashboard zu müssen.
  $PY scripts/dokumente_stand.py >>"$LOG" 2>&1 || true
  # Die Pause war die zweite Bremse: zehn Minuten Nichtstun nach jeder Runde. Sie sollte die
  # Portale schonen — die kommen aber in Stufe 2 dran, nicht hier. Zwei Minuten reichen, um
  # zwischen den Runden Luft zu lassen und den Lock erneut zu pruefen.
  sag "Runde beendet — 2 min Pause"
  sleep 120
done
