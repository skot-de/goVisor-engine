# Erstaufruf: 12 Sekunden — und der Grund ist ein anderer als gedacht

## Teil (a): Ladezustand — ERLEDIGT am 2026-09-17

Nach der Anmeldung stand „0 von 0" auf dem Schirm, darunter „Keine Leads mit diesen
Filtern. Passe die Filter an oder wechsle den Grundraum." Beides sind Aussagen ueber die
DATEN; waehrend des Ladens sind beide falsch, und die zweite schickt den Nutzer aktiv in
die Irre.

Der Zustand `loading` existierte bereits in `ExplorerShell.tsx` und wurde von NIEMANDEM
gelesen — gesetzt, gepflegt, nie benutzt. Vierter Fall „gebaut, nicht verdrahtet" an
diesem Tag.

Jetzt gibt es den dritten Zustand neben „leer" und „gefuellt".

## Teil (b): Die Nutzlast — DIE ANNAHME WAR FALSCH

Der urspruengliche Auftrag lautete: „49,6 MB im Erstaufruf, erreichbar sind rund 25,5 MB,
wenn Felder erst beim Oeffnen nachgeladen werden." Beide Zahlen sind gemessen worden und
beide fuehren in die Irre.

### Was die Liste wirklich braucht

Gemessen ueber `leads-bau.json` (18.511 Leads, 31,2 MB Feldinhalt):

    beschreibung  6,2 MB   gebraucht — die Volltextsuche laeuft darueber
    anf           4,4 MB   gebraucht — `aufwandStufe` fuellt die Spalte „Aufwand"
    unterlagen    2,4 MB   gebraucht — Filter „nur mit Link"
    lose          2,1 MB   gebraucht — seit 2026-09-17 auch fuer die Suche
    incumbent     1,8 MB   gebraucht — Spalte „Wettbewerb"
    konk          1,5 MB   gebraucht — Spalte „Konkurrenz"

Nur im Detail gebraucht: **2,8 MB von 31,2 MB (9 %)** — und bei genauem Hinsehen weniger,
denn `cpvLabel`/`cpvLabelEn`/`cpvLabelFr` schienen nur deshalb entbehrlich, weil sie ueber
eine Hilfsfunktion gelesen werden. Die 25,5 MB sind nicht erreichbar.

`detail-<branche>.json` (43,4 MB) traegt bereits ausschliesslich Detailfelder
(`buyerProfile`, `marktSegment`, `sprachfassungen`) und dupliziert nichts. Diese Trennung
ist schon passiert; eine zweite gibt es nicht zu holen.

### Wo die Zeit wirklich hingeht

    Server: JSON.parse + JSON.stringify (Zuschlags-Mischung)    220 ms
    Uebertragung: 5,6 MB gzip  ← der ganze Rest
    Client: JSON.parse                                          130 ms
    Client: matchLead ueber 18.511 Leads                          18 ms

⚠ **Die 47 MB gehen nie ueber die Leitung.** Der Server gzippt auf 5,6 MB (12 %). Die
Zahl „49,6 MB" war die ROHE Groesse. In einem Cafe ueber einen Tunnel sind 5,6 MB
trotzdem der dominierende Posten — dort entstanden die zwoelf Sekunden.

### Der Hebel, der wirklich existiert: Brotli

Der Server liefert NUR gzip, auch wenn der Client `br` anbietet (gemessen: die Antwort
traegt `Content-Encoding: gzip` selbst bei `Accept-Encoding: br, gzip`). Next.js'
eingebaute Komprimierung kann kein Brotli.

    Ausgang    47,3 MB roh   →   gzip 5,65 MB

    Brotli q=1    5,61 MB    -1 %        62 ms
    Brotli q=4    3,79 MB   -33 %       105 ms
    Brotli q=5    3,53 MB   -38 %       217 ms
    Brotli q=9    3,20 MB   -43 %       519 ms
    Brotli q=11   2,96 MB   -48 %    34.642 ms   ← nur vorberechnet

Die Daten aendern sich einmal taeglich. **Vorberechnen mit q=11 ist die richtige Antwort:**
2,96 MB statt 5,65 MB, also 48 % weniger Uebertragung bei null Rechenzeit je Anfrage.

## Aufgabe

1. `scripts/export_web_leads.py` (oder ein Nachschritt) schreibt je Datei eine
   `.br`-Fassung mit Qualitaet 11.
2. `/api/leads` liefert bei `Accept-Encoding: br` die vorkomprimierten Bytes mit
   `Content-Encoding: br`, sonst den bisherigen Weg.
3. Dasselbe fuer die anderen grossen Auslieferungen (`suppliers.json`, `detail-*.json`).

### ⚠ WARUM DAS AM 2026-09-17 NICHT GEBAUT WURDE

Ich komme ohne Anmeldung nicht an `/api/leads` — die Route antwortet mit 401, und ein
Passwort fuer ein Konto habe ich nicht (s. `memory/govisor-frontend-gehoert-mir.md`).
Eine Komprimierungsaenderung an der wichtigsten Route ungeprueft auszuliefern, waere die
falsche Wette: setzt Next zusaetzlich seinen eigenen gzip darueber, ist die Antwort
doppelt kodiert und die Lead-Liste fuer JEDEN kaputt.

**Wer das baut, braucht zuerst einen Weg, die Route angemeldet abzurufen.** Danach ist
die Pruefung einfach: Antwort abrufen, dekomprimieren, mit der unkomprimierten Fassung
Byte fuer Byte vergleichen.

### ⚠ ZWEITE FRAGE VORHER KLAEREN

Vercel und Cloudflare komprimieren an der Kante selbst mit Brotli. Wenn dort ausgeliefert
wird, ist der Gewinn moeglicherweise schon da und diese Arbeit umsonst — die zwoelf
Sekunden entstanden ueber einen Quick Tunnel, nicht in Produktion. Erst messen, was die
Antwort in der echten Umgebung traegt, dann bauen.

## Abnahme
- Uebertragene Bytes vorher/nachher aus dem Netzwerkprotokoll, nicht geschaetzt.
- Ein Test, der die ausgelieferten Bytes dekomprimiert und gegen die Quelldatei haelt.
- Ein Test, der rot wird, wenn `Content-Encoding` und tatsaechliche Kodierung auseinanderfallen.
