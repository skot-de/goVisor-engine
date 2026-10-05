#!/bin/bash
# Alle Waechter in EINEM Lauf — unabhaengig vom Tageslauf.
#
# WARUM ES DIESE DATEI GIBT (2026-09-20). Die elf Sonden standen bis heute ausschliesslich
# am ENDE von `scripts/daily_leads.sh`, ab Zeile 1707 von 1860. In der Nacht zum 20.09.
# blieb der Tageslauf in Zeile 931 haengen (Dubletten-Firewall, 631 min) und wurde vom
# Acht-Stunden-Riegel beendet. Ergebnis:
#
#   · Gold wurde nicht gebaut, das Produkt zeigte elf Stunden lang den Vortagsstand.
#   · KEINE EINZIGE Sonde lief — sie liegen alle hinter der Bruchstelle.
#
# Das ist die Bauform des Problems, nicht ein Einzelfall: **die Aufsicht hing am
# Beaufsichtigten**. Ein Lauf, der frueh stirbt, ist genau der Fall, der Aufmerksamkeit
# braucht, und genau der Fall, in dem niemand hinsieht. Sogar die Sonde, die eigens fuer
# diesen Ausfall gebaut wurde (Sonde 8, „hat die letzte Nacht das Produkt erreicht?"),
# steht in Zeile 1707 und haette am 20.09. nicht gefeuert.
#
# ⚠ ALLE SONDEN HIER SIND LESEND. Keine nimmt die Tageslauf-Sperre, keine schreibt nach
# `data/` — `pruefe_endgueltige.py` laedt in ein Temp-Verzeichnis und verwirft es (ihr
# Docstring sagt es ausdruecklich). Deshalb darf dieser Lauf NEBEN dem Tageslauf und neben
# den Abrufern laufen. Er wartet bewusst nicht: ein Waechter, der auf die Sperre wartet,
# ist wieder vom Beaufsichtigten abhaengig.
#
# ⚠ ZWEITE LISTE, UND SIE DARF NICHT DRIFTEN. Der Tageslauf ruft dieselben Sonden weiter
# selbst auf (sofort-Rueckmeldung im Protokoll). Damit die beiden Listen nicht
# auseinanderlaufen — die Krankheit, an der in diesem Haus schon mehrere Kopien gestorben
# sind — haelt `tests/test_waechterlauf.py` sie gegeneinander: jede `pruefe_*.py`, die der
# Tageslauf ruft, muss auch hier stehen und umgekehrt.
#
#     scripts/waechterlauf.sh            # alle Sonden, Befunde nach stdout + Log
#     scripts/waechterlauf.sh --still    # nur die Zusammenfassung
#
# Rueckgabe 0 = alles still, 1 = mindestens eine Sonde hat etwas gefunden.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

# ⚠ VOLLER PFAD, wie in den Arbeiter-Skripten: unter launchd ist `python3` das
# System-Python ohne duckdb — und der Fehlschlag sieht aus wie ein Sondenbefund.
PY=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
[ -x "$PY" ] || PY=python3

STILL=0
[ "${1:-}" = "--still" ] && STILL=1

# ⚠ NICHT NACH `data/logs/`, so naheliegend es waere. `data` ist ein Symlink auf ein
# externes Volume, und macOS vergibt den Zugriff darauf JE PROGRAMM: das Python-Framework
# hat ihn, die von launchd gestartete Bash NICHT. Ein Waechterlauf, der sein eigenes
# Protokoll nicht schreiben kann, faellt unter launchd stumm aus — und zwar genau so, wie
# es am 2026-09-19 dem Tagesdeckel-Riegel im Analyse-Arbeiter ergangen ist.
# `~/Library/Logs` ist der Pfad, den die beiden Dauerarbeiter aus demselben Grund benutzen.
LOG_DIR="${GOVISOR_WAECHTER_LOGS:-$HOME/Library/Logs}"
mkdir -p "$LOG_DIR" 2>/dev/null
LOG="$LOG_DIR/govisor-waechter-$(date +%Y-%m-%d-%H%M).log"
STAND="$LOG_DIR/govisor-waechter-stand.txt"

# ⚠ FRIST JE SONDE. `pruefe_endgueltige.py` und `pruefe_abdeckung.py` gehen ins Netz; eine
# haengende Gegenstelle darf nicht den ganzen Waechterlauf aufhalten. `timeout` gibt es auf
# macOS nicht — deshalb Kind starten, Wecker danebenstellen (dieselbe Bauform wie
# `mit_grenze` im Tageslauf).
FRIST=${GOVISOR_WAECHTER_FRIST:-900}        # 15 min je Sonde

mit_frist() {
  local frist=$1; shift
  "$@" & local kind=$!
  local ende=$(( $(date +%s) + frist ))
  while kill -0 "$kind" 2>/dev/null; do
    [ "$(date +%s)" -ge "$ende" ] && { kill -TERM "$kind" 2>/dev/null; sleep 3
      kill -KILL "$kind" 2>/dev/null; return 124; }
    sleep 5
  done
  wait "$kind"
}

BEFUNDE=""
ANZAHL=0
GEPRUEFT=0

# sonde <name> <hinweis> -- <befehl...>
sonde() {
  local name=$1 hinweis=$2; shift 3     # das "--" mit wegwerfen
  GEPRUEFT=$(( GEPRUEFT + 1 ))
  local t0 rc
  t0=$(date +%s)
  if [ "$STILL" = "1" ]; then
    mit_frist "$FRIST" "$@" >>"$LOG" 2>&1; rc=$?
  else
    mit_frist "$FRIST" "$@" 2>&1 | tee -a "$LOG"; rc=${PIPESTATUS[0]}
  fi
  local dauer=$(( $(date +%s) - t0 ))
  if [ "$rc" = "124" ]; then
    BEFUNDE="$BEFUNDE  ⏱ $name — Frist von $(( FRIST / 60 )) min gerissen, abgebrochen
"
    ANZAHL=$(( ANZAHL + 1 ))
  elif [ "$rc" != "0" ]; then
    BEFUNDE="$BEFUNDE  ⚠ $name — $hinweis
"
    ANZAHL=$(( ANZAHL + 1 ))
  fi
  printf '[%s] %-26s %s (%ds)\n' "$(date '+%H:%M')" "$name" \
    "$([ "$rc" = 0 ] && echo still || echo "BEFUND rc=$rc")" "$dauer" >>"$LOG"
}

echo "── Waechterlauf $(date '+%Y-%m-%d %H:%M') ──" | tee -a "$LOG"
if [ -d "$ROOT/data/.daily_leads.lock" ]; then
  echo "   (Tageslauf laeuft gerade — die Sonden lesen nur, das stoert ihn nicht)" | tee -a "$LOG"
fi

# ── Die vierzehn Sonden, in der Reihenfolge des Tageslaufs ─────────────────────────────────
# ⚠ ZUERST, und zwar aus dem Grund, der diese Sonde hervorgebracht hat: am 2026-10-05
# meldeten zwei Pruefungen eine entartete Kennzahl, und die Ursache war, dass der Nachtlauf
# einen anderen Baum faehrt als den, in dem geprueft wird. Schlaegt sie an, kann jeder
# Befund darunter ein Trugbild sein.
sonde laufender_code "Details: python3 scripts/pruefe_laufender_code.py --alle" \
  -- $PY scripts/pruefe_laufender_code.py
sonde verdrahtung "Details: python3 scripts/pruefe_verdrahtung.py --offen" \
  -- $PY scripts/pruefe_verdrahtung.py
sonde laender_tabellen "Details: python3 scripts/pruefe_laender_tabellen.py --alle" \
  -- $PY scripts/pruefe_laender_tabellen.py
sonde endgueltige "Details: python3 scripts/pruefe_endgueltige.py --offen" \
  -- $PY scripts/pruefe_endgueltige.py --stichprobe 8
sonde nuts_vorgabe "Details: python3 scripts/pruefe_nuts_vorgabe.py --alle" \
  -- $PY scripts/pruefe_nuts_vorgabe.py
# ⚠ Diese Sonde war am 2026-10-03 nur im Tageslauf verdrahtet und hier NICHT — gefunden von
#   `tests/test_waechterlauf.py::test_beide_listen_sind_deckungsgleich`, also von genau dem
#   Test, der fuer diesen Fall gebaut wurde. Sie gehoert hierher, weil der Tageslauf frueh
#   sterben kann (20.09. in Zeile 931 von 1860, danach lief keine einzige Sonde) und eine
#   entartete Kennzahl dann unbemerkt im Produkt steht. Sie liest nur `web/data/strategie.json`.
sonde streuung "Details: python3 scripts/pruefe_streuung.py --offen" \
  -- $PY scripts/pruefe_streuung.py
sonde sondierung "Details: python3 scripts/pruefe_sondierung.py" \
  -- $PY scripts/pruefe_sondierung.py
sonde supabase_migrationen "Details: python3 scripts/pruefe_supabase_migrationen.py" \
  -- $PY scripts/pruefe_supabase_migrationen.py --still
sonde abdeckung "Details: python3 scripts/pruefe_abdeckung.py" \
  -- $PY scripts/pruefe_abdeckung.py
sonde sondierungszahlen "Details: python3 scripts/pruefe_sondierungszahlen.py --alle" \
  -- $PY scripts/pruefe_sondierungszahlen.py
sonde werte "Details: python3 scripts/pruefe_werte.py" \
  -- $PY scripts/pruefe_werte.py
sonde gold_integritaet "Details: python3 scripts/pruefe_gold_integritaet.py --land <L>" \
  -- $PY scripts/pruefe_gold_integritaet.py
sonde bibel "Details: python3 scripts/pruefe_bibel.py --offen" \
  -- $PY scripts/pruefe_bibel.py
sonde vollstaendigkeit "Details: python3 scripts/pruefe_vollstaendigkeit.py --offen" \
  -- $PY scripts/pruefe_vollstaendigkeit.py

# ── Zusammenfassung ──────────────────────────────────────────────────────────────────────
#
# ⚠ EINE ZEILE, DIE JEMAND LIEST. `data/logs/letzter_lauf.txt` hat am 20.09. den Abbruch
# korrekt protokolliert — und niemand hat hineingesehen. Deshalb hier dieselbe Form
# ABSICHTLICH fuer den Waechterlauf: eine Datei, ein Satz, und die Morgenpruefung liest sie.
if [ "$ANZAHL" = "0" ]; then
  ZEILE="$(date '+%Y-%m-%d %H:%M')  still · $GEPRUEFT Sonden · keine Befunde"
else
  ZEILE="$(date '+%Y-%m-%d %H:%M')  $ANZAHL von $GEPRUEFT Sonden melden Befunde"
fi
printf '%s\n' "$ZEILE" > "$STAND"

echo "" | tee -a "$LOG"
echo "── $ZEILE" | tee -a "$LOG"
[ -n "$BEFUNDE" ] && printf '%s' "$BEFUNDE" | tee -a "$LOG"
echo "   Protokoll: $LOG" | tee -a "$LOG"

find "$LOG_DIR" -name 'govisor-waechter-*.log' -type f -mtime +30 -delete 2>/dev/null || true
[ "$ANZAHL" = "0" ] || exit 1
exit 0
