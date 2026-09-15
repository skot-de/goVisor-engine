#!/bin/bash
# ============================================================================
# goVisor — Vorfuehrung ueber einen Cloudflare-Tunnel
#
#     scripts/demo_tunnel.sh
#
# Startet den Produktionsserver auf 127.0.0.1:3000 und haengt einen Tunnel davor.
# Am Ende steht eine oeffentliche https-Adresse, die auf JEDEM Geraet laeuft — iPad,
# Telefon, fremder Rechner. Der Mac mini muss dabei an sein und wach bleiben.
#
# WARUM PRODUKTION UND NICHT `next dev`. Zwei Gruende, beide zaehlen vor Publikum:
#   · `next dev` kompiliert jede Seite beim ERSTEN Aufruf — im Café sind das fuenf bis
#     fuenfzehn Sekunden Weiss, und zwar genau dann, wenn jemand zusieht.
#   · ⚠ Und der entscheidende: in `development` ist die Baustellen-Sperre AUS
#     (`middleware.ts`: BLACKOUT haengt an NODE_ENV === "production"). Ein Tunnel ist
#     eine oeffentliche Adresse. Mit `next dev` stuende die ganze App offen im Netz,
#     samt /intern.
#
# WAS DIE OEFFENTLICHKEIT SIEHT: Schwarz. Der Blackout bleibt scharf; herein kommt nur,
# wer `?preview=<PREVIEW_KEY>` anhaengt (einmal — danach traegt ein Cookie). Der
# Schluessel steht in `web/.env.local`.
#
# ⚠ DER MAC DARF NICHT EINSCHLAFEN. Er steht auf „Ruhezustand nach 1 Minute"; wach ist er
# gerade nur, weil ein Programm im Vordergrund laeuft. Schlaeft er, ist der Tunnel tot —
# und das merkt man erst, wenn man vor jemandem sitzt. Dieses Skript haelt ihn mit
# `caffeinate` wach, solange es laeuft. Dauerhaft ginge `sudo pmset -a sleep 0`.
# ============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-3000}"
WEB="$PWD/web"

if lsof -ti tcp:"$PORT" >/dev/null 2>&1; then
  echo "⛔ Auf Port $PORT laeuft schon etwas. Erst beenden:"
  echo "   lsof -ti tcp:$PORT | xargs kill"
  exit 1
fi

SCHLUESSEL=$(grep -E '^PREVIEW_KEY=' "$WEB/.env.local" 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' ')
if [ -z "$SCHLUESSEL" ]; then
  # FAIL-CLOSED wie die Middleware: ohne Schluessel gibt es keinen Bypass, und dann
  # zeigt die Vorfuehrung eine schwarze Seite. Lieber hier abbrechen als dort.
  echo "⛔ PREVIEW_KEY fehlt in web/.env.local — ohne ihn kommt niemand hinter die Sperre."
  exit 1
fi

echo "── 1/3  Produktionsstand bauen (dauert ein bis zwei Minuten)"
( cd "$WEB" && npm run build ) || { echo "⛔ Build fehlgeschlagen — Tunnel nicht gestartet."; exit 1; }

# ⚠ AUFRAEUMEN MUSS DEN GANZEN BAUM TREFFEN, NICHT NUR DAS KIND.
#
# Der erste Entwurf machte `kill $SERVER` auf die PID der Subshell. Gemessen am
# 2026-09-15: Skript beendet, und `cloudflared` sowie `next start` liefen WEITER —
# Port 3000 belegt, Tunnel offen. Das ist hier kein Schoenheitsfehler: wer Strg-C
# drueckt und das Fenster schliesst, laesst sonst eine oeffentliche Adresse auf seinen
# Rechner zeigen, ohne es zu wissen.
#
# `npx` startet Enkel (node), `caffeinate` haelt nebenher die Zusicherung. Deshalb wird
# der Baum von unten nach oben abgeraeumt.
baum_abraeumen() {
  local pid
  for pid in "$@"; do
    [ -n "${pid:-}" ] || continue
    pkill -P "$pid" 2>/dev/null
    kill "$pid" 2>/dev/null
  done
}

aufraeumen() {
  baum_abraeumen "${TUNNEL:-}" "${SERVER:-}"
  # Nachfassen: was der Baum nicht erwischt hat, trifft der Name. Beide Muster sind eng
  # genug, um keine fremden Laeufe zu treffen (`--url` gehoert zum Quick Tunnel, der
  # Port zu diesem Server).
  pkill -f "cloudflared tunnel --url http://127.0.0.1:$PORT" 2>/dev/null
  lsof -ti tcp:"$PORT" 2>/dev/null | xargs kill 2>/dev/null
  [ -n "${PROTO:-}" ] && rm -f "$PROTO"
  return 0
}
trap aufraeumen EXIT INT TERM

echo "── 2/3  Server starten"
( cd "$WEB" && exec caffeinate -s npx next start -p "$PORT" ) &
SERVER=$!

for _ in $(seq 1 60); do
  curl -sf -o /dev/null "http://127.0.0.1:$PORT/api/health" && break
  sleep 1
done

echo "── 3/3  Tunnel oeffnen"
PROTO=$(mktemp)   # vom Trap oben aufgeraeumt
cloudflared tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate >"$PROTO" 2>&1 &
TUNNEL=$!

ADRESSE=""
for _ in $(seq 1 45); do
  ADRESSE=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$PROTO" | head -1)
  [ -n "$ADRESSE" ] && break
  sleep 1
done

if [ -z "$ADRESSE" ]; then
  echo "⛔ Keine Tunnel-Adresse erhalten. Protokoll:"; tail -20 "$PROTO"; exit 1
fi

echo
echo "════════════════════════════════════════════════════════════════════════"
echo "  Auf dem iPad oeffnen — EINMAL mit dem Schluessel, danach traegt ein Cookie:"
echo
echo "    $ADRESSE/?preview=$SCHLUESSEL"
echo
echo "  Die Sales-Seite direkt:"
echo "    $ADRESSE/t/017d72c50939b898?preview=$SCHLUESSEL"
echo
echo "  ⚠ Die Adresse gilt nur, solange dieses Fenster offen ist. Neustart = neue"
echo "     Adresse. Also erst kurz vor dem Termin starten und laufen lassen."
echo "  ⚠ Ohne den Schluessel sieht jeder Fremde eine schwarze Seite. So gewollt."
echo "════════════════════════════════════════════════════════════════════════"
echo
echo "  Beenden mit Strg-C. Falls doch etwas haengenbleibt:"
echo "      pkill -f 'cloudflared tunnel --url'; lsof -ti tcp:$PORT | xargs kill"
wait $SERVER
