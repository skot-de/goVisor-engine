#!/usr/bin/env bash
# Wer arbeitet gerade woran? — und gehoert das, was ich anfangen will, schon jemandem?
#
#     scripts/wer_macht_was.sh                      Uebersicht aller Baeume und Branches
#     scripts/wer_macht_was.sh web/app/impressum/page.tsx web/lib/anbieter.ts
#                                                   gehoeren DIESE Pfade schon jemandem?
#     scripts/wer_macht_was.sh --kein-abruf         ohne `git fetch` (schneller, aber veraltet)
#
# WARUM ES DIESES SKRIPT GIBT. Am 2026-10-03 habe ich angefangen, Impressum und
# Datenschutzerklaerung zu bauen — beides lag fertig auf `origin/web/grounding-page`, gebaut
# von einer anderen Sitzung. Eine Stunde Doppelarbeit, gestoppt nur, weil eine dritte Sitzung
# zufaellig mitlas.
#
# ⚠ EIN WORKTREE HAETTE DAS NICHT VERHINDERT, und das ist der Punkt. Worktrees verhindern, dass
#   zwei Sitzungen dieselbe Datei BESCHREIBEN. Sie verhindern nicht, dass zwei Sitzungen
#   dasselbe BAUEN. Mein Fehlschluss war „neue Dateien, also keine Kollision" — ueber Branches
#   hinweg ist das einfach falsch.
#
# ⚠ UND DER GEFAEHRLICHE AUSFALL IST DIE FALSCHE BERUHIGUNG. Ohne `git fetch` sind die
#   Remote-Refs veraltet, und dann meldet dieses Skript „niemand arbeitet daran" — genau die
#   Auskunft, die den Fehler verursacht hat. Deshalb wird standardmaessig abgerufen, und ein
#   FEHLGESCHLAGENER Abruf bricht laut ab statt stillschweigend mit altem Stand zu antworten.
#   Dieselbe Fehlerklasse wie `grep -q` auf einer unlesbaren Datei (s. memory launchd-Fallen).

set -uo pipefail

ABRUF=ja
PFADE=()
for a in "$@"; do
  case "$a" in
    --kein-abruf) ABRUF=nein ;;
    -h|--hilfe|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) PFADE+=("$a") ;;
  esac
done

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "kein Git-Baum"; exit 2; }
# ⚠ `--show-toplevel` liefert in einem Worktree DESSEN Wurzel. Fuer die Uebersicht brauchen wir
#   aber alle Baeume, und `git worktree list` kennt sie von jedem Baum aus. Passt also.

if [ "$ABRUF" = ja ]; then
  if ! git fetch --quiet --prune origin 2>/dev/null; then
    echo "⛔ ABBRUCH: `git fetch` fehlgeschlagen."
    echo "   Ohne Abruf waeren die Remote-Refs veraltet, und dieses Skript wuerde"
    echo "   „niemand arbeitet daran\" melden — genau die falsche Beruhigung, gegen die es"
    echo "   gebaut ist. Entweder Netz pruefen oder bewusst --kein-abruf setzen."
    exit 3
  fi
fi
[ "$ABRUF" = nein ] && echo "⚠ OHNE ABRUF — der Stand kann veraltet sein."

HAUPT=$(git rev-parse --abbrev-ref HEAD)

# Alle Branches, die etwas vor origin/main haben: lokale und entfernte, ohne Dubletten.
branches() {
  { git for-each-ref --format='%(refname:short)' refs/heads
    git for-each-ref --format='%(refname:short)' refs/remotes/origin \
      | grep -v '^origin/HEAD$' | grep -v '^origin/main$'
  } | sed 's|^origin/||' | sort -u
}

# Dateien eines Branches gegenueber dem gemeinsamen Vorfahren mit origin/main.
# ⚠ NICHT gegen origin/main direkt. Ist origin/main weitergelaufen, zeigte das fremde
#   Dateien, die der Branch nie angefasst hat — und dann sucht man Kollisionen, die es
#   nicht gibt, und uebersieht die echten.
dateien() {
  local ref="$1" basis
  basis=$(git merge-base refs/remotes/origin/main "$ref" 2>/dev/null) || return 1
  git diff --name-only "$basis".."$ref" 2>/dev/null
}

# Welchen Ref nehmen wir je Branch? Den entfernten, wenn es ihn gibt (das ist, was die
# anderen SEHEN koennen), sonst den lokalen.
ref_fuer() {
  local b="$1"
  if git rev-parse --verify --quiet "refs/remotes/origin/$b" >/dev/null; then
    echo "refs/remotes/origin/$b"
  elif git rev-parse --verify --quiet "refs/heads/$b" >/dev/null; then
    echo "refs/heads/$b"
  fi
}

# ── Modus 1: gehoeren bestimmte Pfade schon jemandem? ───────────────────────────────────
if [ ${#PFADE[@]} -gt 0 ]; then
  echo "── Gehoeren diese Pfade schon jemandem? ──"
  gefunden=0
  for p in "${PFADE[@]}"; do
    treffer=""
    # ⚠ LIEGT DER PFAD SCHON AUF origin/main? Dann ist „liegt dort" KEINE Auskunft: die Datei
    #   liegt dann auf jedem Nachkommen, und das Werkzeug meldete acht Branches, von denen
    #   keiner etwas damit zu tun hat. Gemessen am 2026-10-03 an `tests/test_marktwert.py` —
    #   acht Treffer, null Erkenntnis, und das echte Signal („wer hat sie GEAENDERT")
    #   ertrank darin. Bei solchen Pfaden zaehlt nur noch, wer sie anfasst.
    auf_main=nein
    git cat-file -e "refs/remotes/origin/main:$p" 2>/dev/null && auf_main=ja
    while read -r b; do
      [ -z "$b" ] && continue
      r=$(ref_fuer "$b"); [ -z "$r" ] && continue
      if dateien "$r" 2>/dev/null | grep -qxF "$p"; then
        treffer="$treffer $b(geaendert)"
      elif [ "$auf_main" = nein ] && git cat-file -e "$r:$p" 2>/dev/null; then
        # Neu angelegt und nicht auf main: genau der Fall, der zu Doppelarbeit fuehrt.
        treffer="$treffer $b(neu angelegt)"
      fi
    done < <(branches)
    if [ -n "$treffer" ]; then
      echo "  ⛔ $p →$treffer"
      gefunden=1
    elif [ "$auf_main" = ja ]; then
      # ⚠ KEIN ⛔. Die Datei existiert, aber niemand arbeitet daran — sie zu aendern ist
      #   normale Arbeit, kein Konflikt. Ein Werkzeug, das hier rot wird, ist bei jeder
      #   bestehenden Datei rot und damit wertlos.
      echo "  ✓  $p → liegt auf origin/main, niemand aendert sie gerade"
    else
      echo "  ✓  $p → niemand"
    fi
  done
  if [ "$gefunden" = 1 ]; then
    echo
    echo "  ⛔ Mindestens ein Pfad gehoert schon jemandem. NICHT neu bauen, sondern die"
    echo "     Sitzung fragen, die den Branch haelt. Zwei Fassungen desselben Dings sind"
    echo "     teurer als eine Nachfrage."
    exit 1
  fi
  exit 0
fi

# ── Modus 2: Uebersicht ─────────────────────────────────────────────────────────────────
echo "── Arbeitsbaeume ──"
# ⚠ NICHT `--show-toplevel` zum Kuerzen: in einem Worktree liefert das DESSEN Wurzel, nicht
#   die des Haupt-Baums. Die fremden Pfade blieben dann in voller Laenge stehen und die
#   Uebersicht war unlesbar. Der Haupt-Baum ist die ERSTE Zeile von `git worktree list`.
WURZEL=$(git worktree list | head -1 | awk '{print $1}')
git worktree list | while read -r pfad rest; do
  kurz=${pfad/#$WURZEL/.}
  schmutz=$(git -C "$pfad" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  marke=""
  [ "$schmutz" != 0 ] && marke="  ⚠ $schmutz unversionierte/geaenderte Datei(en)"
  printf "  %-58s %s%s\n" "$kurz" "$rest" "$marke"
done

echo
echo "── Branches vor origin/main ──"
declare -a ALLE_DATEIEN=()
while read -r b; do
  [ -z "$b" ] && continue
  r=$(ref_fuer "$b"); [ -z "$r" ] && continue
  n=$(git rev-list --count "refs/remotes/origin/main..$r" 2>/dev/null) || continue
  [ "${n:-0}" = 0 ] && continue
  gepusht="nur lokal"
  git rev-parse --verify --quiet "refs/remotes/origin/$b" >/dev/null && gepusht="gepusht"
  hier=""
  [ "$b" = "$HAUPT" ] && hier="  ← DU"
  printf "  %-34s %2s Commit(s)  %-9s%s\n" "$b" "$n" "$gepusht" "$hier"
  while read -r f; do
    [ -n "$f" ] && ALLE_DATEIEN+=("$f|$b")
  done < <(dateien "$r")
done < <(branches)

echo
echo "── ⛔ Dateien, die MEHR ALS EIN Branch anfasst ──"
# Genau hier entstehen die Konflikte beim Zusammenfuehren, und genau das sieht man sonst erst
# beim Merge.
printf '%s\n' "${ALLE_DATEIEN[@]:-}" | awk -F'|' '
  NF==2 { wer[$1] = wer[$1] " " $2; n[$1]++ }
  END {
    gefunden = 0
    for (f in n) if (n[f] > 1) { printf "  %-52s%s\n", f, wer[f]; gefunden = 1 }
    if (!gefunden) print "  keine — die Branches sind sauber getrennt"
  }' | sort

echo
echo "ⓘ Vor dem Anlegen neuer Dateien: scripts/wer_macht_was.sh <pfad> [<pfad> …]"
