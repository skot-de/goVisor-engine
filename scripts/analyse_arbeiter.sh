#!/usr/bin/env bash
# Dauer-Arbeiter NUR für die LLM-Analyse.
#
# WARUM GETRENNT VOM DOKUMENTEN-ARBEITER. Der macht drei Stufen nacheinander: Text auslesen,
# Unterlagen holen, analysieren. Stufe 2 fragt fünf Portale ab, je bis zu einer Stunde und
# bewusst langsam (Höflichkeit gegenüber den Portalen). Gemessen am 2026-08-18 um 20:15: die
# Analyse kam in 34 Minuten auf 9 Vorgänge — nicht weil sie langsam ist, sondern weil sie
# gar nicht lief. Im Alleinlauf schafft sie bei 10 Fäden rund 200 in der Stunde.
#
# Zwei Schleifen statt einer, weil die beiden Aufgaben nichts miteinander zu tun haben: die
# eine wartet auf fremde Server, die andere auf ein Sprachmodell. Sie in eine Reihe zu
# zwingen heisst, die schnelle auf die langsame warten zu lassen.
#
# ⛔ WEM ER AUSWEICHT:
#   * dem Tageslauf (schreibt dieselben Manifeste)
#   * einem laufenden `index-docs` (schreibt doc_text.parquet, aus dem hier gelesen wird)
# Beides wird VOR JEDER RUNDE geprüft, nicht nur beim Start.
#
# Aufruf:  scripts/analyse_arbeiter.sh
#          launchctl load ~/Library/LaunchAgents/eu.govisor.analyse.plist
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
# ⚠ VOLLER PFAD. Unter launchd ist `python3` das System-Python (/usr/bin/python3) — ohne
# duckdb, ohne alles. Gemessen: „ModuleNotFoundError: No module named 'duckdb'", und der
# Dienst lief weiter, als sei nichts. Der Dokumenten-Arbeiter kam damit durch, weil er aus
# einer Terminal-Sitzung geladen wurde und deren PATH geerbt hat; das ist Zufall, kein
# Verlass. Wer die Python-Version wechselt, aendert diese Zeile.
PY=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
[ -x "$PY" ] || PY=python3
LOCK="$ROOT/data/.daily_leads.lock"
EIGEN="$ROOT/data/.analyse_arbeiter.lock"
# ⚠ NICHT nach data/logs/. `data` ist ein Symlink auf die externe Platte, und ein NEU
# angelegter launchd-Dienst hat dort keine Schreibrechte (macOS vergibt den Zugriff auf
# externe Volumes je Programm). Gemessen am 2026-08-18, 20:23: „tee: Operation not
# permitted", danach brach JEDE Runde ab — der Dienst lief, tat aber nichts.
# Das Log gehoert ohnehin auf die interne Platte: es soll auch lesbar sein, wenn die
# externe gerade nicht eingehaengt ist.
LOG="$HOME/Library/Logs/govisor-analyse.log"

# ⚠ Externe Platte. Ist sie nicht eingehaengt, warten statt ins Leere greifen.
while [ ! -d "$ROOT/data/gold" ]; do
  echo "[$(date '+%d.%m. %H:%M')] Datenplatte nicht eingehaengt — warte 5 min." \
    >> "$HOME/Library/Logs/govisor-analyse.out.log"
  sleep 300
done
mkdir -p "$(dirname "$LOG")"

# Nur EIN Analyse-Arbeiter: zwei wuerden dieselbe doc-analysis.json schreiben und sich
# gegenseitig ueberschreiben — der zweite gewinnt, und die Arbeit des ersten ist weg.
if [ -e "$EIGEN" ] && kill -0 "$(cat "$EIGEN" 2>/dev/null)" 2>/dev/null; then
  echo "Ein Analyse-Arbeiter läuft bereits (PID $(cat "$EIGEN"))." ; exit 0
fi
echo $$ > "$EIGEN"
trap 'rm -f "$EIGEN"' EXIT

sag() { echo "[$(date '+%d.%m. %H:%M')] $*" | tee -a "$LOG"; }

sag "Analyse-Arbeiter gestartet (PID $$)"
while true; do
  if [ -e "$LOCK" ]; then
    sag "Tageslauf aktiv — warte 10 min."
    sleep 600; continue
  fi
  if pgrep -f "govisor.cli index-docs" >/dev/null 2>&1; then
    sag "index-docs laeuft — warte 5 min."
    sleep 300; continue
  fi

  # LIMIT begrenzt die Runde, nicht den Fortschritt: nach jeder Runde wird oben erneut
  # geprueft, ob jemand anderes an die Daten will. PARALLEL steht hoeher als beim
  # Dokumenten-Arbeiter, weil hier nichts anderes um die Verbindung konkurriert.
  # PARALLEL=40. Sven: „dann lass halt 100 agenten parallel los laufen." Die Grenze ist
  # nicht die Maschine — der Lauf ist Warten auf das Modell — sondern zweierlei: das
  # Ratenlimit der Gegenstelle (`govisor/llm.py` faengt 429 mit Backoff und Key-Rotation
  # ab, aber wer dauernd dagegenlaeuft, wartet nur teurer) und der Speicher: jeder Faden
  # packt Archive aus und haelt bis zu 200.000 Token Text. 40 ist der gemessene Schritt
  # nach 10; wenn im Log keine 429 auftauchen und der Speicher haelt, darf er hoeher.
  # ── DREI VORGABEN, die am 2026-08-21 gefehlt haben ─────────────────────────────────
  #
  # Ohne sie lief dieser Arbeiter 15 Stunden unbemerkt bei rund 50 $/h durch und rechnete
  # dabei fast ausschliesslich Vorgaenge mit ABGELAUFENER Frist — die einzigen, die im
  # Textindex standen. Rund 350 $ fuer Analysen ohne Produktwert.
  #
  #   BUDGET_USD  harte Notbremse. Der Lauf merkt sich den Kontostand beim Start und bricht
  #               ab, sobald die Differenz die Grenze reisst. ⚠ Der Stand ist KONTOWEIT:
  #               laeuft parallel etwas anderes, zaehlt es mit.
  #   NUR_OFFENE  nur Ausschreibungen mit laufender Frist. Gemessen: von 940 nie
  #               analysierten Vorgaengen waren 110 offen — der Rest kostet dasselbe und
  #               nuetzt niemandem.
  #   OR_MODEL    wirkt erst, seit OpenRouter in `govisor/llm.py` vorne steht. Ein von
  #               aussen gesetztes Modell gilt NUR bei OpenRouter; stand es hinten, griffen
  #               zuerst die anderen Anbieter mit ihren eigenen, schwaecheren Modellen.
  #
  # PARALLEL von 40 auf 8: nicht aus Hoeflichkeit, sondern damit die Bremse greifen KANN.
  # Sie prueft alle zehn fertigen Vorgaenge; bei 40 gleichzeitigen Anfragen sind im Moment
  # des Abbruchs bis zu 40 unterwegs — bei 0,42 $ je Vorgang also bis zu 17 $ Ueberschuss.
  # Bei 8 sind es hoechstens 3 $.
  LIMIT=400 PARALLEL="${PARALLEL:-8}" \
    NUR_OFFENE="${NUR_OFFENE:-1}" \
    BUDGET_USD="${BUDGET_USD:-8}" \
    OR_MODEL="${OR_MODEL:-google/gemini-2.5-flash}" \
    PYTHONUNBUFFERED=1 \
    $PY scripts/analyze_docs.py >>"$LOG" 2>&1 \
    && sag "  Runde fertig" || sag "  ⚠ Runde abgebrochen"

  # Wie viele warten noch? Eine Zeile, damit man den Fortschritt im Log sieht, ohne
  # das Dashboard zu oeffnen.
  $PY - <<'PY' >>"$LOG" 2>&1 || true
import json, pathlib
w = pathlib.Path("web/data")
try:
    vt = set(json.loads((w / "doc-text-index.json").read_text()))
    an = set(json.loads((w / "doc-analysis.json").read_text()))
    print(f"  Stand: {len(an):,} analysiert · {len(vt - an):,} warten noch")
except Exception as e:
    print(f"  Stand unbekannt: {e}")
PY
  # ⛔ NICHT WEITERDREHEN, WENN NIEMAND MEHR LIEFERT. Am 2026-08-18 war das OpenRouter-
  # Guthaben leer; der Arbeiter holte trotzdem alle 30 Sekunden 400 Vorgaenge, bekam bei
  # jedem 402 und meldete „Runde fertig". Eine Stunde lang, mit vollem Log und ohne einen
  # einzigen Fortschritt. Wer nichts tun kann, soll schlafen und es sagen.
  if grep -q '"erschoepft": true' "$ROOT/data/.llm_stand.json" 2>/dev/null; then
    sag "Kein Guthaben bei keinem Anbieter — warte 30 min. Aufladen: openrouter.ai/credits"
    sleep 1800; continue
  fi
  sleep 30
done
