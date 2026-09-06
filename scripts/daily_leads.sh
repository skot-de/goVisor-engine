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

# ⛔ SELBSTKOPIE — GEGEN DEN FEHLER, DER DIESEN LAUF SCHON ZWEIMAL GETOETET HAT.
#
# Bash liest ein Skript WAEHREND der Ausfuehrung haeppchenweise nach. Wird die Datei in der
# Zwischenzeit geaendert, liest der laufende Prozess ab der naechsten Nachlade-Grenze an
# einer falschen Byte-Position weiter. Das Ergebnis sieht aus wie ein Syntaxfehler im Code
# und ist keiner:
#
#   2026-08-17 13:21  ABGEBROCHEN (Code 258) — line 787: syntax error near `else'
#   2026-08-19 00:13  ABGEBROCHEN (Code 258) — line 787: syntax error near `else'
#
# Beide Male lief ein Tageslauf, waehrend am Skript gearbeitet wurde; beim zweiten Mal war
# ich es selbst, mit sechs Aenderungen zwischen 23:35 und 23:55. Der Lauf war um 00:13 tot,
# und die Nacht damit verloren.
#
# Also: beim Start EINE Kopie anlegen und die ausfuehren. Wer danach am Original arbeitet,
# aendert eine Datei, die niemand mehr liest. `ROOT` steht hart oben, deshalb ist der Ort
# der Kopie gleichgueltig.
if [ "${GOVISOR_TAGESLAUF_KOPIE:-0}" != "1" ]; then
  _KOPIE="$(mktemp "${TMPDIR:-/tmp}/daily_leads.XXXXXX")" || {
    echo "Selbstkopie fehlgeschlagen — Lauf abgebrochen, bevor er beginnt."; exit 1; }
  cat "$0" > "$_KOPIE" && chmod +x "$_KOPIE" || {
    echo "Selbstkopie nicht schreibbar — Lauf abgebrochen."; exit 1; }
  # Alte Kopien aufraeumen (aelter als ein Tag). Kein `trap`, weil der Lauf weiter unten
  # seinen eigenen EXIT-Trap setzt und ein zweiter ihn ersetzen wuerde.
  find "${TMPDIR:-/tmp}" -maxdepth 1 -name 'daily_leads.*' -mtime +1 -delete 2>/dev/null || true
  export GOVISOR_TAGESLAUF_KOPIE=1
  exec /bin/bash "$_KOPIE" "$@"
fi

LOG_DIR="$ROOT/data/logs"
LOCK="$ROOT/data/.daily_leads.lock"
# ⚠ `-u`, UND ZWAR ZENTRAL. Zeile 291 leitet die ganze Ausgabe durch `tee` — also durch eine
# PIPE, und dort puffert Python blockweise. Der Waechter in `mit_grenze` misst aber die
# GROESSE der Logdatei: was im Puffer steht, sieht fuer ihn aus wie Stillstand.
# In der Nacht zum 2026-09-05 hat das simap.ch gekostet — der Schritt arbeitete, sagte 35
# Minuten nichts und wurde abgeschossen; CH blieb einen Tag alt. Das war kein simap-Problem,
# sondern galt fuer JEDEN Python-Schritt hier; bei simap fiel es nur zuerst auf, weil er
# ohnehin selten etwas sagt.
# ⚠ `$PY` wird an 77 Stellen UNQUOTED benutzt und vertraegt die zwei Woerter; ein `"$PY"`
# gibt es nirgends (geprueft). Wer eines einfuehrt, bricht alles.
PY="python3 -u"

# ── ARBEITSSPEICHER UND TEMP AUF DIE EXTERNE PLATTE ───────────────────────────────────────
#
# Gemessen 2026-08-14, nachdem der Rechner wegen vollem Speicher neu gestartet werden musste:
#
#   /  (intern)          228 GB, davon 36 GB frei   ← hier landete die Arbeit
#   /Volumes/goVisor     1,8 TB, davon 1,6 TB frei  ← hier liegen die Daten
#
# `data/` ist ein Symlink auf die externe Platte, die DATEN liegen also richtig. Die ARBEIT
# nicht: Pythons `tempfile` zeigt auf /var/folders (intern), und DuckDBs Auslagerung steht
# per Vorgabe auf `.tmp` — relativ zum Arbeitsverzeichnis, und das Repo liegt intern.
#
# Bei 16 GB RAM, 2 GB Swap und 89 GB Archiven reicht das nicht. Beides wandert deshalb auf
# die grosse Platte. Faellt sie aus, greift der Daten-Guard weiter unten ohnehin.
if [ -d "$ROOT/data" ]; then
  export TMPDIR="$ROOT/data/.tmp"
  mkdir -p "$TMPDIR"
  # DuckDB kennt KEINE Umgebungsvariable dafuer — die Einstellung geht nur pro Verbindung,
  # und davon gibt es 125 im Projekt. Der Hebel ist stattdessen die Vorgabe selbst: DuckDB
  # legt seine Auslagerung nach `.tmp` RELATIV ZUM ARBEITSVERZEICHNIS. Ist `.tmp` im Repo
  # ein Symlink auf die grosse Platte, greift das fuer alle 125 Verbindungen, ohne dass eine
  # Zeile Code sich aendert.
  [ -L "$ROOT/.tmp" ] || ln -s data/.tmp "$ROOT/.tmp" 2>/dev/null || true
fi
MONTH="$(date +%Y-%m)"
TODAY="$(date +%Y-%m-%d)"

# --- Lock: keine Überlappung, falls ein Lauf noch dreht (atomar via mkdir) ---
#
# ZWEI FEHLER, die am 2026-08-14 zugeschlagen haben und hier behoben sind:
#
# (1) VERWAISTER LOCK BLOCKIERTE ALLES. Der `trap` raeumt bei einem SAUBEREN Ende — er
#     feuert NICHT bei SIGKILL, und genau das passiert, wenn der Rechner mitten im Lauf
#     schlafen geht. Gefunden: ein Lock vom 13.08. 20:42, leer, Prozess laengst tot. Jeder
#     Lauf seither brach sofort ab. Der Lock traegt jetzt die PID, und ein Lock ohne
#     lebenden Prozess wird uebernommen statt respektiert.
#
# (2) ABBRUCH MELDETE ERFOLG. `exit 0` heisst fuer launchd „Lauf war erfolgreich". Ein
#     blockierter Lauf ist aber KEIN erfolgreicher — die Daten veralten, und niemand sieht
#     es. Jetzt `exit 75` (EX_TEMPFAIL): „nicht gelaufen, spaeter erneut versuchen".
# ── SCHREIBTEST AUF DIE DATENPLATTE — VOR ALLEM ANDEREN ───────────────────────────────
#
# Gefunden am 2026-08-15, nachdem Sven fragte, ob der Tageslauf sauber laeuft. Er lief seit
# Tagen ueberhaupt nicht — und zwar unsichtbar. Das launchd-Fehlerlog sagte:
#
#   2026-08-14 13:00:03 ⚠ Verwaister Lock — uebernommen.
#   rm: .../data/.daily_leads.lock: Operation not permitted
#   Lock nicht uebernehmbar.
#
# Nicht „Lock haengt", sondern „Operation not permitted". `data/` ist ein Symlink auf die
# externe SSD, und macOS verweigert HINTERGRUNDDIENSTEN den Zugriff auf externe Volumes,
# solange die Freigabe fehlt. Aus einem Terminal geht es (die App hat die Freigabe), aus
# launchd nicht.
#
# ZWEI FEHLER MACHTEN DAS UNSICHTBAR:
#  · Der Lock liegt SELBST auf der Platte — der Lauf starb an ihm, bevor er irgendetwas
#    pruefen konnte, und die Meldung sprach von einem Lock-Problem statt von Rechten.
#  · Der vorhandene Daten-Guard weiter unten prueft nur, ob eine Datei LESBAR ist (`-e`).
#    Lesen war erlaubt, Schreiben nicht — er schlug also nie an.
#
# Deshalb steht der Schreibtest jetzt VOR dem Lock und prueft, was wirklich gebraucht wird.
# Ausgabe auf stderr, weil launchd sie nach ~/Library/Logs/govisor-launchd.err.log lenkt —
# die einzige Datei, die noch beschreibbar ist, wenn die Platte gesperrt ist.
_PROBE="$ROOT/data/.schreibtest.$$"
if ! mkdir "$_PROBE" 2>/dev/null; then
  {
    echo "$(date '+%F %T') FEHLER: In data/ kann nicht geschrieben werden — abgebrochen."
    echo "  Pfad:  $(readlink "$ROOT/data" 2>/dev/null || echo "$ROOT/data")"
    echo "  Grund: sehr wahrscheinlich fehlende macOS-Freigabe fuer externe Volumes."
    echo "         Aus einem Terminal funktioniert es, aus launchd nicht — das ist das Muster."
    echo "  Fix:   Systemeinstellungen → Datenschutz & Sicherheit → Festplattenvollzugriff"
    echo "         → /bin/bash hinzufuegen (der Dienst laeuft als bash-Skript)."
    echo "         Danach: launchctl kickstart -k gui/\$UID/de.skot.govisor.daily"
  } >&2
  exit 77                       # EX_NOPERM — nicht 75: hier hilft kein spaeterer Versuch
fi
rmdir "$_PROBE" 2>/dev/null || true

# ── SPEICHER PRUEFEN ──────────────────────────────────────────────────────────────────
#
# Ein Playwright-Schritt braucht Luft. Am 2026-08-16 waren beim Start 1,4 GB frei, das
# Betriebssystem raeumte den Browser eines Abrufers ab, und der Lauf fror ein. Gemessen
# wird frei + INAKTIV: inaktive Seiten gibt macOS auf Anforderung heraus, sie als belegt
# zu zaehlen wuerde fast jeden Start verhindern.
_frei_gb() {
  vm_stat | awk '/page size of/{ps=$8} /Pages free/{f=$3} /Pages inactive/{i=$3}
                 END{gsub(/\./,"",f); gsub(/\./,"",i); printf "%.1f", (f+i)*(ps?ps:4096)/1073741824}'
}
_MIN_GB=${GOVISOR_MIN_GB:-2.0}
_hab=$(_frei_gb)
if awk -v a="$_hab" -v b="$_MIN_GB" 'BEGIN{exit !(a < b)}'; then
  echo "⛔ Nur ${_hab} GB Speicher frei (noetig: ${_MIN_GB} GB) — Tageslauf NICHT gestartet." >&2
  echo "   Playwright-Abrufe brauchen Luft; ohne sie friert der Lauf ein statt zu scheitern." >&2
  exit 75
fi
echo "  Speicher beim Start: ${_hab} GB frei"

# ── WARTEN, WENN EIN INDEX-NEUAUFBAU LAEUFT ──────────────────────────────────────────
#
# WARUM. Am 2026-08-15 startete dieser Lauf um 22:00 planmaessig, waehrend ein
# `index-docs --neu-aufbauen` noch bis 23:50 lief. Drei Index-Arbeiter à 2 GB plus die
# Abrufer dieses Laufs liessen 1,4 GB frei — das Betriebssystem raeumte den Browser eines
# Abrufers ab, und der Lauf fror 10,5 Stunden ein.
#
# Der eigene Lock schuetzt NUR gegen einen zweiten Tageslauf. Gegen alles andere, was auf
# derselben Maschine dieselben Verzeichnisse und denselben Speicher braucht, schuetzt er
# nicht — dafuer gibt es `scripts/laeuft_was.sh`, und ausgerechnet der Lauf, der es am
# noetigsten hat, benutzte es nicht.
#
# WARUM WARTEN UND NICHT UEBERSPRINGEN: ein Neuaufbau dauert ~5 h und ist selten. Startet
# der Lauf danach, ist er nur spaeter. Startet er waehrenddessen, faellt er aus — und zwar
# nicht sichtbar, sondern als Haenger. Nach der Obergrenze wird bewusst ABGEBROCHEN statt
# trotzdem gestartet: ein ausgefallener Lauf steht am naechsten Tag im Altersbericht, ein
# eingefrorener steht dort gar nicht.
_INDEX_WARTE=${GOVISOR_INDEX_WARTE:-10800}      # 3 h
_bis=$(( $(date +%s) + _INDEX_WARTE ))
while pgrep -f "cli index-docs" >/dev/null 2>&1; do
  if [ "$(date +%s)" -ge "$_bis" ]; then
    echo "⛔ Index-Neuaufbau laeuft seit ueber $(( _INDEX_WARTE / 3600 )) h — Tageslauf NICHT gestartet." >&2
    echo "   Grund: gemeinsamer Speicher und derselbe Dokumentbaum (s. 2026-08-16)." >&2
    exit 75                      # EX_TEMPFAIL — ein spaeterer Versuch kann klappen
  fi
  echo "  … Index-Neuaufbau aktiv, warte (Pruefung alle 5 min)"
  sleep 300
done

if ! mkdir "$LOCK" 2>/dev/null; then
  _alt="$(cat "$LOCK/pid" 2>/dev/null | tr -d '[:space:]')"
  if [ -n "$_alt" ] && kill -0 "$_alt" 2>/dev/null; then
    echo "$(date '+%F %T') Lauf laeuft bereits (PID $_alt) — abgebrochen." >&2
    exit 75
  fi
  echo "$(date '+%F %T') ⚠ Verwaister Lock (PID '${_alt:-unbekannt}' laeuft nicht) — uebernommen." >&2
  rm -rf "$LOCK" && mkdir "$LOCK" || { echo "Lock nicht uebernehmbar." >&2; exit 75; }
fi
echo $$ > "$LOCK/pid"
# ── ABSCHLUSSMELDUNG ──────────────────────────────────────────────────────────────────
#
# Sie steht im `trap` und damit an JEDEM Ende — auch bei Abbruch, Zeitgrenze oder Absturz.
# Genau das fehlte: ein Lauf, der durchlief, hinterliess ein langes Log, und ein Lauf, der
# einfror, hinterliess GAR NICHTS. Die eine Zeile hier sagt in beiden Faellen, woran man ist,
# ohne 4.000 Zeilen Log zu lesen.
abschluss() {
  local rc=$?
  local dauer=$(( SECONDS / 60 ))
  # `$LOG` (nicht LOGFILE) — und KEIN `|| echo 0`: `grep -c` schreibt bei null Treffern
  # bereits „0" und beendet sich trotzdem mit 1. Das angehaengte echo haette eine zweite
  # Null erzeugt und die Meldung waere „0\n0 Warnungen" geworden.
  #
  # ⚠ NUR ZEILEN, DIE MIT ⚠ BEGINNEN. Gezaehlt wurde jedes Vorkommen des Zeichens
  # irgendwo in der Zeile — und das Zeichen dient an vielen Stellen als INLINE-MARKER,
  # nicht als Warnung: „⚠2024=10Mon" markiert im Marktpuls eine Serie, die mitten im Jahr
  # beginnt, „⚠ unvollstaendig" steht am Ende jeder Healy-Hudson-Landeszeile. Ergebnis
  # (gemessen ueber acht Laeufe vom 20. bis 25.08.): die Zahl stand bei 18, 18, 18, 18,
  # 18, 13, 18, 19. Eine Kennzahl, die jede Nacht denselben Wert hat, liest niemand mehr —
  # und ein Lauf, in dem wirklich etwas kaputtging, saehe genauso aus.
  #
  # Mit dem strengeren Filter: 3, 3, 3, 3, 3, 4, 3, 5. Am 25.08. sind die zwei zusaetz-
  # lichen der Verdrahtungsbefund und die Deflator-Naeherung — also genau das, was man
  # sehen will. Wer die Rohzahl braucht: `grep -c '⚠' data/logs/daily-*.log`.
  local warn; warn=$(grep -cE '^[[:space:]]*⚠' "${LOG:-/dev/null}" 2>/dev/null); warn=${warn:-0}
  local zustand="fertig"
  [ "$rc" -ne 0 ] && zustand="ABGEBROCHEN (Code $rc)"
  [ -n "$_SCHRITT_NAME" ] && [ "$rc" -ne 0 ] && zustand="$zustand bei: $_SCHRITT_NAME"
  # Uebersprungene Abrufer GEHOEREN in den Bericht. Ohne sie sieht ein gekuerzter Lauf
  # aus wie ein vollstaendiger: die Auswertung lief ja durch, es fehlen bloss die
  # Dokumente, die niemand geholt hat. Genau diese stille Kuerzung soll sichtbar sein.
  local gekuerzt=""
  [ "${_ABRUF_UEBERSPRUNGEN:-0}" -gt 0 ] \
    && gekuerzt=" · ${_ABRUF_UEBERSPRUNGEN} Abrufe uebersprungen (Zeitbudget)"
  {
    printf '%s  %s · %d min · %s Warnungen%s\n' \
      "$(date '+%Y-%m-%d %H:%M')" "$zustand" "$dauer" "$warn" "$gekuerzt"
  } > "$ROOT/data/logs/letzter_lauf.txt"
  echo ""
  echo "── $(cat "$ROOT/data/logs/letzter_lauf.txt")"
  # Nur die EIGENE Sperre wegraeumen. Ein blindes `rm -rf` nimmt die Sperre eines
  # Nachfolgers mit, falls dieser Lauf spaet stirbt und der naechste sie inzwischen
  # uebernommen hat. Dritte Stelle derselben Klasse — die anderen beiden stehen in
  # `analyse_arbeiter.sh` und `_index_nach_tageslauf.sh`.
  if [ "$(tr -d '[:space:]' < "$LOCK/pid" 2>/dev/null)" = "$$" ]; then
    rm -rf "$LOCK" 2>/dev/null
  fi
}
trap abschluss EXIT

# ── PHASEN ────────────────────────────────────────────────────────────────────────────────
#
# WARUM GETRENNT. Der erste Vollauf (2026-08-14) hat die Zeitachse offengelegt:
#
#   10:49  Gold fertig — die Leads EXISTIEREN
#   10:49  Vergabeunterlagen holen                       70 min
#   11:58  Entpacken, Volltext-Index, Signale, LV      >100 min
#   13:52  Frontend-Export                             ← erst HIER sieht sie ein Nutzer
#
# Die Leads waren drei Stunden fertig und kamen trotzdem nicht an, weil der Export der
# letzte Schritt ist und hinter der Dokumentenarbeit steht. Das ist keine Laufzeitfrage,
# das ist Latenz auf dem Produkt — und sie trifft die Alarme mit: eine Frist-Warnung an
# einem Lead, den es erst drei Stunden spaeter gibt, geht drei Stunden spaeter raus.
#
# Gemessen, warum das zaehlt: 22,4 % der offenen DE-Leads haben WENIGER ALS SIEBEN TAGE
# Restfrist (3.379 von 15.081). Dort ist ein Tag Verzoegerung ein Fuenftel der Zeit, die
# der Bieter ueberhaupt hat.
#
#   leads         Quellen → Firewall → Gold           ~40 min · mehrmals taeglich
#   dokumente     Unterlagen → Index → Signale → LV   ~2 h    · nachts
#   alles         beides (Vorgabe, rueckwaertskompatibel)
#
# `veroeffentlichen` (Marktpuls, Frontend-Export, Supabase) laeuft in BEIDEN Phasen — das
# ist der Kern der Entkopplung. Sonst haette man die Dokumente entkoppelt und die Leads
# warteten trotzdem.
#
# Der Zuwachs am naechsten Tag ist kein Fehler, sondern die Wahrheit: der Abruf ist
# absichtlich langsam, weil wir fremde Portale hoeflich behandeln. Der Fehler waere, den
# Lead so lange zurueckzuhalten.
PHASE="${1:-alles}"
case "$PHASE" in
  leads|dokumente|alles) ;;
  *) echo "Unbekannte Phase '$PHASE'. Erlaubt: leads | dokumente | alles" >&2; exit 64 ;;
esac
phase_an() { [ "$PHASE" = "alles" ] || [ "$PHASE" = "$1" ]; }
echo "Phase: $PHASE"

# --- Daten-Guard: externe Platte / Symlink muss aufgelöst sein ---
if [ ! -e "$ROOT/data/gold/DE/lead_export.parquet" ]; then
  echo "$(date '+%F %T') FEHLER: data/ nicht verfügbar (externe Platte nicht gemountet?) — abgebrochen." >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
# STARTZEIT IM NAMEN. Vorher hiess die Datei nur `daily-<datum>.log` — zwei Laeufe am
# selben Tag (13:00 und 22:00, oder ein Nachlauf von Hand) schrieben also in DIESELBE
# Datei. Das Dashboard las sie als EINEN Lauf, fand das Ende des ersten und meldete
# „durchgelaufen", waehrend der zweite noch arbeitete (gesehen 2026-08-16).
#
# Ein Lauf = eine Datei. Das trennt auch die Historie: Schrittdauern zu vergleichen ist
# unmoeglich, solange zwei Laeufe ineinander stehen.
LOG="$LOG_DIR/daily-$TODAY-$(date '+%H%M').log"
exec > >(tee -a "$LOG") 2>&1
echo "════════════════════════════════════════════════════════════════"
echo "goVisor Tageslauf  $(date '+%F %T')  (Monat $MONTH, Stichtag $TODAY)"
echo "════════════════════════════════════════════════════════════════"

# Meldet die Dauer des VORIGEN Schritts. Am 2026-08-14 stand der Volltext-Index 106 Minuten
# ohne Ausgabe; ob er arbeitete oder haengt, war nur ueber `sample` auf die Prozess-ID
# herauszufinden. Ein Lauf, der nachts unbeaufsichtigt arbeitet, muss das selbst sagen.
_SCHRITT_START=0
_SCHRITT_NAME=""
# Obergrenze fuer den GANZEN Lauf. Normal braucht er 3-4 h; 8 h heisst, dass etwas nicht
# stimmt, das keine Einzelgrenze gefangen hat. Geprueft wird an der SCHRITTGRENZE und nicht
# per Hintergrund-Waechter: seit jeder Netz-Schritt bei 45 min gekappt wird, kommen
# Schrittgrenzen regelmaessig — ein zweiter Waechterprozess waere Mechanik ohne Mehrwert.
GRENZE_GESAMT=${GOVISOR_GRENZE_GESAMT:-28800}   # 8 h

# ══ MODELLMARKT: TAEGLICH SCHAUEN, VOR DEM LAUF ══════════════════════════════════════
#
# Sven, 2026-08-23: „am besten machst du die abfrage bevor wir unseren lauf starten, dann
# passt sich im idealfall der anbieter und/oder das modell automatisch an" — und: „nicht
# einmal im monat checken, sondern jeden tag. die preise sind variable."
#
# Zwei Schritte, bewusst getrennt nach dem, was sie kosten:
#
#   --pruefen   EIN HTTP-Aufruf, keine Token, kein Guthaben. Holt den Katalog (422 Modelle),
#               legt den Tagesstand ab, vergleicht mit gestern, reiht lohnende Kandidaten
#               in den Pruefstand ein und frischt die Modellwahl auf.
#   pruefung    Gibt Geld aus — aber aus einem EIGENEN Topf (GOVISOR_TEST_USD, Vorgabe
#               0,50 $/Tag) und hoechstens fuer zwei Kandidaten. Wer besteht, wird
#               freigegeben; die naechste Analyserunde nimmt ihn dann von selbst.
#
# ⚠ Beide duerfen den Lauf NIE aufhalten. Faellt der Katalog aus, bleibt es beim zuletzt
# gewaehlten Modell — ein Waechter, der die Produktion blockiert, ist teurer als jedes
# Modell, das er einsparen koennte.
echo ""
echo "── Modellmarkt"
$PY scripts/modellwaechter.py --pruefen \
  || echo "  ⚠ Modellkatalog nicht erreichbar — es bleibt bei der zuletzt getroffenen Wahl."
$PY scripts/modellpruefung.py \
  || echo "  ⚠ Modellpruefung uebersprungen — die Warteschlange bleibt stehen."

# ══ RESERVE FUER DIE AUSWERTUNG ══════════════════════════════════════════════════════
# Wie viel Zeit muss am Ende uebrig bleiben, damit Entpacken, Signale, Leistungs-
# verzeichnisse, Marktpuls, Frontend-Export, Supabase, gap_effects und der Ertragsbericht
# noch durchlaufen?
#
# NICHT geschaetzt, sondern aus `data/logs/daily-*.log` ausgezaehlt — die GANZE Ernte,
# also alles hinter der Marke unten (10 Schritte, Stand 2026-08-30):
#
#     letzte sieben Laeufe:  45 · 56 · 60 · 65 · 77 · 94 · 99 min
#
# ⚠ DIESE ZAHL IST EINMAL VERROTTET, UND ZWAR STILL. Hier stand „zusammen ~45 min, 90 min
# ist das Doppelte davon". Am 2026-08-30 nachgemessen: der schlimmste Fall lag bei 99 min —
# die Reserve war also nicht das Doppelte, sondern das **0,91-fache**. Sie war gar keine
# Reserve mehr. Aufgefallen ist es nicht im Betrieb, sondern erst beim Nachrechnen: die
# Laeufe blieben mit 87 bis 184 min weit unter der 8-h-Grenze, die Reserve wurde also nie
# geprueft. Sie haette beim ersten langen Abruf gegriffen — und genau dann versagt.
#
# Zwei Gruende fuer das Wachstum, beide legitim: die Tabelle zaehlte nur 7 der 10 Schritte
# (`Dokument-Dubletten` allein kostet 18 min und kam spaeter dazu), und die Ernte skaliert
# mit der Zahl NEUER Dokumente — ein Abruf, der endlich einmal durchlaeuft, macht sie teuer.
#
# 200 min ist wieder das Doppelte des gemessenen schlimmsten Falls. Wer hier knapp rechnet,
# bricht den Lauf an der Stelle ab, an der er sich gerade gelohnt haette.
#
# `tests/test_daily.py::test_ernte_reserve_deckt_die_gemessene_ernte` rechnet das gegen die
# echten Protokolle nach und wird rot, wenn der Abstand wieder schmilzt.
ERNTE_RESERVE=${GOVISOR_ERNTE_RESERVE:-12000}   # 200 min

# Darf noch ein Abrufer starten? Die Beschaffung ist nach oben offen (gemessen 1.622 min
# im schlimmsten Fall), die Auswertung dahinter ist es nicht. Also teilen sich ALLE
# Abrufer einen Topf: was nach Abzug der Reserve uebrig ist.
#
# Geprueft wird VOR dem Start, nicht waehrenddessen: ein Schritt, der mittendrin
# abgeschnitten wird, hinterlaesst halb geladene Pakete. `mit_grenze` deckelt zusaetzlich
# den einzelnen Schritt — beides zusammen, nicht eines statt des anderen.
abruf_erlaubt() {
  local rest=$(( GRENZE_GESAMT - SECONDS ))
  if [ "$rest" -lt "$ERNTE_RESERVE" ]; then
    echo ""
    echo "⏭ $* — uebersprungen."
    echo "   Nur noch $(( rest / 60 )) min bis zur Gesamtgrenze, reserviert sind $(( ERNTE_RESERVE / 60 )) min"
    echo "   fuer Auswertung und Veroeffentlichung. Der Abruf holt das morgen nach."
    _ABRUF_UEBERSPRUNGEN=$(( ${_ABRUF_UEBERSPRUNGEN:-0} + 1 ))
    return 1
  fi
  return 0
}
_ABRUF_UEBERSPRUNGEN=0

step() {
  if [ -n "$_SCHRITT_NAME" ]; then
    printf '  ⏱ %s — %ds\n' "$_SCHRITT_NAME" "$(( SECONDS - _SCHRITT_START ))"
  fi
  if [ "$SECONDS" -ge "$GRENZE_GESAMT" ]; then
    echo ""
    echo "⛔ Gesamtlaufzeit ueber $(( GRENZE_GESAMT / 3600 )) h — Lauf wird hier beendet."
    echo "   Erledigt bis: ${_SCHRITT_NAME:-nichts}. Der Rest faellt heute aus."
    exit 75
  fi
  _SCHRITT_NAME="$*"; _SCHRITT_START=$SECONDS
  echo ""; echo "▶ $(date '+%T')  $*"
}

# ── ZWISCHENZEIT JE SKRIPT ────────────────────────────────────────────────────────────
#
# WARUM. Der Frontend-Export ist EIN Schritt mit zehn Skripten darin. Am 2026-09-03 stand
# dafuer im Protokoll eine einzige Zahl (Median 575 s), und die Frage „welches davon" war
# nur durch Subtraktion zu beantworten: sechs Skripte von Hand messen, den Rest ausrechnen.
# Das Ergebnis war eine Schaetzung mit Fehlerbalken, wo eine Messung haette stehen koennen.
#
# ⚠ AUF STDERR, NICHT AUF STDOUT. Zwei der Aufrufe schicken ihre Ausgabe nach `/dev/null`;
# stuende die Zeile auf stdout, verschwaende sie mit. `exec > >(tee …) 2>&1` weiter oben
# fuehrt stderr ohnehin ins selbe Protokoll.
#
# ⚠ RUECKGABEWERT DURCHREICHEN. Die Aufrufer haengen `|| echo "⚠ …"` an oder stehen in
# einem `if`; verschluckt der Helfer den Code, meldet kein einziger Schritt mehr einen
# Fehlschlag — und ein stiller Ausfall ist genau das, was dieser Lauf sonst ueberall
# bekaempft.
teil() {
  local name="$1"; shift
  local start=$SECONDS
  "$@"
  local code=$?
  printf '    ⏱ %s — %ds\n' "$name" "$(( SECONDS - start ))" 1>&2
  return $code
}

# ── ZEITGRENZE JE SCHRITT ─────────────────────────────────────────────────────────────
#
# WARUM. Am 2026-08-16 fror der Lauf 10,5 Stunden ein. Der Playwright-Browser des
# Healy-Hudson-Abrufers wurde vom Betriebssystem wegen Speichermangels abgeraeumt (der
# Index-Neuaufbau lief parallel); der Python-Client wartete danach unbegrenzt auf eine
# Verbindung zu einem Prozess, den es nicht mehr gab. Die Zeitgrenzen IM Modul (90 s
# Standard, 180 s je Download) greifen genau dann nicht: sie setzen voraus, dass der
# Browser antwortet. Ist er weg, laeuft keine Uhr mehr.
#
# Die Grenze gehoert deshalb NACH AUSSEN, wo sie nicht davon abhaengt, dass der
# ueberwachte Prozess noch gesund ist. `timeout` gibt es auf diesem Mac nicht (kein
# GNU coreutils), also von Hand — mit Wanduhr, nicht mit Rundenzaehlung.
mit_grenze() {
  local grenze=$1; shift
  # In der Beschaffungsphase erst fragen, ob der gemeinsame Topf noch etwas hergibt.
  # VOR dem Start, nicht waehrenddessen: ein mittendrin abgeschnittener Abruf hinterlaesst
  # halb geladene Pakete.
  if [ "${_ABRUF_PHASE:-0}" = "1" ]; then
    # Beschaffung abgeschaltet? Dann gar nicht erst starten (s. `_ABRUF_AUS` weiter unten).
    [ "${_ABRUF_AUS:-0}" = "1" ] && return 0
    abruf_erlaubt "${_SCHRITT_NAME:-Abruf}" || return 0
  fi
  "$@" &
  local kind=$!
  local ende=$(( $(date +%s) + grenze ))
  local regung=$(date +%s)
  local groesse=0
  while kill -0 "$kind" 2>/dev/null; do
    local jetzt g grund=""
    jetzt=$(date +%s)
    # STILLSTAND. Der eigentliche Waechter: schreibt der Schritt noch? Das Log waechst,
    # solange er arbeitet — auch langsam. Bleibt es 30 min unveraendert, haengt er.
    g=$(wc -c < "${LOG:-/dev/null}" 2>/dev/null || echo 0)
    if [ "$g" != "$groesse" ]; then groesse=$g; regung=$jetzt; fi
    if [ $(( jetzt - regung )) -ge "$STILLSTAND" ]; then
      grund="keine Ausgabe seit $(( STILLSTAND / 60 )) min"
    elif [ "$jetzt" -ge "$ende" ]; then
      grund="Obergrenze $(( grenze / 60 )) min erreicht"
    fi
    if [ -n "$grund" ]; then
      echo "  ⚠ Schritt abgebrochen — $grund."
      kill -TERM "$kind" 2>/dev/null
      sleep 10
      kill -KILL "$kind" 2>/dev/null
      # Verwaiste Browser mitnehmen, sonst fressen sie den Speicher des naechsten Schritts.
      pkill -f "playwright" 2>/dev/null
      wait "$kind" 2>/dev/null
      return 124
    fi
    sleep 15
  done
  wait "$kind"
}

# ── KALIBRIERUNG ──────────────────────────────────────────────────────────────────────
#
# STILLSTAND ist der eigentliche Waechter, die Obergrenze nur der Rueckfall. Die erste
# Fassung hatte es umgekehrt: 45 min pauschal — gemessen an den Logs haette das
# `subreport` (87,6 min) und `Healy-Hudson-Unterlagen` (55,6 min) JEDE NACHT abgeschossen,
# beides gesunde Laeufe. Nach Gefuehl gesetzte Grenzen sind hier besonders teuer, weil ihr
# Fehlschlag wie ein Portal-Problem aussieht.
#
# Der Haenger vom 2026-08-16 lief 719 min OHNE eine einzige Ausgabezeile. Genau das faengt
# der Stillstands-Waechter — und zwar unabhaengig davon, wie lange ein Schritt normal braucht.
STILLSTAND=${GOVISOR_STILLSTAND:-1800}          # 30 min ohne Ausgabe = haengt
GRENZE_ABRUF=${GOVISOR_GRENZE_ABRUF:-7200}      # 2 h  Rueckfall, Regelfall
GRENZE_LANG=${GOVISOR_GRENZE_LANG:-14400}       # 4 h  subreport (gemessen 87,6 min)

# Zeitlimit fuer einen Schritt. `timeout` gibt es auf macOS nicht von Haus aus, deshalb
# selbst gebaut: Kind starten, Wecker danebenstellen, wer zuerst kommt gewinnt.
#
# Gemessen 2026-08-14: `index-docs` lief 106 Minuten an einem einzelnen Dokument fest
# (Stack zeigte reine String-Arbeit, kein Fortschritt) und blockierte die restlichen fuenf
# Schritte. Ein Schritt ohne Obergrenze, der unbeaufsichtigt laeuft, ist ein Lauf, der
# irgendwann nicht mehr fertig wird — und niemand merkt es, weil er formal noch arbeitet.
mit_limit() {
  local grenze="$1"; shift
  ( "$@" ) & local kind=$!
  ( sleep "$grenze"; kill -TERM "$kind" 2>/dev/null; sleep 5; kill -9 "$kind" 2>/dev/null ) & local wecker=$!
  local rc=0; wait "$kind" 2>/dev/null || rc=$?
  kill "$wecker" 2>/dev/null; wait "$wecker" 2>/dev/null || true
  if [ "$rc" -ne 0 ]; then
    printf '  ⚠ nach %ss abgebrochen oder fehlgeschlagen (rc=%s)\n' "$grenze" "$rc"
  fi
  return "$rc"
}
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
if phase_an leads; then
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
mit_grenze "$GRENZE_ABRUF" $PY -m govisor.cli ingest-simap --country CH --max-pages 30 --silver \
  && echo "  simap ok." || echo "  ⚠ simap.ch fehlgeschlagen — CH bleibt auf altem Stand."

# AT bekommt wie CH beide Kanäle: OffeneVergaben.at (national, auch unterschwellig) und
# TED-AT (EU-Schwelle). Anders als bei CH braucht es hier KEINEN Backfill — die TED-AT-
# Historie liegt über die Monatsarchive vollständig vor (180.061 Notices ab 2004, gegen die
# TED-API auf 99,8–100 % geprüft). Gefehlt hat allein der Tagesabruf: das Monatsarchiv
# erscheint mit Verzug, dadurch stand TED-AT auf dem Stand vom 29. Juni.
step "TED-Live AT"
$PY scripts/fetch_ted_live.py --country AT --workers 3 \
  && echo "  TED-AT ok." || echo "  ⚠ TED-AT fehlgeschlagen — AT bleibt auf OffeneVergaben allein."

# ⚠ LU BRAUCHT DEN LIVE-ABRUF DRINGENDER ALS JEDES ANDERE LAND. Luxemburg haelt die
# Vergabeunterlagen nach Fristende NICHT vor (gemessen 2026-09-03, dieselbe Gruppe wie DE).
# Wer aufs Monatsarchiv wartet, bekommt die Bekanntmachung — die Unterlagen sind dann weg.
# Der Tagesabruf ist hier keine Frischhaltung, sondern die einzige Gelegenheit.
step "TED-Live LU"
$PY scripts/fetch_ted_live.py --country LU --workers 3 \
  && echo "  TED-LU ok." || echo "  ⚠ TED-LU fehlgeschlagen — ⏳ heutige LU-Unterlagen moeglicherweise verloren."

step "OffeneVergaben.at (AT)"
mit_grenze "$GRENZE_ABRUF" $PY -m govisor.cli ingest-atverg --country AT --silver \
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
mit_grenze "$GRENZE_ABRUF" $PY -m govisor.dtvp --regeln VOB --typen Tender --max-seiten 40 --stop-nach-bekannten 40 --silber \
  || echo "  ⚠ DTVP-Import fehlgeschlagen — fremdes Portal, der Lauf geht ohne weiter."

# NETSERVER (Administration Intelligence) — FUENF Laenderportale: Bremen, Sachsen,
# Mecklenburg-Vorpommern, Baden-Wuerttemberg und Hessen (HAD).
#
# ⚠ Hessen laeuft ueber einen EIGENEN Pfad (`hole_had`, Playwright): unter /NetServer/
# liegen dort nur die Detailseiten, die Suche ist ein POST-Formular, das sich per curl
# nicht reproduzieren liess. Faellt Playwright aus, meldet der Lauf das und macht ohne
# Hessen weiter — die vier anderen brauchen keinen Browser.
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
# ⚠ BERLIN UND SAARLAND sind seit 2026-08-14 in der Portal-Tabelle. Sie fahren dieselbe
# NetServer-Software wie die fuenf anderen und waren nie „nicht angebunden" — sie standen
# nur nicht drin. Erster Lauf: 98 (BE) + 58 (SL) Bekanntmachungen, davon 44 unterschwellig.
# Sie laufen SOFORT mit, nicht hinter dem Schalter unten: es ist derselbe erprobte Pfad.
step "NetServer-Bekanntmachungen (HB/SN/MV/BW/HE/BE/SL, ober- und unterschwellig)"
mit_grenze "$GRENZE_ABRUF" $PY -m govisor.netserver --portale hb,sn,mv,bw,he,be,sl --kategorien tender,vorinfo,zuschlag --silber \
  || echo "  ⚠ NetServer-Import fehlgeschlagen — fremde Portale, der Lauf geht ohne weiter."

# ── NEUE QUELLEN, SCHARF ────────────────────────────────────────────────────────────────
#
# Fuenf Schritte: healyhudson (Bekanntmachungen) und vier Unterlagen-Fetcher.
#
# SCHARFGESCHALTET am 2026-08-14 (Svens Entscheidung). Der Schalter bleibt, aber die Vorgabe
# ist jetzt AN — abschalten mit `GOVISOR_NEUE_QUELLEN=0`.
#
# ⚠ WAS DABEI GILT UND NICHT UEBERSEHEN WERDEN DARF: die vier Unterlagen-Fetcher holen
# Pakete von 10-188 MB (ein Ausreisser 335 MB). Der Volltext-Index hat seit heute eine
# Groessen-Sperre bei 50 MB — die grossen Pakete landen also auf der Platte, aber NICHT im
# Index; sie bekommen `status='zu_gross'` und sind damit gezaehlt.
#
# Das ist bewusst so: die Unterlagen werden fuer Musterableitung, Dokumentvorschlaege und
# Textbaustein-Wiederverwendung GESAMMELT, auch wenn der heutige Parser sie noch nicht
# auswertet. Ein besserer Parser holt spaeter mehr daraus — das Rohmaterial ist wertvoller
# als der aktuelle Index. Platz ist da (1,6 TB frei bei 96 GB Bestand).
#
# Wer die grossen Pakete AUSWERTEN will, braucht `process_zip` mit stroemendem Entpacken
# statt „alles in den Speicher". Bis dahin waechst hier ein Vorrat, kein Ergebnis.
if [ "${GOVISOR_NEUE_QUELLEN:-1}" = "1" ]; then

  # Healy-Hudson-Bekanntmachungen: EINE oeffentliche Liste fuer alle sechzehn Laender
  # (`Dashboard_off?BL=<amtlicher Schluessel>`). 1.300 offene Vorgaenge gemessen, davon
  # kannten wir 508 ueber die Unterlagen-Links. ⚠ Die Liste WUERFELT je Abruf ~25 Zeilen —
  # deshalb Runden mit Dublettenfilter, und der Bestand fuellt sich ueber die Tage.
  step "Healy-Hudson-Bekanntmachungen (alle 16 Laender, rotierende Liste)"
  mit_grenze "$GRENZE_ABRUF" $PY -m govisor.healyhudson --alle --runden 12 \
    || echo "  ⚠ Healy-Hudson-Import unvollstaendig."
  # Bronze → Silber. Ohne diesen Schritt sammelt healyhudson nur JSONL und es entsteht
  # KEIN einziger Lead — genau der Zustand, in dem die Quelle bis zum 2026-08-14 war.
  # Eigener Aufruf statt Teil des Imports: der Abruf kann unvollstaendig sein (die Liste
  # wuerfelt je Seitenaufruf), das Silber soll trotzdem aus allem gebaut werden, was da ist.
  mit_grenze "$GRENZE_ABRUF" $PY -m govisor.healyhudson --silber \
    || echo "  ⚠ Healy-Hudson-Silber nicht gebaut — die Vorgaenge bleiben in Bronze liegen."


# ══ ERNTE VOR ABRUF ══════════════════════════════════════════════════════════════════
# Dieser Block stand bis 2026-08-17 HINTER den Unterlagen-Abrufern. Am 2026-08-16 kostete
# ihn das den halben Lauf: nach 623 min riss die 8-h-Grenze, 18 von 33 Schritten waren
# erledigt, und ausgefallen war ausgerechnet alles, was aus Daten ein Produkt macht —
# Gold-Rebuild, Signale, Frontend-Export, Supabase, Ertragsbericht. 93 % der Laufzeit
# waren in Beschaffung gegangen.
#
# Gemessen ueber fuenf Laeufe: die Beschaffung kostet im schlimmsten Fall 1.622 min und
# ist nach oben offen, die Wertschoepfung 45 min und ist gedeckelt. Wer das Gedeckelte
# hinter das Offene stellt, verliert im Zweifel immer dasselbe.
#
# Die Kette Firewall -> Kategorie -> Gold wandert deshalb GESCHLOSSEN nach vorn. Einzeln
# ginge es nicht: die Kategorie-Ableitung liest `notice_duplicates` aus der Firewall, und
# der Gold-Lead-Bau liest `lead_kategorie.parquet` aus der Kategorie-Ableitung.
#
# PREIS, den das hat: Unterlagen, die dieser Lauf holt, werden erst im naechsten
# ausgewertet — die Auswertung sitzt jetzt hinter dem Abruf. Dafuer steht das Produkt
# jeden Morgen frisch da, auch wenn die Beschaffung ins Zeitlimit laeuft.
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
# ERLEDIGT (2026-08-14): hier stand, dass AT 2019-2023 und DE 2023-2025 in den
# Marktpuls-Jahresschichten unbereinigt bleiben und der echte Fix ein Umbau auf DuckDB-SQL
# waere. Beides ist ueberholt. Der SQL-Umbau wurde gebaut und war gemessen zwei- bis
# dreimal LANGSAMER (s. Docstring in govisor/dedupe.py); geholfen haben Seed-Deckel und
# Zeitscheiben. Seither laeuft die volle Historie, die Luecke ist zu.
#
# Gemessen 2026-08-14 ueber die volle Historie:
#   AT  128.216 Paare ·  64.889 mit Kaeufer-Beleg ·  65.537 Anreicherungswerte
#   CH   18.465 Paare ·  14.510 mit Kaeufer-Beleg ·   7.579 Werte
#   DE  115.871 Paare ·  25.990 mit Kaeufer-Beleg ·   1.469 Werte
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
# ROLLENDES FENSTER statt voller Historie — der teuerste Schritt des Laufs (gemessen
# 188 min am 2026-08-16, mehr als jeder andere).
#
# Warum das verlustfrei geht: ein Dubletten-Paar muss binnen 90 Tagen liegen. Ein Lauf,
# der nur die letzten 190 Tage laedt, kann hoechstens Paare verlieren, deren BEIDE Seiten
# aelter sind — und die stehen bereits in `notice_duplicates.parquet`, weil ein frueherer
# Lauf sie gefunden hat. `--fenster-tage` schaltet deshalb auch das VEREINIGEN ein: das
# Ergebnis kommt zum Bestand dazu, es ersetzt ihn nicht.
#
# Gemessen (Paarung, alle Arten, ab 2004):
#     CH   120.641 Saetze  7,5 s  →  18.228 im Fenster  0,9 s   (8x)
#     AT   414.172 Saetze 39,4 s  →  26.882 im Fenster  2,0 s  (20x)
#     DE 2.221.669 Saetze  s. u.  → 163.049 im Fenster 41,5 s
# In allen drei Faellen fand das Fenster KEIN Paar, das der Vollauf nicht auch fand.
#
# SONNTAGS trotzdem voll. Nicht aus Misstrauen gegen die Rechnung, sondern gegen die
# Annahmen darin: ruecklaufende Korrekturen an alten Saetzen, ein geaenderter Schwellwert,
# eine neue Quelle mit Altbestand. Der Wochenlauf faengt das ein, und er faellt auf einen
# Tag, an dem kein Mensch auf frische Zahlen wartet.
if [ "$(date +%u)" = "7" ] || [ -n "${GOVISOR_DEDUPE_VOLL:-}" ]; then
  _DEDUPE_MODUS="volle Historie ab 2004 (Sonntag)"
  _DEDUPE_ARGS=""
else
  _DEDUPE_MODUS="rollendes Fenster 190 Tage (+ Saetze ohne Datum)"
  _DEDUPE_ARGS="--fenster-tage 190"
fi
step "Dubletten-Firewall + Anreicherung (DE/AT/CH/LU)"
echo "  Modus: $_DEDUPE_MODUS"
for L in DE AT CH LU; do
  # shellcheck disable=SC2086  # _DEDUPE_ARGS ist bewusst wortgetrennt
  $PY -m govisor.dedupe --country "$L" --ab-jahr 2004 --alle-arten --anreichern $_DEDUPE_ARGS \
    || echo "  ⚠ Dublettencheck $L fehlgeschlagen — Anreicherung bleibt auf altem Stand."
done

# KATEGORIE-WASSERFALL. Muss ZWISCHEN Firewall und Gold laufen, und das ist keine
# Geschmacksfrage: er liest `notice_duplicates` (kommt aus der Firewall) und schreibt
# `lead_kategorie.parquet`, das der Gold-Lead-Bau per LEFT JOIN liest. Davor gaebe es die
# Zwillinge noch nicht, danach kaeme das Ergebnis einen Lauf zu spaet.
#
# GEFEHLT bis 2026-08-14: der Wasserfall war gebaut, aber nie verdrahtet. `lead_kategorie`
# stand deshalb auf dem Stand eines einzelnen Handlaufs — alle spaeter dazugekommenen
# Quellen (healyhudson: 676 Leads) blieben „Ohne Kategorie", ohne dass etwas abbrach.
step "Kategorie-Ableitung fuer Ausschreibungen ohne CPV"
$PY -m govisor.kategorie --country DE --schreiben \
  || echo "  ⚠ Kategorie-Ableitung fehlgeschlagen — die Leads ohne CPV bleiben 'Ohne Kategorie'."

step "AT/CH-Gold (volle Pipeline, 26 Schritte je Land)"
# ⚠ LU laeuft HIER mit, nicht ueber `cli gold`. Der CLI-Weg zieht build_hr_index() mit —
# den deutschen Handelsregister-Index mit 5,5 Mio. Firmen — und der ist fuer Luxemburg weder
# zustaendig noch bezahlbar. Genau deshalb gehen AT und CH schon diesen Weg.
$PY scripts/build_dach_gold.py --laender AT,CH,LU --as-of "$TODAY" \
  && echo "  AT/CH-Gold ok." \
  || echo "  ⚠ AT/CH-Gold unvollstaendig — beide Laender bleiben auf dem letzten Stand."

# 2) Gold neu mit heutigem Stichtag — refresht Leads, Fristen, months_to_expiry. FATAL bei Fehler.
# ⚠ KEIN DATUM IM SCHRITTNAMEN. Der Name ist der Schluessel, unter dem `⏱ <Name> — <n>s`
# im Protokoll steht — und damit die einzige Handhabe, die Dauer eines Schritts ueber
# mehrere Naechte zu verfolgen. Mit dem Stichtag darin zerfiel ausgerechnet der GROESSTE
# Schritt in lauter Einzelnamen: 13 von 61 verschiedenen Schrittnamen aus 14 Naechten
# waren derselbe „Gold-Rebuild". Seine Entwicklung war damit unsichtbar — und genau die
# will Schritt 4 des Effizienzplans messen. Der Stichtag steht jetzt in der AUSGABE.
step "Gold-Rebuild"
echo "  Stichtag: $TODAY"
if ! $PY -m govisor.cli gold --country DE --as-of "$TODAY"; then
  echo "  ✖ Gold-Rebuild fehlgeschlagen — KEIN Supabase-Push (kein Halb-Stand nach oben)."
  echo "Abbruch nach ${SECONDS}s."
  exit 2
fi
echo "  Gold ok."

# ⚠ ZWEITER SCHRITT, DER NIE GERUFEN WURDE — und dieser hier ist noch nie gelaufen.
#
# `govisor/retender_link.py` verknuepft chronisch erfolglose Bedarfe („diese Vergabestelle
# sucht zum vierten Mal") mit den offenen Leads. Sven hat genau danach am 2026-08-16
# gefragt; das Modul wurde daraufhin gebaut — und nie verdrahtet. `lead_retender.parquet`
# gab es in KEINEM Land: nicht veraltet, sondern nie entstanden. Sonde 1 der
# Verdrahtungspruefung konnte es deshalb nicht melden, sie misst das Alter VORHANDENER
# Dateien.
#
# Erster Lauf ueberhaupt (2026-08-25, DE): 2.464 chronische Bedarfe, 14.470 offene Leads,
# 11 Verknuepfungen. 0,2 s.
#
# ⚠ ES LIEST NOCH NIEMAND. Der Erzeuger laeuft ab hier, der Verbraucher fehlt — die Datei
# kommt in keinem Frontend-Export vor. Das ist eine offene Produktfrage, kein Defekt, und
# sie steht ausdruecklich hier, statt still zu bleiben.
#
# NACH dem Gold-Rebuild: gelesen werden `retender_signal` und `lead_export`, beides Gold.
step "Zweitversuch-Kennzeichnung (chronische Bedarfe → offene Leads)"
$PY -m govisor.retender_link --country DE \
  || echo "  ⚠ lead_retender nicht gebaut — die Zweitversuch-Marke bleibt auf altem Stand."

# ══ AB HIER: BESCHAFFUNG ═════════════════════════════════════════════════════════════
# Alles zwischen dieser Marke und der Auswertung weiter unten ist nach oben offen und
# teilt sich EINEN Topf: was nach Abzug von ERNTE_RESERVE uebrig bleibt. Die Marke statt
# elf einzelner Wachen, damit ein neuer Abrufer nicht vergessen werden kann — er liegt
# zwischen den Marken und ist damit automatisch gedeckelt.
# ⛔ BESCHAFFUNG IM TAGESLAUF: STANDARDMAESSIG AUS (seit 2026-08-18).
#
# Gemessen ueber zehn protokollierte Laeufe: 4 von 10 liefen durch, 6 endeten mit Code 75 —
# das ist KEIN Absturz, sondern die selbstgesetzte Acht-Stunden-Grenze. Und wohin die Zeit
# geht, ist eindeutig (Durchschnitt ueber die Laeufe vom 14. bis 18.08.):
#
#   Healy-Hudson-Unterlagen        136 min   (Spitze 719 min)
#   Anforderungs-Signale            48 min
#   subreport-Dateilisten           39 min
#   vergabeportal.at                35 min
#   NetServer                       34 min
#   Staatsanzeiger                  31 min
#   Dubletten-Firewall              29 min
#
# Rund fuenf der acht Stunden gehen fuer das HOLEN von Unterlagen drauf — also fuer die
# Arbeit, fuer die es seit dem 2026-08-18 einen eigenen Dauerarbeiter gibt
# (`scripts/dokumente_arbeiter.sh`, laeuft rund um die Uhr und kennt dieselben zwoelf
# Abrufer ueber `scripts/rueckstau.py`). Beides parallel zu betreiben heisst: dieselben
# Portale doppelt behelligen und den Tageslauf an seiner eigenen Grenze sterben lassen.
#
# Der Tageslauf macht ab jetzt, was nur er kann: einlesen, entdoppeln, Gold bauen,
# exportieren, veroeffentlichen, messen. Das Holen laeuft nebenher und ohne Uhr.
#
# Wieder einschalten (etwa fuer einen Nachhol-Lauf von Hand):
#     GOVISOR_TAGESLAUF_HOLT_UNTERLAGEN=1 scripts/daily_leads.sh
# ⚠ ZWEI SCHALTER, DIE MAN LEICHT VERWECHSELT — und ich habe es getan.
# `_ABRUF_PHASE` markiert die Beschaffungsphase; daran haengt die BUDGETWACHE. Auf 0
# gesetzt liefen die Abrufe nicht etwa nicht, sondern OHNE Deckel. Ob ueberhaupt geholt
# wird, entscheidet deshalb ein eigener Schalter.
_ABRUF_PHASE=1
_ABRUF_AUS=1
[ "${GOVISOR_TAGESLAUF_HOLT_UNTERLAGEN:-0}" = "1" ] && _ABRUF_AUS=0
if [ "$_ABRUF_AUS" = "1" ]; then
  echo ""
  echo "⏭ Unterlagen-Abruf uebersprungen — das macht der Dauerarbeiter"
  echo "   (scripts/dokumente_arbeiter.sh, launchctl list | grep govisor.dokumente)."
  echo "   Einschalten: GOVISOR_TAGESLAUF_HOLT_UNTERLAGEN=1"
fi

  # NetServer-UNTERLAGEN. Die zweitgroesste Dokumentenluecke: 1.055 offene Leads auf
  # Portalen, deren Bekanntmachungen oben schon hereinkommen. Der Weg fuehrt ueber
  # `&thContext=publications` und ein Modal — die rohe `documents_url` zeigt auf die
  # Bekanntmachung und traegt keine einzige Datei.
  # ⚠ Diese Pakete sind gross (gemessen 10–65 MB, ein Ausreisser 335 MB); der Lauf ist
  # deshalb auf 2 GB gedeckelt und arbeitet den Rest ueber die Tage ab.
  step "NetServer-Unterlagen (DE, anonym, budgetiert + idempotent)"
  mit_grenze "$GRENZE_ABRUF" $PY -m govisor.docfetch_netserver --limit 60 \
    || echo "  ⚠ NetServer-Unterlagen unvollstaendig."

  # e-VERGABE DES BUNDES (evergabe-online.de). Die GROESSTE Einzelluecke: 1.026 offene
  # Leads, bis 2026-08-15 ueberhaupt kein Zugang (die Plattform stand tagelang in Wartung).
  # Der Download ist frei und ausdruecklich angeboten — „uneingeschraenkter und
  # vollstaendiger direkter Zugang gebuehrenfrei", ohne Anmeldung.
  # GEMESSEN 2026-08-15 (Trockenlauf): 30 von 30 bzw. 8 von 8 mit ZIP-Knopf, 18–144 Dateien
  # je Vergabe. Erwartete Wirkung: DE-Unterlagenabdeckung 68 % → ~77 %.
  # ⚠ `/xvergabe/services/` (XVergabe-Standard) und `/ws-suche/` existieren laut robots.txt,
  # sind dort aber fuer automatische Zugriffe gesperrt — wir sprechen sie NICHT an. Die
  # Anfrage ans Beschaffungsamt liegt in `api-anfragen.md`.
  step "e-Vergabe des Bundes — Unterlagen (DE, anonym, budgetiert + idempotent)"
  mit_grenze "$GRENZE_ABRUF" $PY -m govisor.docfetch_evergabe_online --limit 60 \
    || echo "  ⚠ e-Vergabe-Unterlagen unvollstaendig."

  # DEUTSCHES AUSSCHREIBUNGSBLATT. 172 offene Leads, ZIP anonym (3 von 3 gemessen).
  # ⚠ Die Bezahlschranke der Seite gilt der RECHERCHE, nicht den Unterlagen — der
  # Tarif-Knopf ist im DOM unsichtbar, der Unterlagen-Knopf sichtbar.
  step "Ausschreibungsblatt-Unterlagen (DE, anonym, budgetiert + idempotent)"
  mit_grenze "$GRENZE_ABRUF" $PY -m govisor.docfetch_ausschreibungsblatt --limit 40 \
    || echo "  ⚠ Ausschreibungsblatt-Unterlagen unvollstaendig."

  # bi-medien.de. 110 offene Leads. Sammel-ZIP je Vergabe ueber einen eigenen Dienst
  # (publictender.bi-medien.de/api/Part/<uuid>), anonym http 200 (2 von 2 gemessen).
  # ⚠ Die Links stehen zugeklappt im DOM — auslesen, nicht klicken (Klick = Timeout).
  step "bi-medien-Unterlagen (DE, anonym, budgetiert + idempotent)"
  mit_grenze "$GRENZE_ABRUF" $PY -m govisor.docfetch_bimedien --limit 40 \
    || echo "  ⚠ bi-medien-Unterlagen unvollstaendig."

  # Healy-Hudson-UNTERLAGEN. 508 offene Leads. ⚠ Pro Instanz verschieden: Bahn und Hamburg
  # geben heraus, `bieterzugang.deutsche-evergabe.de` leitet auf ein Dashboard ohne Dateien.
  # Das Manifest schluesselt nach Host auf, damit das sichtbar bleibt.
  # GEMESSEN 2026-08-14 (40 Kandidaten, Trockenlauf): 0 geladen, 8 waeren geladen worden.
  # 30 der 40 liegen auf bieterzugang.deutsche-evergabe.de, und das leitet anonyme Abrufe
  # aufs zentrale Dashboard um (`kein_downloadbereich`). Ertrag also ~20 % — `--limit 60`
  # heisst ~12 echte Vorgaenge je Lauf, nicht 60. Wer die Ausbeute heben will, muss NICHT
  # den Fetcher anfassen, sondern die Warteschlange: deutsche-evergabe braucht Anmeldung.
  step "Healy-Hudson-Unterlagen (DE, anonym, idempotent)"
  mit_grenze "$GRENZE_ABRUF" $PY -m govisor.docfetch_healyhudson --limit 60 \
    || echo "  ⚠ Healy-Hudson-Unterlagen unvollstaendig."

  # aumass-UNTERLAGEN. Der sauberste Zugang von allen: ein Link, der woertlich „Ohne
  # Registrierung herunterladen." heisst, auf einen parametrisierten Endpunkt. 288 Leads,
  # 269 verschiedene Vergaben (Geschwister teilen sich den Abruf).
  # ⚠ Die Pakete sind gross (13–188 MB gemessen); Lauf auf 2 GB gedeckelt.
  step "aumass-Unterlagen (DE, anonym, budgetiert + idempotent)"
  mit_grenze "$GRENZE_ABRUF" $PY -m govisor.docfetch_aumass --limit 40 \
    || echo "  ⚠ aumass-Unterlagen unvollstaendig."

  # staatsanzeiger-UNTERLAGEN. 211 Leads, davon 153 ueber die funktionierende URL-Form.
  # Dreistufig: Weiche → „Anonym als Zip" (NAVIGATION, kein Download) → ZIP-Link auf
  # einem anderen Host. ⚠ Die restlichen 56 tragen ein Frameset, dessen Inhalts-Frame
  # ohne Sitzung leer bleibt — eigener Status `frameset`, kein Fehler.
  step "Staatsanzeiger-Unterlagen (DE, anonym, budgetiert + idempotent)"
  mit_grenze "$GRENZE_ABRUF" $PY -m govisor.docfetch_staatsanzeiger --limit 40 \
    || echo "  ⚠ Staatsanzeiger-Unterlagen unvollstaendig."

  # ÖSTERREICH — der erste AT-Schritt ueberhaupt. `vergabeportal.at` + `wien.gv.at` (dieselbe
  # Software) tragen 334 Leads = 91 % aller erreichbaren AT-Leads.
  # ⚠ NUR DIE DATEILISTE, keine Dateien: der anonyme Download ist durch hCaptcha geschuetzt
  # (nachgewiesen ueber den Netzwerkverkehr). Ein CAPTCHA wird nicht geloest und nicht
  # umgangen. Die LISTE ist ohne CAPTCHA sichtbar und traegt Name, Groesse, Erstell- UND
  # Aenderungsdatum, „Inaktiv"-Kennzeichen und SHA — daraus kommt „gibt es ein
  # Leistungsverzeichnis, welche Nachweise, wurde nachgebessert".
  step "vergabeportal.at-Dateilisten (AT, ohne CAPTCHA, idempotent)"
  mit_grenze "$GRENZE_ABRUF" $PY -m govisor.vergabeportal_at --limit 60 \
    || echo "  ⚠ AT-Dateilisten unvollstaendig."

  # ⏳ LUXEMBURG — der einzige Abrufer gegen eine VERGAENGLICHE Quelle.
  #
  # ⚠ WARUM ER HIER STEHT UND NICHT IM RUECKSTAU-ARBEITER. Nach Fristende sind die
  # luxemburgischen Unterlagen WEG (belegt: 30 von 30 aelteren Vergaben melden „Aucune
  # piece jointe", docs/sondierung/haltbarkeit.md §14). Es gibt dort also keinen
  # Rueckstau, den man abarbeiten koennte — nur einen Zulauf, den man verpasst oder
  # nicht. Verlustrate rund 135 Vergaben im Monat.
  #
  # ⚠ Seine Warteschlange kommt aus der TED-SUCHSCHNITTSTELLE, nicht aus data/gold: fuer
  # LU gibt es kein Gold, und die Monatspakete liegen bis zu vier Wochen zurueck —
  # laenger als manche luxemburgische Frist. Sortiert nach Frist aufsteigend.
  #
  # ⚠ KEINE Groessenschwelle. Median 6,9 MB, aber gemessen bis 614 MB je Vergabe; eine
  # Schwelle waere hier ein dauerhafter Verzicht auf die Bauvorhaben mit Planunterlagen.
  # Das Lauf-Budget (GOVISOR_LU_BUDGET_MB, Vorgabe 8000) bremst statt auszuschliessen.
  step "Luxemburg-Unterlagen (vergaenglich — jetzt oder nie)"
  mit_grenze "$GRENZE_ABRUF" $PY -m govisor.docfetch_lu --limit 40 \
    || echo "  ⚠ LU-Unterlagen unvollstaendig — ⏳ diese Vergaben sind moeglicherweise verloren."

else
  echo ""
  echo "▶ Neue Quellen (healyhudson + die VIER Unterlagen-Fetcher) ABGESCHALTET."
  echo "  Wieder an mit: GOVISOR_NEUE_QUELLEN=1 (Vorgabe ist AN)"
fi


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
fi   # Ende Phase „leads"

if phase_an dokumente; then
step "Vergabeunterlagen holen (DE/cosinex, höflich + idempotent)"
mit_grenze "$GRENZE_ABRUF" $PY -m govisor.cli fetch-docs --country DE || echo "  ⚠ Fetch unvollständig — Auswertung läuft über den vorhandenen Bestand."
# ⚠ DIESER SCHRITT FEHLTE (gemessen 2026-08-13: 2.114 Vorgänge heruntergeladen, 241 mit Text).
#   `signals-docs` liest doc_text.parquet — das erzeugt AUSSCHLIESSLICH `index-docs`. Ohne
#   diese Zeile lief der Tageslauf formal durch: Fetch grün, Signale grün, aber die Signale
#   entstanden aus dem Textbestand des letzten Handlaufs. Genau die Falle, die wir beim
#   Fetch schon einmal hatten — Herunterladen allein bringt nichts, Auswerten ohne
#   Aufbereiten aber genauso wenig.
# evergabe.de: ECHTE Vergabeunterlagen, anonym (§ 41 VgV — die Plattform beschriftet den Weg
# selbst mit „Der Auftraggeber erfaehrt nicht, dass Sie die Vergabeunterlagen herunterladen").
# 846 offene Leads, und die Ausbeute ist inhaltlich: aus einer geholten .X83 liest unser
# GAEB-Parser 625 LV-Positionen mit Menge und Einheit. Die ZIPs landen dort, wo `index-docs`
# unten sucht — deshalb steht dieser Schritt VOR dem Index.
#
# Gedeckelt, weil eine CloudWAF nach ~10 Vorgaengen drosselt. Die Sperre ist fluechtig
# (gemessen 6 min), der Connector pausiert und macht weiter; 40 Vorgaenge dauern damit rund
# eine Stunde. Idempotent — bereits geholte Vergaben fallen raus, der Rueckstand arbeitet
# sich ueber die Tage ab.
step "evergabe.de-Unterlagen (DE, anonym, gedeckelt + idempotent)"
mit_grenze "$GRENZE_ABRUF" $PY -m govisor.docfetch_evergabe --limit 40 || echo "  ⚠ evergabe.de-Abruf unvollständig."

# subreport ELViS: DATEILISTEN, keine Dateien. Der Download reagiert dort ohne Anmeldung
# nicht (gemessen ueber drei Vergaben und alle Knopfpositionen; der eine Knopf, der liefert,
# gibt die Bekanntmachung — die haben wir ueber TED). Die LISTE ist oeffentlich, und aus den
# Dateinamen zieht `doctypes` genug: gemessen an 60 Vergaben 90 % mit Liste, 57 % mit
# Leistungsverzeichnis, 77 % mit Eignungsunterlage. Damit ist beantwortbar, ob ein LV
# existiert und welche Nachweise verlangt werden, ohne eine einzige Datei zu besitzen.
# Gedeckelt, weil jede Vergabe ~14 s braucht (clientseitiges Rendern); idempotent, bekannte
# Vorgaenge fallen raus — der Rueckstand arbeitet sich ueber die Tage ab.
step "subreport-Dateilisten (DE, gedeckelt + idempotent)"
mit_grenze "$GRENZE_LANG" $PY -m govisor.subreport --limit 120 || echo "  ⚠ subreport-Listen unvollständig."

# ══ AB HIER: AUSWERTUNG ══════════════════════════════════════════════════════════════
# Fuer diesen Rest ist ERNTE_RESERVE da. Kein Budget-Waechter mehr: was hier laeuft, ist
# gedeckelt (gemessen ~45 min) und macht aus den Daten das Produkt.
_ABRUF_PHASE=0

step "Unterlagen entpacken → Volltext-Index"
# ⚠ ZWEI SCHUTZE, beide am 2026-08-14 durch Schaden gelernt:
#
# (1) ZEITLIMIT (45 min). Der Schritt lief 106 Minuten an einem Dokument fest.
# (2) EIGENES LOCK. Waehrend des Laufs startete jemand `cli index-docs` direkt aus einer
#     zweiten Sitzung — ZWEI Prozesse schrieben gleichzeitig `doc_text.parquet`. Das
#     Lauf-Lock schuetzt Laeufe gegeneinander, nicht gegen einen direkten Aufruf. Wer auf
#     eine gemeinsame Datei schreibt, braucht sein eigenes.
# ⚠ DER INDEXER LIEF NUR FUER DE — auch nachdem der LU-Abrufer am 2026-09-03 in den
# Tageslauf kam. Das ist die haesslichste Form der Luecke: das Sammeln war verdrahtet, das
# Auswerten nicht. Die ZIPs lagen auf der Platte, `doc_text` kannte sie nicht, und nichts
# war rot — ein Land sammelt dann Unterlagen, die niemand je liest.
# ⚠ LU laeuft INNERHALB desselben Locks: `doc_text.parquet` liegt je Land getrennt, aber
# der Indexer ist derselbe Prozess, und zwei davon gleichzeitig war schon einmal der Fehler
# (s. Absatz 2 oben). Nacheinander, nicht parallel.
_IXLAENDER="DE LU"
_index_alle() {
  for _L in $_IXLAENDER; do
    mit_limit 2700 $PY -m govisor.cli index-docs --country "$_L" \
      || echo "  ⚠ Index $_L unvollständig — Auswertung läuft über den vorhandenen Textbestand."
  done
}
_IXLOCK="$ROOT/data/.index_docs.lock"
if mkdir "$_IXLOCK" 2>/dev/null; then
  echo $$ > "$_IXLOCK/pid"
  _index_alle
  rm -rf "$_IXLOCK"
else
  _alt="$(cat "$_IXLOCK/pid" 2>/dev/null | tr -d '[:space:]')"
  if [ -n "$_alt" ] && kill -0 "$_alt" 2>/dev/null; then
    echo "  ⚠ Index laeuft bereits (PID $_alt) — uebersprungen, um doppeltes Schreiben zu vermeiden."
  else
    echo "  ⚠ Verwaistes Index-Lock — uebernommen."
    rm -rf "$_IXLOCK" && mkdir "$_IXLOCK" && echo $$ > "$_IXLOCK/pid"
    _index_alle
    rm -rf "$_IXLOCK"
  fi
fi
# ⚠ DIESER SCHRITT HAT GEFEHLT — gebaut am 2026-08-22, gerufen von niemandem.
#
# `govisor/dokdubletten.py` bildet Paare „dieselbe Datei, ein Master", damit ein
# Standardformular EINMAL ausgewertet wird statt in jeder Vergabe erneut. Der Code stand
# fertig da, die CLI kannte ihn nicht, der Tageslauf auch nicht. `document_duplicates.parquet`
# stammte deshalb aus einem Handlauf vom 22.08. um 19:18 und lag drei Tage still, waehrend
# `analyze_docs.py` es jede Runde einlas — im Log Tag fuer Tag dieselben „449 ueber Master".
# Nachgemessen am 25.08.: es waeren **3.687** Paare gewesen, also rund 3.200 Dokumente, die
# seither erneut ans Modell gingen, obwohl ihr Ergebnis schon vorlag.
#
# Gefunden hat es Sonde 1 der Verdrahtungspruefung (sie laeuft unten am Ende dieses Laufs)
# — nicht ein Blick in den Code. Genau dafuer gibt es sie.
#
# ⚠ REIHENFOLGE: NACH `index-docs`. Die Paare entstehen aus `doc_text.parquet`; wer sie vor
# dem Index bildet, vergleicht den Bestand von gestern.
#
# NUR DE, und das ist belegt, nicht vergessen: AT und CH haben 0 % Dokumentabdeckung
# (s. `docs/laender/03-input-dokumente.md`). Das Modul sagt es selbst, wenn kein Textindex
# da ist, statt still nichts zu tun — ein Land, das Unterlagen bekommt, kommt hier dazu.
step "Dokument-Dubletten (gleiche Datei → ein Master)"
$PY -m govisor.dokdubletten --country DE \
  || echo "  ⚠ Dokument-Dubletten nicht neu gebildet — die Analyse zahlt Wiederholungen erneut."

step "Unterlagen auswerten → Anforderungs-Signale"
# ⚠ `signals-docs` nimmt EIN Land (Vorgabe DE) und wurde ohne Angabe gerufen — LU waere
# also nie signalisiert worden, auch mit indiziertem Text. Dieselbe Schleife wie beim
# Indexer; `_IXLAENDER` ist bewusst dieselbe Liste, damit die beiden nicht auseinanderlaufen.
_signale_alle() {
  _ok=1
  for _L in $_IXLAENDER; do
    $PY -m govisor.cli signals-docs --country "$_L" \
      || { _ok=0; echo "  ⚠ Signale $_L fehlgeschlagen."; }
  done
  [ "$_ok" = 1 ]
}
if _signale_alle; then
  $PY scripts/export_doc_signals.py || echo "  ⚠ doc-signals.json nicht geschrieben."
  # Aufwand gegen Zeitfenster (Kennzahl 1). Braucht `doc_analysis` in Gold UND das
  # Veroeffentlichungsdatum aus Silber — laeuft deshalb NACH der Gold-Kette, nicht davor.
  # ⚠ Fehlt die Datei, verschwindet die Zeile im Lead-Detail lautlos. Deshalb laut melden.
  $PY scripts/export_fenster.py || echo "  ⚠ fenster.json nicht geschrieben — Kennzahl 1 fehlt im Detail."
  # Anforderungsprofil (Kennzahl 2). Braucht `doc_checklist` in Gold.
  $PY scripts/export_anforderungsprofil.py || echo "  ⚠ anforderungsprofil.json nicht geschrieben — Kennzahl 2 fehlt im Detail."
  # Fingerabdruck der Vergabestelle (Kennzahl 3).
  $PY scripts/export_stellenprofil.py || echo "  ⚠ stellenprofil.json nicht geschrieben — Kennzahl 3 fehlt im Detail."
  # Umfang der Angebotsarbeit (Kennzahlen 4 und 5): groesstes Formular und groesstes
  # GAEB-Leistungsverzeichnis. Liest `doc_checklist` und fuer den Gewerksvergleich `lead_export`.
  $PY scripts/export_umfang.py || echo "  ⚠ umfang.json nicht geschrieben — Kennzahlen 4 und 5 fehlen im Detail."
  # Bezifferte Schwellen (Kennzahl 6). Winzige Datei: nur Gruppenwerte und die Regeln, mit
  # denen der Renderer denselben Gruppenschluessel bildet.
  $PY scripts/export_schwellen.py || echo "  ⚠ schwellen.json nicht geschrieben — Kennzahl 6 fehlt im Detail."
  # Standardtext-Anteil (Kennzahl 8). Liest den VOLLTEXT (4,2 Mrd. Zeichen in DE) und braucht
  # rund 90 Sekunden — der einzige Schritt hier, der nicht in Sekunden durchlaeuft.
  $PY scripts/export_standardtext.py || echo "  ⚠ standardtext.json nicht geschrieben — Kennzahl 8 fehlt im Detail."
  # Fristwiderspruch (Kennzahl 9). Vergleicht die belegte Angebotsfrist aus den Unterlagen mit
  # der aus der Bekanntmachung. ⚠ Ein Fehlalarm kostet hier eine Abgabe, s. Filter im Skript.
  $PY scripts/export_fristwiderspruch.py || echo "  ⚠ fristwiderspruch.json nicht geschrieben — Kennzahl 9 fehlt im Detail."
  # ⚠ DER ERZEUGER FEHLTE, DER VERBRAUCHER LIEF. Die Zeile darunter sagt seit jeher
  # "braucht doc_qa_stand" — gebaut hat es nachts NIEMAND. Zuletzt lief
  # build_doc_qa_stand.py am 2026-09-01 von Hand; die Frische-Sonde meldete die Tabelle
  # am 2026-09-04 mit 2,2 Tagen Rueckstand. Falle A1: gebaut, aber nicht verdrahtet.
  # Laeuft ueber dieselbe Liste wie der Indexer — die Tabelle liest doc_text.
  for _L in $_IXLAENDER; do
    $PY scripts/build_doc_qa_stand.py --land "$_L" \
      || echo "  ⚠ doc_qa_stand $_L nicht gebaut — Bieterfragen bleiben auf altem Stand."
  done
  # Bieterfragen und Antworten. Liest den Volltext der Q&A-Dokumente; braucht `doc_qa_stand`.
  $PY scripts/export_bieterfragen.py || echo "  ⚠ bieterfragen.json nicht geschrieben — Bieterfragen fehlen im Detail."
  # Aenderungen an den Unterlagen: vergleicht die Fassungen im Dokumentpfad.
  $PY scripts/export_unterlagenstand.py || echo "  ⚠ unterlagenstand.json nicht geschrieben — Fassungsänderungen fehlen."
else
  echo "  ⚠ Signal-Extraktion übersprungen."
fi

# ⚠ DIESER SCHRITT FEHLTE — und zwar lautlos, seit es ihn gibt.
#
# `index-docs` schreibt den ausgelesenen Volltext nach data/docs/DE/doc_text.parquet.
# Von dort holt ihn `export_doc_text.py` ins Frontend. Nur stand der Aufruf nie im
# Tageslauf: exportiert wurden allein die SIGNALE. Gemessen am 2026-08-18 lagen
# 4.499 Vorgaenge mit Text bereit (3.986 davon zu offenen Leads) und im Frontend
# standen 14 — das Ergebnis eines Handlaufs von irgendwann.
#
# Aufgefallen ist es nur, weil jemand die Abdeckung nachgezaehlt hat: nichts war rot,
# kein Schritt schlug fehl, die Datei existierte. Sie war bloss uralt. Genau dagegen
# hilft es, den Export NEBEN den Erzeuger zu stellen statt ihn einmal von Hand zu fahren.
step "Unterlagen-Volltext exportieren (doc-text.json)"
$PY scripts/export_doc_text.py || echo "  ⚠ doc-text.json nicht geschrieben — Lead-Detail zeigt weiter den alten Textstand."
# Dasselbe fuer die LLM-Auswertungen: `doc-analysis.json` ist der Arbeitsstand des
# Analyse-Arbeiters (252 MB) und bleibt lokal; das Frontend liest eine Datei je Vorgang.
# Ohne diesen Aufruf zeigt das Lead-Detail die Auswertungen vom letzten Export.
$PY scripts/export_doc_analysis.py || echo "  ⚠ doc-analysis nicht zerlegt — Lead-Detail zeigt weiter den alten Auswertungsstand."
# Und dieselbe Auswertung in die GOLD-EBENE, als abfragbare Tabellen.
#
# ⚠ WARUM DAS NOETIG IST: bis zum 2026-09-01 lag die LLM-Auswertung ausschliesslich als
# 7.188 lose JSON in `web/data/doc-analysis/` — also im Auslieferungsverzeichnis. 633.078
# Einzelaussagen aus 165 Mio Token, das einzige Artefakt mit echten Kosten, und weder
# abfragbar noch verbindbar noch dauerhaft: ein Neubau von `web/data` haette es gekostet.
# Direkt hinter den Erzeuger gestellt, aus demselben Grund wie der Export darueber.
$PY scripts/build_doc_analysis.py || echo "  ⚠ doc_analysis/doc_checklist nicht gebaut — die Auswertung bleibt auf dem alten Tabellenstand."

# Vorgaenge: Ausschreibung + Dokumente + Zuschlag unter EINER Kennung. Laeuft NACH
# `build_doc_analysis`, weil es `doc_checklist` liest, um die Unterlagen anzuhaengen.
# Alle Laender in einem Lauf, rund 25 Sekunden.
$PY scripts/build_vorgaenge.py || echo "  ⚠ vorgaenge/vorgang_notice nicht gebaut — die Vorgangsakte bleibt auf dem alten Stand."
# Verfahrenskalender (#16) — MUSS nach `export_doc_analysis` laufen: er liest die
# Splitterdateien, die dort entstehen. Baut je offenem Lead die Terminliste aus
# Bekanntmachung (Angebotsfrist) und Unterlagen (Bindefrist, Bieterfragen, Ortstermin …).
# Nur klassifizierte Termine; was sich keiner Art zuordnen laesst, wird gezaehlt und
# verworfen — sonst stuende das Druckdatum einer PDF im Kalender.
# ⚠ ALLE VIER LAENDER, auch wenn heute fast nur DE etwas liefert (LU: 3 Vorgaenge): AT und CH haben bei den
# Vergabeunterlagen 0 % Abdeckung, ihr Lauf schreibt also nichts. Er ist trotzdem richtig
# hier — am Tag, an dem die ersten AT-Unterlagen ankommen, steht der Kalender ohne
# Zutun. Und er ist seit dem 2026-08-25 gefahrlos: bis dahin haette ein AT-Lauf ALLE
# 2.945 DE-Dateien geloescht (die Reinigung las „leer" als „alles verwaist").
for L in DE AT CH LU; do
  $PY scripts/export_kalender.py --country "$L" \
    || echo "  ⚠ Verfahrenskalender $L nicht gebaut — die Terminliste bleibt auf altem Stand."
done
# Dateilisten der Portale (subreport DE, vergabeportal AT): was dort LIEGT, ohne dass wir es
# gelesen haben. Lag bis zum 22.08. ungenutzt im Gold-Layer — 944 offene Vergaben ohne
# Volltext haben darüber trotzdem eine Aussage, darunter die ersten 134 für Österreich.
$PY scripts/export_doc_listing.py || echo "  ⚠ Dateilisten nicht exportiert — die Portal-Listen bleiben auf altem Stand."

# Struktur AUS den Unterlagen: Leistungsverzeichnis (GAEB + Preisblatt) und Kriterienmatrix.
# Anders als die Signale oben ist das keine Ableitung aus Fließtext, sondern die Tabelle
# selbst — „wie viel wovon" und „woran werde ich gemessen". Läuft über den vorhandenen
# Archiv-Bestand, braucht kein Netz und keine LLM, also täglich unproblematisch.
# Reihenfolge ist Pflicht: extract_criteria liest doc_lv.parquet aus extract_positions.
# ⚠ SONNTAGS VOLL, wie die Dubletten-Firewall — und aus demselben Grund. `extract_positions`
# uebernimmt seit dem 2026-09-03 unveraenderte Vorgaenge aus dem letzten Lauf, statt jede
# Nacht 10.216 Archive neu zu entpacken. Der Merker erkennt geaenderte ARCHIVE zuverlaessig,
# aber nicht jede denkbare Aenderung am Leser; `PARSER_STAND` deckt die bewussten ab, der
# Wochenlauf die unbewussten. Er faellt auf einen Tag, an dem niemand auf frische Zahlen
# wartet.
step "Leistungsverzeichnisse + Kriterienmatrizen aus den Unterlagen"
_LV_ARGS=""
if [ "$(date +%u)" = "7" ]; then
  _LV_ARGS="--voll"
  echo "  Sonntag: alle Archive neu lesen (kein Merker)."
fi
# shellcheck disable=SC2086  # _LV_ARGS ist bewusst wortgetrennt
if $PY scripts/extract_positions.py --country DE $_LV_ARGS; then
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
fi   # Ende Phase „dokumente"

# Ab hier: VEROEFFENTLICHEN — laeuft in JEDER Phase, s. Erklaerung oben.
step "Marktpuls berechnen (Saison + Jahre 2004-2025 + Lage)"
$PY scripts/build_marktpuls.py --ab-jahr 2004 || echo "  ⚠ marktpuls.json bleibt auf dem letzten Stand — die Anzeige weist das aus."

step "Namenswoerter-Tabelle (Grundlage des Impressum-Pruefers)"
# Die Tabelle sagt, wie selten ein Wort in Firmennamen ist. Der Impressum-Pruefer
# entscheidet daran sein *Traegerwort*: das seltenste Wort eines Firmennamens muss im
# Impressum stehen, sonst zaehlt der Treffer nicht.
#
# WARUM DAS TAEGLICH LAUFEN MUSS: sie leitet sich aus entities.parquet ab und veraltet
# mit ihm. Bleibt sie stehen, waehrend der Bestand waechst, halten neue Allerweltswoerter
# sich weiter fuer selten — der Pruefer wird schleichend nachlaessiger, ohne dass
# irgendwo etwas rot wird. Gemessen am 2026-08-17 kostete eine fehlende Unterscheidung
# 5,5 % Fehlbestaetigungen: fremde Firma auf fremder Domain als „belegt" durchgewinkt.
#
# Schlaegt der Schritt fehl, bleibt die alte Tabelle stehen (der Bau schreibt erst
# daneben und benennt dann um). Das ist der richtige Ausgang: eine leicht veraltete
# Tabelle ist harmlos, eine halb geschriebene waere es nicht.
$PY scripts/build_namenswoerter.py || echo "  ⚠ Namenswoerter-Tabelle bleibt auf dem letzten Stand"

step "Bundeslaender ableiten (fuer Leads ohne NUTS-Kennung)"
# ⚠ REIHENFOLGE. Das muss VOR dem Frontend-Export laufen, sonst liest der Export die
# Ableitung von GESTERN — und beim ersten Lauf gar keine. Beim Einbauen hatte ich sie
# hinter den Export gesetzt; aufgefallen ist es nur, weil die Zeilennummern nicht passten.
#
# Die Ableitung schliesst die groesste sichtbare Luecke des Bestands: bei den offenen Leads
# fehlte das Bundesland zu 40 %, weil die unterschwelligen Quellen keine NUTS-Kennung
# liefern. Wer im Explorer nach Bundesland filtert, verlor vier von zehn Ausschreibungen.
$PY scripts/region_ableiten.py \
  || echo "  ⚠ Regions-Ableitung fehlgeschlagen — Bundeslaender bleiben so lueckenhaft wie die Quelle."

step "Frontend-Daten exportieren (web/data)"
if teil export_web_leads $PY scripts/export_web_leads.py; then
  # ACHTUNG: export_web_leads.py schreibt plz-geo.json komplett neu und wirft dabei den
  # Stadt-Index `_cities` weg (Umkreissuche über Stadtnamen). Der Index MUSS direkt danach
  # neu gebaut werden, sonst findet die Stadtsuche im Frontend nichts mehr.
  teil build_city_index $PY scripts/build_city_index.py || echo "  ⚠ Stadt-Index nicht gebaut — Umkreissuche über Städte fällt aus."
  teil export_suppliers $PY scripts/export_suppliers.py || echo "  ⚠ Lieferanten-Index nicht gebaut — Onboarding-Matching bleibt auf altem Stand."
  # ── ZWEI PRODUKTWEGE, DIE BIS 2026-08-23 IN KEINEM LAUF STANDEN ────────────────────
  #
  # Beide schreiben nach `web/data` und wurden trotzdem nie gebaut. Aufgefallen ist es
  # erst, als die Frischepruefung auf `web/data` ausgeweitet wurde:
  # `firma-profiles.json` war 23 TAGE alt (16,6 MB) und speist die /firma-Seite.
  # Klassischer Fall von „gebaut, aber nicht verdrahtet" — eine Ebene weiter aussen als
  # die Gold-Builder, und deshalb von Sonde 1 lange nicht gesehen.
  teil export_web_awards $PY scripts/export_web_awards.py \
    || echo "  ⚠ Zuschlagsphase nicht gebaut — die Ansicht bleibt auf altem Stand."
  # 70 MB. Laeuft NACH den Leads, weil es `lead_export` liest.
  teil export_firma_profiles $PY scripts/export_firma_profiles.py \
    || echo "  ⚠ Firmenprofile nicht gebaut — /firma bleibt auf altem Stand."
  # Vorgangsakten (/vorgang): Ausschreibung, Korrekturen, Unterlagen und Zuschlag unter einer
  # Nummer. MUSS NACH DEN LEADS LAUFEN — es liest `web/data/leads-*.json`, um die Produktmenge
  # zu bestimmen (rund 36.000 von 1,47 Mio. Vorgaengen). Vorher gelesen wuerde es die Menge
  # von gestern aufbereiten, und das faellt niemandem auf: alte Akten sehen aus wie frische.
  # Braucht ausserdem build_vorgaenge.py (Z. 1058) und export_doc_listing.py (Z. 1076) davor.
  teil export_vorgaenge $PY scripts/export_vorgaenge.py \
    || echo "  ⚠ Vorgangsakten nicht gebaut — /vorgang bleibt auf altem Stand."
  # Strategie-Aggregate: eigener Export, weil er 36 Monate braucht (unternehmerische
  # Planung), während die Lead-Liste auf 24 gedeckelt ist (Handlungsrelevanz). Fehlte
  # bisher im Tageslauf — /api/strategie las deshalb einen Stand vom 28. Juli.
  teil export_strategie $PY scripts/export_strategie.py >/dev/null \
    || echo "  ⚠ Strategie-Aggregate nicht gebaut — die Strategie-Ansicht bleibt auf altem Stand."
  # Regionalansicht (Strategie-Sektion „Region"): region_kpi.parquet → web/data/regionen.json.
  # 174 KB, reines Umformen, unter einer Sekunde. Ohne diesen Schritt bliebe die Ansicht auf
  # dem Stand des Tages stehen, an dem sie gebaut wurde — und niemand saehe es, denn eine
  # alte Regionsdatei sieht genauso aus wie eine frische. Genau so verlor `export_doc_text`
  # monatelang unbemerkt den Anschluss.
  teil export_regionen $PY scripts/export_regionen.py \
    || echo "  ⚠ Regionen-Export fehlgeschlagen — die Regionalansicht bleibt auf altem Stand."
    # Zahlen der oeffentlichen Startseite. Sie stehen dort NICHT im Quelltext, weil eine
    # getippte Zahl in dem Moment veraltet, in dem sie jemand tippt — und niemand merkt es.
    teil export_landing $PY scripts/export_landing.py \
      || echo "  ⚠ Startseiten-Zahlen nicht aktualisiert — die Startseite zeigt den alten Stand."
  # web/data liegt seit dem 2026-08-18 NICHT mehr in Git (s. .gitignore dort). Damit ist
  # dieser Schritt die einzige Bruecke zwischen dem Export hier und dem Deployment: ohne ihn
  # zeigt die Cloud-Fassung den Stand des letzten Uploads, und niemand sieht es, denn alte
  # Daten sehen aus wie frische. Ist kein Speicher konfiguriert, sagt das Skript das und
  # bricht den Tageslauf NICHT ab — lokal ist die Platte weiterhin die Quelle.
  teil upload_web_data $PY scripts/upload_web_data.py \
    || echo "  ⚠ Upload uebersprungen oder unvollstaendig — Deployment bleibt auf altem Stand."

  # Qualitaetsbericht ZULETZT: er misst, was die Schritte davor hinterlassen haben. Jede
  # Zahl darin wurde bis zum 2026-08-18 von Hand ermittelt — und was von Hand gemessen wird,
  # misst niemand taeglich. Genau so blieben 14 statt 4.499 Volltexte monatelang unbemerkt.
  teil qualitaet_bericht $PY scripts/qualitaet_bericht.py >/dev/null \
    || echo "  ⚠ Qualitaetsbericht nicht geschrieben — Verschlechterungen faellen dann niemandem auf."
  echo "  Frontend-Daten ok."
else
  echo "  ✖ Frontend-Export fehlgeschlagen — die App zeigt weiter den alten Stand."
fi

# 4) Schema selbstheilend migrieren (neue Parquet-Spalten → gov_*-Tabellen) via psql, dann pushen.
#
# ⚠ DER gov_*-PUSH IST STANDARDMAESSIG AUS. Am 2026-08-16 meldete Supabase das Ueberschreiten
# des Free-Limits: 787 MB bei 500 MB erlaubt. Gemessen waren 775 MB davon (98,5 %) die acht
# `gov_*`-Tabellen — und die liest NIEMAND. Das Frontend holt seine Leads aus
# `web/data/leads-<branche>.json` (aus lokalem Parquet gebaut); aus Supabase kommen nur die
# `user_*`-Tabellen, zusammen 568 kB. Geprueft: kein `.from("gov_...")` im Web-Code, keine
# View, kein Fremdschluessel, keine Funktion, die sie referenziert.
#
# Die Datenkette darueber laeuft unveraendert weiter — es entsteht also KEIN Rueckstand.
# Der Bestand bleibt lokal aktuell; beim Go-live ist der Weg zurueck ein Befehl:
#     GOVISOR_SUPABASE_GOV_PUSH=1 scripts/daily_leads.sh
#     # oder direkt: python3 scripts/export_supabase.py --table all --prune
#
# ⚠ NICHT mit-abschalten: `gap_effects.py` weiter unten schreibt `user_gap_effects` — eine
# ECHTE Nutzertabelle, die das Frontend liest. Sie haengt an SUPABASE_URL, nicht am Push.
GOV_PUSH="${GOVISOR_SUPABASE_GOV_PUSH:-0}"
if [ -n "${SUPABASE_URL:-}" ] && [ -n "${SUPABASE_SERVICE_KEY:-}" ] && [ "$GOV_PUSH" = "1" ]; then
  step "Supabase-Schema-Migration (DDL aus aktuellem Parquet, idempotent via psql)"
  $PY scripts/export_supabase.py --table all --ddl-only
  REF="$(echo "$SUPABASE_URL" | sed -E 's#https?://([a-z0-9]+)\.supabase\.co.*#\1#')"
  # PSQL SELBST FINDEN, nicht auf den PATH verlassen. Gemessen 2026-08-15: psql liegt unter
  # /opt/homebrew/bin, und der launchd-PATH (in der plist fest verdrahtet) kennt nur
  # /usr/local/bin, /usr/bin, /bin, /usr/sbin, /sbin. Unter launchd waere die Migration also
  # STILL uebersprungen worden — mit dem Hinweis „im Dashboard ausfuehren", den nachts
  # niemand liest. Aus dem Terminal lief sie, weil dort Homebrew im PATH steht: genau die
  # Sorte Unterschied, die man erst im Ausfall bemerkt.
  PSQL="$(command -v psql || true)"
  for _p in /opt/homebrew/bin/psql /usr/local/bin/psql /Applications/Postgres.app/Contents/Versions/latest/bin/psql; do
    [ -n "$PSQL" ] && break
    [ -x "$_p" ] && PSQL="$_p"
  done
  if [ -z "$PSQL" ]; then
    echo "  ⚠ psql nicht gefunden — Schema-Migration uebersprungen. Das DDL liegt in"
    echo "    docs/supabase_schema.sql und muss im Supabase-Dashboard laufen."
  fi
  if [ -f "$ROOT/.secrets/supabase_db.txt" ] && [ -n "$PSQL" ]; then
    if PGPASSWORD="$(tr -d '[:space:]' < "$ROOT/.secrets/supabase_db.txt")" "$PSQL" \
         -h "db.$REF.supabase.co" -p 5432 -U postgres -d postgres \
         -v ON_ERROR_STOP=1 -q -f docs/supabase_schema.sql >/dev/null; then
      # PostgREST hält einen eigenen Schema-Cache. Nach DDL kennt es neue Spalten erst
      # nach einem Reload — sonst PGRST204 („column not found in the schema cache"),
      # obwohl die Spalte in der Datenbank längst existiert (genau der Fehler am 09.08.).
      PGPASSWORD="$(tr -d '[:space:]' < "$ROOT/.secrets/supabase_db.txt")" "$PSQL" \
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
fi

# 5) Lücken-Wirkung je Nutzer vorberechnen (#11 §7) — nicht fatal, Frontend hat On-Demand-Fallback.
# Laeuft UNABHAENGIG vom gov_*-Push: `user_gap_effects` ist eine Nutzertabelle, die das
# Frontend wirklich liest. Sie darf nicht mit dem Spiegel-Push zusammen abgeschaltet werden.
if [ -n "${SUPABASE_URL:-}" ] && [ -n "${SUPABASE_SERVICE_KEY:-}" ]; then
  if [ "$GOV_PUSH" != "1" ]; then
    echo "  · gov_*-Push übersprungen (GOVISOR_SUPABASE_GOV_PUSH≠1) — Supabase hält nur Nutzerdaten."
  fi
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
if [ -n "$_SCHRITT_NAME" ]; then
  printf '  ⏱ %s — %ds\n' "$_SCHRITT_NAME" "$(( SECONDS - _SCHRITT_START ))"
fi

step "Ertragsbericht (Trichter, Reichweite, Auslesequalitaet)"
# Rein lesend und schnell — deshalb ohne Zeitgrenze und ohne `||`-Abfangen an dieser
# Stelle nicht noetig: faellt er aus, fehlt eine Anzeige, keine Daten.
$PY -m govisor.ertrag --country DE || echo "  ⚠ Ertragsbericht nicht geschrieben."

# ── ALTERSBERICHT ────────────────────────────────────────────────────────────────────────
#
# WARUM. Am 2026-08-14 lief der Tageslauf formal durch — jeder Schritt gruen — und die
# Anforderungs-Signale entstanden trotzdem aus einem Volltext-Index vom 31. JULI. Zwei
# Wochen alt, und niemand konnte es sehen: „Schritt erfolgreich" heisst nur, dass das
# Programm nicht abgestuerzt ist, nicht dass sein Ergebnis frisch ist.
#
# Ein Schritt kann aus drei Gruenden nichts Neues erzeugen und trotzdem gruen melden: die
# Quelle lieferte nichts, er wurde uebersprungen (Lock, Zeitbudget), oder er fiel weich aus
# (`|| echo`). In allen drei Faellen ist das Datum der Datei die einzige ehrliche Auskunft.
#
# Bewusst NUR eine Warnung, kein Abbruch: ein veralteter Baustein ist ein Grund
# hinzusehen, keiner den Lauf wegzuwerfen — der Rest der Kette ist ja in Ordnung.
alter_tage() {
  [ -e "$1" ] || { echo "-"; return; }
  echo $(( ( $(date +%s) - $(stat -f %m "$1" 2>/dev/null || echo 0) ) / 86400 ))
}
echo ""
echo "── Altersbericht (Tage seit letzter Aenderung)"
_ALT=0
for eintrag in \
  "data/gold/DE/lead_export.parquet:1:Leads (Frontend-Quelle)" \
  "data/gold/DE/notice_duplicates.parquet:2:Dubletten-Firewall" \
  "data/docs/DE/doc_text.parquet:7:Volltext-Index der Unterlagen" \
  "data/docs/DE/doc_signals.parquet:7:Anforderungs-Signale" \
  "web/data/leads-bau.json:1:Frontend-Daten" \
  "web/data/marktpuls.json:2:Marktpuls"
do
  _d="${eintrag%%:*}"; _rest="${eintrag#*:}"; _max="${_rest%%:*}"; _name="${_rest#*:}"
  _t="$(alter_tage "$ROOT/$_d")"
  if [ "$_t" = "-" ]; then
    printf '  ⚠ %-32s FEHLT\n' "$_name"; _ALT=1
  elif [ "$_t" -gt "$_max" ]; then
    printf '  ⚠ %-32s %s Tage alt (erwartet <= %s)\n' "$_name" "$_t" "$_max"; _ALT=1
  else
    printf '  ✓ %-32s %s Tage\n' "$_name" "$_t"
  fi
done
[ "$_ALT" = "1" ] && echo "  → Ein Baustein ist aelter als erwartet. Gruener Lauf heisst NICHT frische Daten."

# ── VERDRAHTUNGSPRUEFUNG ─────────────────────────────────────────────────────────────────
#
# Der Altersbericht daruber ist eine HANDGEPFLEGTE Liste von sechs Eckpfeilern. Genau das
# war die Luecke: `lead_lot` und `lead_text` standen nie drauf, wurden im DACH-Lauf nie
# gebaut und fielen 10 bzw. 12 Tage zurueck, ohne dass irgendetwas rot wurde. Wer eine
# neue Tabelle baut, denkt nicht daran, sie hier nachzutragen.
#
# Die Sonde dreht das um: sie beobachtet ALLE Gold-Dateien und fuehrt stattdessen die
# Ausnahmen — mit Begruendung, und `tests/test_verdrahtung.py` haelt die Liste ehrlich.
#
# BEIDE bleiben stehen, weil sie verschiedene Ausfaelle sehen:
#   Altersbericht  absolute Frische weniger Eckpfeiler → merkt, wenn der GANZE Lauf steht
#   Sonde 1        Frische relativ zum Landeslauf      → merkt, wenn EIN Schritt fehlt
# Faellt alles gleichzeitig aus, ist die Sonde blind (ihr Bezugspunkt wandert mit) und der
# Altersbericht der einzige Waechter. Umgekehrt sieht der Altersbericht nur seine sechs.
#
# Warnung, kein Abbruch — aus demselben Grund wie oben.
echo ""
$PY scripts/pruefe_verdrahtung.py \
  || echo "  → Verdrahtungspruefung meldet Befunde. Details: python3 scripts/pruefe_verdrahtung.py --offen"

# ⚠ WERTETABELLEN. Die Verdrahtungssonde darueber fragt „wird es GEBAUT?" — diese hier fragt
# „kennt es das LAND?". Zwei verschiedene Ausfaelle: eine Tabelle kann taeglich frisch
# gebaut werden und trotzdem ein Land nicht kennen. Genau das war am 2026-09-03 dreimal der
# Fall (PLZ-Stellen, Regionslaengen, Locale) — kein Fehler, keine leere Datei, nur ein
# schlechteres Ergebnis. Deshalb laeuft sie direkt daneben.
$PY scripts/pruefe_laender_tabellen.py \
  || echo "  → Wertetabellen unvollstaendig. Details: python3 scripts/pruefe_laender_tabellen.py --alle"

# ── Sonde 5: haelt ein endgueltiges Urteil noch? ─────────────────────────────────────────
# Stati aus DAUERHAFT/KEIN_FEHLSCHLAG werden NIE WIEDER angefasst. Zwischen dem 20. und dem
# 31.08. sind neun solcher Vermerke von Hand widerlegt worden, immer derselbe Satzbau: aus
# dem Verhalten eines Portals wurde eine Eigenschaft des Vorgangs. Diese Sonde sucht die
# Klasse selbst, damit es keine Handrunde mehr braucht.
# ⚠ Sie schreibt nichts (Temp-Verzeichnis) und darf deshalb neben einem Abrufer laufen.
$PY scripts/pruefe_endgueltige.py --stichprobe 8 \
  || echo "  → Ein endgueltiges Urteil haelt nicht mehr. Details: python3 scripts/pruefe_endgueltige.py --offen"

# ── Sonde 6: eine Regionskennung, die in Wahrheit ein Vorgabewert ist ────────────────────
# Der Anlass (2026-09-01): die DÖE-Quelle kannte ueber ihren GESAMTEN Bestand genau einen
# NUTS-Wert — DEA22, den Sitz des eSenders. Er stand auf 33.966 Kaeuferzeilen in 393 Orten,
# und im Frontend landeten 172 Magdeburger Leads unter „Nordrhein-Westfalen", als
# `regionQuelle='amtlich'`. Nichts ist dabei gescheitert; die Regions-ABDECKUNG stieg sogar.
# ⚠ Die Sonde prueft SILBER, nicht Gold — dort schreibt der Parser hin, und dort faellt es
# auf, bevor es sich ueber Entities, Leads und Frontend verteilt. Sie liest nur.
# Warnung, kein Abbruch — wie die uebrigen Sonden.
$PY scripts/pruefe_nuts_vorgabe.py \
  || echo "  → NUTS-Waechter meldet einen Vorgabewert. Details: python3 scripts/pruefe_nuts_vorgabe.py --alle"

# ── SONDIERUNG GEGEN AUFNAHME ────────────────────────────────────────────────────────────
#
# Ein sondiertes Land ist angesehen, nicht angebunden. Der Unterschied verschwindet leise:
# beim Bau der Vorgangs-Tabellen wurde nebenbei fuer PL und EU geschrieben, damit galten
# beide als aufgenommene Laender, und die Paritaetssonde meldete 40 bestehende Tabellen als
# Luecke. Niemand hatte Polen aufgenommen — es sah nur so aus.
#
# Bei einer EU-weiten Sondierung droht derselbe Fehler dreissigmal, deshalb steht die Wache
# HIER und nicht nur im Test: sie vergleicht den Zustand auf der Platte mit der Registry,
# und zwar an dem Tag, an dem geschrieben wurde. Warnung, kein Abbruch — wie die uebrigen.
$PY scripts/pruefe_sondierung.py \
  || echo "  → Sondierungs-Waechter meldet Befunde. Details: python3 scripts/pruefe_sondierung.py"

# ── BIBEL-PRUEFUNG ───────────────────────────────────────────────────────────────────────
#
# Die Laender-Bibel (docs/laender/) altert anders als Code: sie faellt nicht um, sie wird
# nur langsam falsch. Am 2026-08-23 wurde sie an einem Tag geschrieben und am selben Tag
# zweimal von der Wirklichkeit ueberholt — sechs Zahlen drifteten binnen Stunden.
#
# Drei Pruefungen: Zahlen ohne Datum (die altern lautlos), Behauptungen gegen die
# LIVE-Daten (nicht gegen das Feld, das die Antwort behauptet), und Doppelpflege mit
# CLAUDE.md (wer eine Aussage an zwei Stellen fuehrt, pflegt sie an einer nicht).
#
# Warnung, kein Abbruch — wie die Verdrahtungspruefung.
$PY scripts/pruefe_bibel.py \
  || echo "  → Bibel-Pruefung meldet Befunde. Details: python3 scripts/pruefe_bibel.py --offen"

# Alte Logs aufräumen (>30 Tage)
find "$LOG_DIR" -name 'daily-*.log' -type f -mtime +30 -delete 2>/dev/null || true
