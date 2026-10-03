# Portal-Accessibility-Map — Ausschreibungsdokumente DACH

**Stand der Sondierung 2026-07-29, nachgemessen am 2026-10-04 (siehe unten).** Gemessen an **11.705 offenen DE-Leads** mit `documents_url` (96 % der offenen
Leads). Ziel: **wo kommen wir ohne Accounts an die Vergabeunterlagen, wo braucht es Login** — damit
Accounts nur dort angelegt werden, wo sie wirklich etwas freischalten.

## Kernbefund

Die `documents_url` ist nie eine direkte Datei, sondern eine **Portal-Landingpage**. Die eigentlichen
Dateien liegen hinter portal-spezifischer Navigation. **Entscheidend:** die 146 Domains laufen auf nur
**~8 Software-Engines** — der Zugangsmodus ist **je Engine** gleich (ein DTVP-Muster gilt für dtvp.de,
brandenburg, niedersachsen, nrw, autobahn… gleichermaßen). Rechtlicher Hebel: **§41 VgV** verlangt für
**oberschwellige** Vergaben *freien, unentgeltlichen, uneingeschränkten, direkten* Zugang zu den
Unterlagen — deshalb erlauben die großen Engines den Download oberschwellig **ohne Registrierung**.

---

## ⚠ NACHGEMESSEN 2026-10-04 — die Kernaussage unten war überholt

**Der alte Schluss „realistischer Bulk-Automat ~32 % (nur cosinex)" gilt nicht mehr. Gemessen
sind 65 %.** Die Messung vom Juli war eine *Sondierung*: jemand hat die Portale angesehen und
geschätzt, was ginge. Inzwischen gibt es zehn Abrufer, die es seit Wochen tun, und ihre
Manifeste (`data/docs/<Land>/_manifest_*.parquet`) sagen, was wirklich herauskommt. **Eine
Sondierung schätzt, ein Manifest zählt.** Beides stand zwei Monate nebeneinander, und die
Schätzung war die pessimistischere.

Zwei Engines, die der Juli-Stand als praktisch unerreichbar führte, liefern heute zuverlässig:

| Engine | Juli-Urteil | gemessen 2026-10-04 |
|---|---|---|
| **Bund e-Vergabe** | „Wicket-stateful, Download-Link → 403, nur per Browser" | **2.464 von 2.588 geholt (95,2 %)** |
| **AI evergabe.de** | „418 Anti-Bot, nur per Browser" | **1.731 von 1.899 geholt (91,2 %)** |
| **bi-medien / ibau** | „kommerzieller Aggregator 🔴 Abo" | **289 von 290 geholt (99,7 %)** |

Die drei Zeilen mit „zu verifizieren" (Staatsanzeiger, AUMASS, Deutsches Ausschreibungsblatt)
sind ebenfalls erledigt — für alle drei existiert seit Wochen ein Abrufer, und die Karte hat es
nicht mitbekommen. **Ein Dokument, das einen Bauzustand beschreibt, altert gegen den Code, nicht
gegen die Zeit.**

### Die Lage heute, gemessen

Verteilung über **12.766 offene DE-Vergaben mit Unterlagen-Link** (`lead_export`, phase open/planned,
2026-10-04; während eines laufenden Gold-Neubaus gelesen, also auf ±1 Tag genau). Erfolgsquote je
Engine aus dem jeweiligen Abruf-Manifest über den gesamten bisherigen Bestand.

| Engine | Anteil offen | Abrufe | geholt | Quote | wirksam |
|---|---:|---:|---:|---:|---:|
| **cosinex / DTVP** | 35,1 % | 8.656 | 7.490 | 86,5 % | 30,4 % |
| **Healy-Hudson + NetServer** | 13,4 % | 5.592 | 4.138 | 74,0 % | 9,9 % |
| **AI evergabe.de** | 13,3 % | 1.899 | 1.731 | 91,2 % | 12,1 % |
| **Bund e-Vergabe** | 7,7 % | 2.588 | 2.464 | 95,2 % | 7,3 % |
| **Staatsanzeiger / vergabe24** | 3,5 % | 457 | 282 | 61,7 % | 2,2 % |
| **AUMASS** | 1,5 % | 559 | 354 | 63,3 % | 0,9 % |
| **Dt. Ausschreibungsblatt** | 1,4 % | 513 | 505 | 98,4 % | 1,4 % |
| **bi-medien / ibau** | 0,9 % | 290 | 289 | 99,7 % | 0,9 % |
| subreport ELViS | 6,4 % | 2.328 | **0 Dateien** | 0 % | 0 % |
| RIB meinauftrag | 5,3 % | **kein Abrufer** | — | — | 0 % |
| xvergabe | 0,1 % | gesperrt (`hosts_gesperrt.csv`) | — | — | 0 % |
| sonstige | 11,5 % | ungemessen | — | — | **offen** |
| | | | | **Summe** | **65,1 %** |

**65 % statt 32 %.** Dazu kommen von subreport 2.089 öffentliche Dateilisten: keine Dateien, aber
die Namen, und die beantworten, ob ein Leistungsverzeichnis existiert und welche Nachweise
verlangt werden.

### ⚠ Was dabei aufgefallen ist und offen bleibt

1. **RIB meinauftrag hat keinen Abrufer.** 5,3 % der offenen Vergaben, 675 Stück, nie versucht.
   Die Karte führte sie als „Login-Wand"; ob das stimmt, ist seit Juli nicht nachgeprüft — und
   genau dieselbe Annahme hat sich bei NetServer, Bund, AI und bi-medien als falsch erwiesen.
2. **Healy-Hudson meldet bei 938 von 1.599 Vorgängen „kein Downloadbereich" (58,7 %).** Das ist
   exakt das Muster, vor dem der Nachtrag vom 2026-08-24 weiter unten warnt: „kein Download-Knopf
   gefunden" ist ein Befund über unseren Blick, nicht über das Portal. Bei had.de und xvergabe.de
   war es jedes Mal ein zweiter Rahmen oder ein anderes Servlet. Arbeitsliste, kein Ergebnis.
3. **Staatsanzeiger meldet 79-mal `frameset` (17 %).** Dieselbe Krankheit, derselbe Verdacht.
4. **11,5 % „sonstige" sind nie vermessen worden.** 1.469 offene Vergaben auf dem
   146-Domain-Schwanz. Der größte unbearbeitete Block nach cosinex.

### ⚠ AT und CH: nicht unversucht, sondern strukturell zu

Hier stand bisher nichts, und im Produkt sah es aus wie eine Lücke aus Nachlässigkeit. Gemessen:

| Land | Abrufe | geholt | Status |
|---|---:|---:|---|
| **AT** (vergabeportal) | 536 | **0 Dateien** | 500 „nur_liste", 36 Fehler |
| **CH** (simap) | 2.815 | **0 Dateien** | **2.815-mal „interesse_noetig"** |
| LU | 126 | 125 (99,2 %) | läuft |

**In der Schweiz verlangt simap.ch ausnahmslos eine Interessensbekundung**, bevor die Unterlagen
erscheinen. Das ist eine Anmeldewand mit anderem Namen, und sie trifft 100 % des Bestands. In
Österreich liefert das Portal die Liste, aber keine Dateien. Beides heißt: **die 0 % Dokumente in
AT und CH sind kein vergessener Abrufer, sondern ein gemessenes Nein.** Wer dort Unterlagen will,
braucht einen anderen Weg als einen Abrufer — das gehört als Entscheidung auf den Tisch, nicht als
Baustelle in eine Liste.

---

## Die Map vom 2026-07-29 (historisch, siehe oben)

| Engine | Anteil | Zugang (oberschwellig) | Für uns |
|---|---:|---|---|
| **cosinex/DTVP** (`/Satellite/`) | 31,9 % | **ohne Registrierung** — „Alle Dokumente als ZIP" | ✅ ohne Account holbar |
| **Bund e-Vergabe** (evergabe-online.de) | 8,8 % | **ohne Registrierung** — freier Download (Beschaffungsamt BMI); rund 2 % hält die Vergabestelle aus Vertraulichkeit zurück | ✅ ohne Account holbar |
| **AI evergabe.de** (`/unterlagen/`) | 7,2 % | **ohne Registrierung** — Deeplink-Download | ✅ ohne Account holbar |
| **AI evergabe.bieter** (`evergabe.bieter/`) | 4,3 % | **ohne Registrierung** (gleiche AI-Plattform) | ✅ ohne Account holbar |
| **Healy-Hudson / NetServer** (`/NetServer/`) | 13,3 % | **ohne Registrierung** — Sammel-ZIP je Version (widerlegt 2026-08-24, s. u.) | ✅ ohne Account holbar |
| **subreport ELViS** | 7,3 % | **Registrierung** für die Dateien; die **Dateiliste mit Namen ist öffentlich** (gemessen 2026-08-14 und 2026-08-24) | 🟡 Login-Wand, aber Namen holbar |
| **RIB meinauftrag** | 6,9 % | **Registrierung nötig** — „Documents"-Bereich öffentlich leer | 🟡 Login-Wand |
| **Staatsanzeiger / vergabe24** | 3,6 % | zu verifizieren | ⚪ offen |
| **AUMASS** | 2,0 % | zu verifizieren | ⚪ offen |
| **Dt. Ausschreibungsblatt** | 1,5 % | zu verifizieren | ⚪ offen |
| **bi-medien / ibau** | 1,1 % | kommerzieller Aggregator | 🔴 Abo |
| **sonstige** (146-Domain-Schwanz, u. a. Kassen kkh/aok direkt) | 12,1 % | gemischt; Behörden-/Kassen-Direktseiten oft mit **direktem PDF** | ⚪ gemischt |

## Was das praktisch heißt

| Tier | Anteil | Bedeutung |
|---|---:|---|
| **Skript-fetchbar** (cosinex/DTVP) | **≈ 32 %** | ✅ **validiert + gebaut** (`docfetch.py`): Archiv-ZIP-Endpoint, login-frei, curl-tauglich |
| **§41-frei, aber NICHT skript-fetchbar** (Bund + AI) | **≈ 20 %** | Bund = Apache-Wicket-Stateful (Download-Link → 403); AI evergabe.de = **418 Anti-Bot**; AI-bieter → Healy-Dashboard. Frei *im Prinzip*, technisch nur per **Browser-Automation** (brüchig, nicht bulk-tauglich, SSD-Schreiben mit Browser-Tools nicht sauber) |
| **Login-Wand** (subreport + RIB) | **≈ 14 %** | Registrierung nötig → **ich darf mich nicht einloggen** (Regelgrenze), egal welche Accounts. NetServer gehört seit 2026-08-24 nicht mehr dazu |
| **Zu verifizieren / gemischt** | **≈ 20 %** | Staatsanzeiger/AUMASS/Direktseiten — Rest der Sondierung |

**Korrektur (2026-07-29, gemessen):** Die frühere „≈ 52 % ohne Login"-Schätzung stützte sich auf
Recherche-Aussagen; die technische Sondierung zeigt, dass **nur cosinex (~32 %) sauber per Skript
holbar** ist. Bund/AI blockieren curl (Wicket-State bzw. 418) — ihr freier Zugang existiert nur im
Browser. Realistischer Bulk-Automat also **~32 %** (cosinex), nicht 52 %.

**Wichtige Klarstellung zur Account-Frage:** Accounts helfen **mir** nicht — ich darf mich auch mit
deinen Zugangsdaten nicht einloggen. Die Trennlinie ist also nicht „mit/ohne Account", sondern
**„braucht Login (ich nicht) vs. braucht keinen Login (ich ja)"**:

- **~52 % ohne Login** → **ich baue den Fetcher, du musst nichts tun.**
- **~28 % mit Login** → **du (oder ein credentialed Downloader) holst; ich verarbeite danach.**

## Nächste Schritte (Vorschlag)

1. **Fetcher für die login-freien Engines** (cosinex/DTVP zuerst — 32 % allein): den echten
   ZIP-Download-Endpoint je Engine reverse-engineeren (die `/notice/.../documents`-URL ist nur die
   Landingpage; der Download hängt an einem `/public/...`-Pfad bzw. der „ZIP"-Funktion). Dann PDFs/ZIPs
   auf die SSD (`data/docs/<land>/<notice_id>/…`), verknüpft mit dem Lead.
2. **Dokument-Pipeline** (engine-unabhängig): Text-Extraktion (PDF/ZIP/Office) → Volltext-Index →
   Analyse (Leistungsverzeichnis, Eignungskriterien). Läuft für login-freie UND später gelieferte Dateien.
3. **Login-Engines:** du lieferst die Dateien in einen SSD-Ordner; die Pipeline zieht sie mit ein.

## Caveats (ehrlich)

- **Login-frei ≠ trivial:** je Engine muss der echte Download-Pfad ermittelt werden (Cookies/Session
  nötig, die Landing-URL allein liefert 404/400). Das ist ~4-5 Engine-Fetcher, kein Universal-Skript.
- **Anti-Bot / Rate-Limits / ToS:** systematisches Herunterladen kann auch bei freiem Zugang gedrosselt
  oder per CAPTCHA blockiert werden. Fetcher **höflich** (Rate-Limit, robots.txt beachten); CAPTCHA
  darf ich nicht lösen → solche Fälle fallen in den „du lieferst"-Pfad.
- **Unterschwellig** (DÖE/atverg): §41 gilt nicht → dort ist Registrierung häufiger, auch bei den
  login-freien Engines. Die 52 % oben beziehen sich auf den oberschwelligen TED-Bestand.
- Zahlen sind DE (der aktuelle Bestand); AT/CH-Verteilung kommt nach dem laufenden Ingest dazu.

## Korrektur (2026-08-24, gemessen): NetServer war nie eine Login-Wand

Die Zeile oben behauptete „Registrierung nötig — keine öffentlichen Download-Buttons".
Gemessen am eigenen Bestand: **1.871 Abrufversuche, 1.494 erfolgreich (80 %), 31.442
Dateien, 57 GB, über 40 Hosts — sämtlich anonym.** Die ursprüngliche Sondierung hatte auf
der BEKANNTMACHUNG nachgesehen; der Unterlagen-Bereich hängt an einem anderen Servlet
(`TenderingProcedureDetails`, siehe `govisor/docfetch_netserver.py`).

Zwei Nachbeben derselben Ursache, beide am 2026-08-24 behoben:

- **had.de** ist nur eine Hülle; die Anwendung läuft im Kindrahmen auf `vergabe.had.de`.
  Wer die Seite abfragt, durchsucht das Menü. 188 Vorgänge galten als „hat keine
  Unterlagen"; die Stichprobe fand bei 21 von 25 welche.
- **xvergabe.de** fährt eine neuere Oberfläche mit anderen CSS-Klassen und einem
  Sammelknopf statt eines Modals. 32 Vorgänge galten als „keine Version gelistet",
  während die Seite die Dateien sichtbar auflistete.

**Die Lehre für jede weitere Zeile dieser Tabelle:** „kein Download-Knopf gefunden" ist ein
Befund über unseren Blick, nicht über das Portal. Erst wenn geklärt ist, WELCHE Seite man
angesehen hat und in welchem Rahmen, ist „Login-Wand" eine Aussage. Die Zeilen mit „zu
verifizieren" stehen bis heute unter diesem Vorbehalt.

## Nachtrag (2026-08-24, gemessen): subreport ist nicht eine Wand, sondern vier Zustände

Die Zeile stand mit „zu bestätigen". Bestätigt ist jetzt: die Vergabeunterlagen selbst
verlangen eine Anmeldung (gemessen 2026-08-14 über drei Vergaben und alle Knopfpositionen,
siehe `govisor/subreport.py`), die **Dateiliste mit Namen** ist dagegen öffentlich und
trägt Substanz — sie beantwortet, ob ein Leistungsverzeichnis existiert und welche
Nachweise verlangt werden.

Wo keine Liste erscheint, liegt es an einem von vier Zuständen, die das Portal in seiner
Statusspalte selbst nennt (Stichprobe 20 von 124):

| Zustand | Anteil | Konsequenz |
|---|---:|---|
| `Download` + „Already registered …" | ~45 % | blockiert, wartet auf ein Konto |
| „Validity expired" | ~15 % | dauerhaft, Fenster zu |
| „canceled" | ~20 % | dauerhaft, Vergabe aufgehoben |
| Passwortabfrage, beschränkte Vergabe | ~5 % | blockiert, Passwort geht an eingeladene Bieter |
| wirklich unerklärt | ~10 % | Arbeitsliste |

Vorher trugen alle 124 denselben Vermerk „0 Dateien" und liefen alle sieben Tage erneut.

## Nachtrag (2026-08-24, gemessen): die Ausnahme beim Bund hat einen Namen

95 % der Vorgänge auf evergabe-online.de liefern das ZIP anonym (1.097 von 1.152 Versuchen).
Die Ausnahme ist keine technische Hürde, sondern eine Entscheidung der Vergabestelle:

> „Aus Gründen der Vertraulichkeit sind die Vergabeunterlagen nicht frei zugänglich.
> Registrierte Nutzer der e-Vergabe können die Vergabeunterlagen im Bereich
> ‚Meine e-Vergabe‘ anfordern."

Das steht auf der VORGANGSSEITE. Die Unterlagenseite selbst quittiert diesen Fall mit
demselben Einheitssatz wie jeden anderen Fehler. Wer nur sie liest, hält 17 bewusst
zurückgehaltene Vergaben für 17 Vergaben ohne Unterlagen.
