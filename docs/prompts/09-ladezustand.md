# Erstaufruf: 12 Sekunden — und der Grund ist ein anderer als gedacht

## Teil (a): Ladezustand — ERLEDIGT 2026-09-17, VERVOLLSTAENDIGT 2026-09-18

Nach der Anmeldung stand „0 von 0" auf dem Schirm, darunter „Keine Leads mit diesen
Filtern. Passe die Filter an oder wechsle den Grundraum." Beides sind Aussagen ueber die
DATEN; waehrend des Ladens sind beide falsch, und die zweite schickt den Nutzer aktiv in
die Irre.

Der Zustand `loading` existierte bereits in `ExplorerShell.tsx` und wurde von NIEMANDEM
gelesen — gesetzt, gepflegt, nie benutzt. Vierter Fall „gebaut, nicht verdrahtet" an
diesem Tag.

⚠ **Die erste Fassung hatte nur ZWEI der vier Zustaende.** Der Auftrag verlangte drei
(*laedt*, *leer*, *gefiltert-leer*), und Falle 1 verlangte einen vierten: scheitert der
Abruf, muss die Anzeige das sagen — `ladeMitGrund` liefert dafuer `DATEN_STOERUNG`.

Genau das fehlte. Der Fehlerzweig setzte `setLoading(false)`, und die Liste sagte wieder
„Keine Leads mit diesen Filtern“: derselbe Fehler, eine Ursache weiter. Dazu kam, dass
`r.json()` auch auf eine 503-Antwort angewandt wurde; `Array.isArray` war dann falsch, und
uebrig blieb eine leere Liste ohne Begruendung.

Jetzt vier Zustaende, in dieser Reihenfolge — eine Stoerung WAEHREND des Ladens ist eine
Stoerung, keine Ladeanzeige, die nie endet:

    stoerung    Die Ausschreibungen konnten nicht geladen werden.
                Das liegt an uns, nicht an euren Filtern.
    laedt       Ausschreibungen werden geladen.
    gefiltert   Keine Leads mit diesen Filtern.  (nur wenn welche gesetzt sind)
    leer        In diesem Grundraum ist gerade nichts offen.

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

### Wo die Zeit wirklich hingeht — KORRIGIERT am 2026-09-18

⚠ **Die Zahl „5,6 MB gzip" war keine Messung.** Sie stand als Kommentar in `/api/leads`
und beschrieb, was eine Komprimierung ERGEBEN WUERDE. Ich habe sie am 2026-09-17
weitergereicht, ohne sie zu pruefen — weil ich ohne Anmeldung nicht an die Route kam.

Mit angemeldeter Sitzung gemessen:

    /api/leads?branche=bau      46.044.875 Bytes   Content-Encoding: KEINE
    /api/plz-geo                 1.463.245 Bytes   Content-Encoding: KEINE
    /api/doc-analysis              649.499 Bytes   Content-Encoding: KEINE
    /_next/static/chunks/*.js        1.905 Bytes   Content-Encoding: gzip

`next start` komprimiert statische Dateien, aber KEINE Route-Handler-Antwort. Die 43,9 MB
gingen roh ueber die Leitung. Bei 30 Mbit/s sind das **12,3 Sekunden** — genau die Zeit,
die gemeldet wurde. Es war nie eine Brotli-gegen-gzip-Frage; es war gar keine
Komprimierung.

    Verfahren      Groesse   Rechenzeit   Ersparnis
    gzip level 6   5,56 MB      260 ms      -87 %
    brotli q=1     5,55 MB       66 ms      -87 %
    brotli q=4     3,76 MB      111 ms      -91 %   ← gewaehlt
    brotli q=5     3,51 MB      219 ms      -92 %

### BEHOBEN am 2026-09-18

`web/lib/komprimiert.ts` handelt br vor gzip aus, setzt `Vary: Accept-Encoding` und legt
das Ergebnis unter (ETag + Verfahren) ab. Verdrahtet in `/api/leads`, `/api/plz-geo`,
`/api/doc-analysis`. Gemessen an der laufenden Anwendung:

    /api/leads?branche=bau   46,0 → 3,9 MB   (-91 %)
    /api/plz-geo              1,40 → 0,46 MB (-67 %)
    /api/doc-analysis         0,62 → 0,10 MB (-84 %)

Der Waechter prueft nicht die Kopfzeile, sondern ENTPACKT und vergleicht Byte fuer Byte
gegen die unkomprimierte Fassung — eine gesetzte Kopfzeile ohne passenden Rumpf zeigt der
Browser als kaputte Seite, nicht als Fehler.

### Die Feldliste: was nach der Komprimierung wirklich kostet

⚠ **Der Auftrag rechnet in ROHEN Bytes, und das kehrt die Reihenfolge um.** Gemessen an
`leads-bau.json` (41,9 MB roh → 3,68 MB brotli), je Feld einzeln weggelassen:

    Feld            roh gespart   brotli gespart   Anteil an der Uebertragung
    beschreibung        6,2 MB         1,58 MB        42,9 %   <- der eigentliche Posten
    incumbent           2,0 MB         0,25 MB         6,7 %
    lose                2,1 MB         0,23 MB         6,4 %
    unterlagen          2,6 MB         0,23 MB         6,2 %
    cpvLabel*           2,2 MB         0,10 MB         2,7 %
    anf                 4,3 MB         0,09 MB         2,4 %

**`anf` ist entschieden: es bleibt.** Der Auftrag nennt es die eine echte Entscheidung mit
5 MB — auf der Leitung sind es 90 kB. Die Struktur ist hochgradig wiederholt und
komprimiert sich weg. Der Nutzer verliert nichts, weil nichts zu gewinnen ist; die
erklaerbare Passung (`matchLead.teile`) bleibt unangetastet.

**Die CPV-Labels bleiben ebenfalls, obwohl sie 17-fach redundant sind.** 3.051
verschiedene CPV-Codes tragen die Labels von 42.813 Leads; als Tabelle waeren es 298 kB
statt 4,3 MB. Nach Brotli sind es netto **139 kB** — fuer eine neue Route, einen zweiten
Abruf, einen Wettlauf beim ersten Rendern und eine Override-Mechanik (der Export faellt
auf `buyer_activity` zurueck, das Label ist also nicht garantiert CPV-rein; heute weicht
bei 42.813 Leads keiner ab, morgen vielleicht doch). Der Tausch lohnt nicht.

**Der einzige Posten, der traegt, ist `beschreibung`** — 42,9 % der Uebertragung, weil
Prosa je Lead einzigartig ist und sich nicht wegkomprimieren laesst. ⚠ Aber der Auftrag
nennt es „nur im Detail-Panel“, und das stimmt nicht: die VOLLTEXTSUCHE laeuft darueber
(`leadText` in `explorerCore.js`). Wer es weglaesst, nimmt der Liste die Suche.

Das ist die offene Frage, und sie ist eine Produktfrage: eine gekuerzte Fassung fuer die
Suche mitschicken (etwa die ersten 400 Zeichen) und den Rest dem Detail ueberlassen? Dann
findet die Suche weniger. Oder die Suche serverseitig? Dann kostet jeder Tastendruck eine
Anfrage. Beides ist zu messen, bevor es gebaut wird.

### Der Weg zur Anmeldung, der das ueberhaupt erst pruefbar machte

    python3 scripts/pruefkonto.py        legt `pruef@govisor.invalid` an (mailfrei)
    node web/scripts/pruefanmeldung.mjs  laesst `@supabase/ssr` selbst anmelden und
                                         gibt die Cookie-Zeile aus

⚠ Das Cookie-Format wird NICHT nachgebaut. `@supabase/ssr` kodiert base64-praefixiert und
zerlegt bei Bedarf auf mehrere Cookies; jede Nachbildung waere beim naechsten Update still
falsch. Das Skript faengt ab, was die echte Bibliothek setzt.

