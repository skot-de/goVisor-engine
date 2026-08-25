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
# ⚠ DIE SPERRE GEHOERT AUF DIE INTERNE PLATTE — aus demselben Grund wie das Log unten.
# `data` ist ein Symlink auf ein externes Volume, und macOS vergibt den Zugriff darauf JE
# PROGRAMM: aus dem Terminal gestartet darf dieses Skript schreiben, als launchd-Dienst
# nicht. Bis zum 2026-08-25 lag die Sperre unter `data/`, und der Dienst scheiterte dort
# bei JEDEM Start mit „Operation not permitted" — auf stderr, in eine Datei, die niemand
# liest. Die alte Fassung machte einfach weiter: Sperre nie geschrieben, Trap ohne Wirkung,
# und der Dienst lief seit dem 24.08. voellig ungeschuetzt. Genau daran ist der Befund
# „Sperre fehlt, waehrend PID 88947 laeuft" haengengeblieben.
#
# Dieselbe Falle steckte schon einmal im Log dieses Skripts (18.08., „tee: Operation not
# permitted"). Sie zweimal zu treffen, reicht: was der Dienst zum Laufen braucht, liegt ab
# hier nicht mehr auf der Datenplatte.
EIGEN="${GOVISOR_ANALYSE_LOCK:-$HOME/Library/Caches/eu.govisor/analyse_arbeiter.lock}"
mkdir -p "$(dirname "$EIGEN")"
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
#
# ⚠ ZWEI RIEGEL, weil einer nachweislich nicht gehalten hat. Am 2026-08-25 lief dieser
# Arbeiter als PID 88947 seit dem Vorabend — und `data/.analyse_arbeiter.lock` gab es
# nicht. Ein zweiter Start haette also nichts vorgefunden und waere danebengelaufen.
#
#   1. VERZEICHNIS statt Datei. `mkdir` ist atomar, `[ -e ] && echo >` ist es nicht:
#      zwischen Pruefung und Schreiben passen zwei Starts gleichzeitig hindurch. Dieselbe
#      Form benutzen der Tageslauf und `_index_nach_tageslauf.sh` schon.
#   2. Der Trap raeumt NUR die EIGENE Sperre weg. Vorher loeschte er blind — ein spaet
#      sterbender Vorgaenger (er haengt bis zu 30 min in `sleep`) nahm damit die Sperre
#      seines Nachfolgers mit. Genau so verschwindet sie unbemerkt.
#   3. Und weil eine Sperre trotzdem verlorengehen kann, fragen wir zusaetzlich die
#      Prozessliste. Ein laufender Prozess luegt nicht.
_andere="$(pgrep -f 'analyse_arbeiter\.sh' 2>/dev/null | grep -v "^$$\$" | head -1)"
if [ -n "$_andere" ]; then
  echo "Ein Analyse-Arbeiter läuft bereits (PID $_andere)." ; exit 0
fi
if ! mkdir "$EIGEN" 2>/dev/null; then
  _alt="$(tr -d '[:space:]' < "$EIGEN/pid" 2>/dev/null)"
  if [ -n "$_alt" ] && kill -0 "$_alt" 2>/dev/null; then
    echo "Ein Analyse-Arbeiter läuft bereits (PID $_alt)." ; exit 0
  fi
  echo "Verwaiste Sperre (PID '${_alt:-?}' läuft nicht) — übernommen."
  rm -rf "$EIGEN" && mkdir "$EIGEN" || { echo "Sperre nicht übernehmbar." >&2; exit 75; }
fi
echo $$ > "$EIGEN/pid"
trap 'if [ "$(tr -d "[:space:]" < "$EIGEN/pid" 2>/dev/null)" = "$$" ]; then rm -rf "$EIGEN"; fi' EXIT

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

  # Wie viele warten noch? Die Zahl geht ins Log UND steuert die Pause.
  #
  # ⛔ SIE MUSS DIESELBE MENGE ZAEHLEN WIE DER LAUF. Hier stand bis zum 2026-08-25 eine
  # eigene Rechnung: Textindex minus Ergebnisdatei. Die kennt den NUR_OFFENE-Filter nicht.
  # Am 25.08. standen so 22 „Wartende" da, von denen kein einziger eine laufende Frist
  # hatte — der Lauf meldete folgerichtig „Zu analysieren: 0", die Pause unten griff
  # trotzdem nicht (sie verlangt exakt 0), und der Arbeiter drehte alle 30 Sekunden eine
  # Leerrunde. 31 davon in einer halben Stunde, jede mit einem Python-Start ueber eine
  # 358-MB-Datei. Dieselbe Klasse Fehler, die `rueckstau_etappen.sh` am 24.08. an
  # 37 Leerrunden gelernt hat.
  #
  # Jetzt sagt der Lauf selbst, was er uebrig gelassen hat (`analyze_docs.py` schreibt
  # `wartend` nach `.llm_stand.json`). Nebeneffekt: die 358-MB-Datei wird nicht mehr
  # jede Runde nur zum Zaehlen eingelesen.
  WARTEN="$($PY - 2>/dev/null <<'PYZ'
import json, pathlib
try:
    print(int(json.loads(pathlib.Path("data/.llm_stand.json").read_text())["wartend"]))
except Exception:
    print(-1)
PYZ
)"
  case "$WARTEN" in ''|*[!0-9-]*) WARTEN=-1 ;; esac
  if [ "$WARTEN" -lt 0 ]; then
    sag "  Stand: unbekannt (kein .llm_stand.json — Lauf abgebrochen?)"
  else
    sag "  Stand: $WARTEN warten noch"
  fi

  # ⛔ NICHT WEITERDREHEN, WENN NIEMAND MEHR LIEFERT. Am 2026-08-18 war das OpenRouter-
  # Guthaben leer; der Arbeiter holte trotzdem alle 30 Sekunden 400 Vorgaenge, bekam bei
  # jedem 402 und meldete „Runde fertig". Eine Stunde lang, mit vollem Log und ohne einen
  # einzigen Fortschritt. Wer nichts tun kann, soll schlafen und es sagen.
  if grep -q '"erschoepft": true' "$ROOT/data/.llm_stand.json" 2>/dev/null; then
    sag "Kein Guthaben bei keinem Anbieter — warte 30 min. Aufladen: openrouter.ai/credits"
    sleep 1800; continue
  fi

  # ⛔ UND NICHT, WENN ES NICHTS ZU TUN GIBT. Am 21.08. war der Rueckstau leer (5.596
  # analysiert, 0 warten) und dieser Arbeiter drehte trotzdem alle 30 Sekunden eine Runde
  # ueber nichts — bei normaler Prozesspriorität, waehrend der Dokumenten-Arbeiter, der als
  # EINZIGER Nachschub liefern kann, freiwillig hinten anstand. Nachschub kommt nicht
  # schneller, wenn man oefter nachsieht.
  if [ "$WARTEN" = "0" ]; then
    sag "  Nichts zu tun — warte 10 min auf Nachschub."
    sleep 600; continue
  fi
  sleep 30
done
