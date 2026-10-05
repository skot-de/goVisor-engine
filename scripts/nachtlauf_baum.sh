#!/bin/bash
# Richtet den Nachtlauf-Baum ein oder prueft ihn — den Baum, der NICHTS tut als laufen.
#
# ⛔ WARUM ES IHN GIBT. Bis zum 2026-10-05 fuhr der Nachtlauf den Haupt-Baum, und damit lief,
# was dort gerade ausgecheckt war. An dem Tag war das ein Zweig ohne den KMU-Fix vom 01.09.:
# fuenf Wochen lang schrieb alter Code in `web/data/strategie.json`, waehrend die Pruefungen
# in den Arbeitsbaeumen gruen aussahen — `data` und `web/data` sind dort Symlinks hierher.
# Seitdem hat der Lauf einen eigenen Baum auf `main`, in dem niemand arbeitet.
#
#     scripts/nachtlauf_baum.sh --pruefen      # ist er vollstaendig? (Rueckgabe 1, wenn nicht)
#     scripts/nachtlauf_baum.sh --einrichten   # Verknuepfungen anlegen/reparieren
#
# ⚠ ER WIRD NICHT AUS GIT VOLLSTAENDIG. Sechs Dinge liegen ausserhalb der Versionierung, und
# jedes einzelne faellt anders aus, wenn es fehlt:
#   .secrets           ohne sie kein OpenRouter, kein Supabase — der Lauf bricht laut ab
#   data               das externe Volume; ohne es gibt es nichts zu rechnen
#   web/.env.local     Schluessel fuer die Web-Seite
#   web/data           ⚠ die AUSGABE. Fehlt der Link, schreibt der Lauf in ein EIGENES
#                      Verzeichnis, das niemand liest — und alles sieht erfolgreich aus.
#   web/node_modules   zwei Pruefungen fahren `node` gegen die echten Dateien
#   .tmp               Arbeitsablage auf demselben Volume wie die Daten
set -uo pipefail

HAUPT="/Users/svko_macmini/PROJEKTE/claude_code/C09_govisor"
BAUM="/Users/svko_macmini/PROJEKTE/claude_code/C09_govisor-nachtlauf"
DATEN="/Volumes/goVisor/govisor-data"
ZWEIG="main"

# ziel<TAB>quelle — die Quelle ist der Ort, auf den der Link zeigt.
VERKNUEPFUNGEN=(
  ".secrets|$HAUPT/.secrets"
  "data|$DATEN"
  ".tmp|data/.tmp"
  "web/.env.local|$HAUPT/web/.env.local"
  "web/data|$HAUPT/web/data"
  "web/node_modules|$HAUPT/web/node_modules"
)

modus="${1:---pruefen}"
fehler=0

if [ ! -d "$BAUM" ]; then
  echo "⛔ Der Nachtlauf-Baum fehlt: $BAUM"
  echo "   Anlegen (aus einem Arbeitsbaum heraus):"
  echo "     git worktree add $BAUM $ZWEIG"
  echo "   danach: scripts/nachtlauf_baum.sh --einrichten"
  exit 1
fi

# Auf welchem Zweig steht er? ⚠ `.git` ist in einem Arbeitsbaum eine DATEI, kein Verzeichnis.
gitdir="$BAUM/.git"
if [ -f "$gitdir" ]; then
  gitdir="$(sed -n 's/^gitdir: //p' "$BAUM/.git")"
fi
ist_zweig="$(sed -n 's|^ref: refs/heads/||p' "$gitdir/HEAD" 2>/dev/null)"
if [ "$ist_zweig" != "$ZWEIG" ]; then
  echo "⛔ Der Nachtlauf-Baum steht auf '${ist_zweig:-?}' statt auf '$ZWEIG'."
  echo "   Damit laeuft nachts wieder ein Arbeitsstand — genau der Zustand vom 2026-10-05."
  fehler=1
else
  echo "✓ Zweig: $ZWEIG"
fi

# ⛔ STIMMT DER INHALT MIT DEM EIGENEN HEAD UEBEREIN?
#
# Am 2026-10-05 stand hier ein GESTAGTES LOESCHEN auf einer Datei, die HEAD mit 21.570 Bytes
# traegt — niemand hatte sie angefasst. Ursache war kein `add`, sondern die Mechanik: der Zweig
# wurde per `update-ref` aus einem ANDEREN Baum weitergeschoben, waehrend dieser hier darauf
# steht. Sein HEAD zeigt dann auf den neuen Commit, sein Index steht auf dem alten — und jede
# seither hinzugekommene Datei erscheint als geloescht.
#
# ⚠ Der Schaden faellt eine Stufe weiter an: wer von hier aus committet, fuehrt das Loeschen
# AUS, unter einer Nachricht, die von etwas ganz anderem handelt. Gefunden hat es eine andere
# Sitzung von Hand; diese Pruefung soll das naechste Mal frueher dran sein.
#
# ⚠ Ein blosses `git status` taugt nicht: der Lauf traegt selbst erzeugte Zahlen nach, die
# IMMER abweichen. Gemeldet wird deshalb nur das gestagte LOESCHEN — das ist der Fall, der
# Arbeit vernichtet.
if command -v git >/dev/null 2>&1 && [ -e "$BAUM/.git" ]; then
  geloescht="$(git -C "$BAUM" diff --cached --name-only --diff-filter=D HEAD 2>/dev/null | head -8)"
  if [ -n "$geloescht" ]; then
    echo "⛔ GESTAGTE LOESCHUNGEN — ein Commit von hier wuerde sie ausfuehren:"
    echo "$geloescht" | sed 's/^/     /'
    echo "   Meist die Folge eines update-ref auf diesen Zweig aus einem anderen Baum."
    echo "   Reparieren:  git -C $BAUM restore --source=HEAD --staged --worktree ."
    fehler=1
  else
    echo "✓ keine gestagten Loeschungen"
  fi
fi

for eintrag in "${VERKNUEPFUNGEN[@]}"; do
  ziel="${eintrag%%|*}"
  quelle="${eintrag#*|}"
  pfad="$BAUM/$ziel"
  if [ "$modus" = "--einrichten" ]; then
    mkdir -p "$(dirname "$pfad")"
    ln -sfn "$quelle" "$pfad"
  fi
  if [ ! -e "$pfad" ]; then
    echo "  ⛔ fehlt: $ziel  (soll zeigen auf $quelle)"
    fehler=1
  elif [ ! -L "$pfad" ]; then
    # ⚠ Ein echtes Verzeichnis statt eines Links ist der gefaehrlichere Fall: bei `web/data`
    # schreibt der Lauf dann in eine Kopie, die niemand liest, und meldet Erfolg.
    echo "  ⚠ $ziel ist ein echtes Verzeichnis, kein Link — der Lauf schreibt am Ziel vorbei."
    fehler=1
  else
    echo "  ✓ $ziel → $(readlink "$pfad")"
  fi
done

if [ "$fehler" -ne 0 ]; then
  [ "$modus" = "--einrichten" ] \
    && echo "⛔ Noch nicht vollstaendig — die Meldungen oben nennen, was fehlt." \
    || echo "⛔ Unvollstaendig. Reparieren: scripts/nachtlauf_baum.sh --einrichten"
  exit 1
fi
echo "✓ Der Nachtlauf-Baum ist vollstaendig."
