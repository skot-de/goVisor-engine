#!/usr/bin/env bash
# Welche drei Dokument-Abrufer sind diese Runde dran?
#
# Liest die Tabelle von `rueckstau.py --rueckstand` auf der Standardeingabe
# (`kurzname \t erwartete Ausbeute \t roher Rueckstau`, absteigend) und schreibt die
# gewaehlten Namen, einen je Zeile.
#
#     scripts/rueckstau.py --rueckstand | scripts/waehle_abrufer.sh <rundennummer>
#
# ── DIE REGEL, UND WARUM SIE DREIMAL GEAENDERT WURDE ─────────────────────────────────
#
# Bis 21.08. reihum: `vergabeportal_at` mit NULL offenen Vergaben bekam dieselbe Stunde
# wie `cosinex` mit 1.737. Also ZWEI nach Rueckstau plus EINER aus der Rotation — denn
# rein nach Rueckstau kaeme immer dieselbe Spitze dran, und ein grosser Rueckstau heisst
# nicht, dass ein Abrufer liefert (`netserver` stand bei 1.327 und lief 46 Stunden ohne
# ein einziges Paket).
#
# ⚠ Am 22.08. kam eine Untergrenze dazu, weil der dritte Platz an `aumass` mit EINEM
# offenen Vorgang ging: nur noch Abrufer mit >= 50 im Rueckstau.
#
# ⚠ UND GENAU DIESE UNTERGRENZE HAT DIE ROTATION AM 2026-09-10 EINGEFROREN. Es lagen
# exakt drei Abrufer ueber 50 (cosinex 2.007 · subreport 812 · netserver 461). Damit hatte
# die Liste drei Eintraege, und `2 + (RUNDE-1) % (3-2)` ist **immer 2** — der dritte Platz
# stand fest auf netserver. Gemessen an einem Tag: 143 Runden, davon netserver 140,
# evergabe 3, die uebrigen acht **null**. Ihre zusammen 182 erreichbaren Vorgaenge kamen
# nie dran, waehrend die drei oben in fast jeder Runde „0 offen" meldeten.
#
# Deshalb jetzt ZWEI Listen statt einer: die Plaetze 1 und 2 gehen an die grossen
# (>= ABRUF_MINDEST), der dritte rotiert durch alle, bei denen sich eine Stunde noch lohnt
# (>= ABRUF_MINDEST_KLEIN) — abzueglich der beiden schon gewaehlten. Die Lehre vom 22.08.
# bleibt damit gewahrt, die vom 10.09. auch.
set -u

RUNDE="${1:?Rundennummer angeben}"
MINDEST="${ABRUF_MINDEST:-50}"
MINDEST_KLEIN="${ABRUF_MINDEST_KLEIN:-10}"

TABELLE="$(cat)"

# ⚠ Spalte 3 (roher Rueckstau), nicht Spalte 2: die zweite ist die ERWARTETE Ausbeute
# (Rueckstau x Trefferquote). Eine Untergrenze soll fragen „gibt es genug zu holen", nicht
# „glauben wir daran" — sonst sperrt eine schlechte Historie einen Abrufer dauerhaft aus.
gefiltert() {
  printf '%s\n' "$TABELLE" | awk -F'\t' -v m="$1" 'NF >= 3 && $3 + 0 >= m {print $1}'
}

GROSS="$(gefiltert "$MINDEST")"
POOL="$(gefiltert "$MINDEST_KLEIN")"

# Reicht es nicht fuer zwei grosse, ruecken die kleineren nach — sonst steht der Schritt
# still, sobald der Rueckstau abgearbeitet ist.
[ "$(printf '%s\n' "$GROSS" | grep -c .)" -lt 2 ] && GROSS="$POOL"

# Gar nichts messbar (Datei fehlt, Abfrage kaputt): feste Reihenfolge, damit der Arbeiter
# nicht stehen bleibt.
if [ -z "$(printf '%s\n' "$GROSS" | tr -d '[:space:]')" ]; then
  GROSS="evergabe_online cosinex subreport netserver ausschreibungsblatt healyhudson
         staatsanzeiger vergabeportal_at aumass bimedien evergabe simap_docs"
  POOL="$GROSS"
fi

# shellcheck disable=SC2206
SORTIERT=($GROSS)
# shellcheck disable=SC2206
ALLE=($POOL)

DRAN=("${SORTIERT[0]}")
[ ${#SORTIERT[@]} -gt 1 ] && DRAN+=("${SORTIERT[1]}")

# Der dritte Platz: alle mit lohnendem Rueckstau, ohne die beiden schon gewaehlten.
REST=()
for X in "${ALLE[@]}"; do
  case " ${DRAN[*]} " in *" $X "*) continue ;; esac
  REST+=("$X")
done
# ⚠ `RUNDE - 1`, nicht `RUNDE`: sonst faengt die Rotation nicht beim naechstbesten an,
# sondern beim zweitnaechsten — Rang 3 kaeme erst ganz am Ende dran.
if [ ${#REST[@]} -gt 0 ]; then
  DRAN+=("${REST[$(( (RUNDE - 1) % ${#REST[@]} ))]}")
fi

printf '%s\n' "${DRAN[@]}"
