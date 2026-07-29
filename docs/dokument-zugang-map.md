# Portal-Accessibility-Map — Ausschreibungsdokumente DACH

**Stand 2026-07-29.** Gemessen an **11.705 offenen DE-Leads** mit `documents_url` (96 % der offenen
Leads). Ziel: **wo kommen wir ohne Accounts an die Vergabeunterlagen, wo braucht es Login** — damit
Accounts nur dort angelegt werden, wo sie wirklich etwas freischalten.

## Kernbefund

Die `documents_url` ist nie eine direkte Datei, sondern eine **Portal-Landingpage**. Die eigentlichen
Dateien liegen hinter portal-spezifischer Navigation. **Entscheidend:** die 146 Domains laufen auf nur
**~8 Software-Engines** — der Zugangsmodus ist **je Engine** gleich (ein DTVP-Muster gilt für dtvp.de,
brandenburg, niedersachsen, nrw, autobahn… gleichermaßen). Rechtlicher Hebel: **§41 VgV** verlangt für
**oberschwellige** Vergaben *freien, unentgeltlichen, uneingeschränkten, direkten* Zugang zu den
Unterlagen — deshalb erlauben die großen Engines den Download oberschwellig **ohne Registrierung**.

## Die Map (nach Engine, gewichtet nach offenen Leads)

| Engine | Anteil | Zugang (oberschwellig) | Für uns |
|---|---:|---|---|
| **cosinex/DTVP** (`/Satellite/`) | 31,9 % | **ohne Registrierung** — „Alle Dokumente als ZIP" | ✅ ohne Account holbar |
| **Bund e-Vergabe** (evergabe-online.de) | 8,8 % | **ohne Registrierung** — freier Download (Beschaffungsamt BMI) | ✅ ohne Account holbar |
| **AI evergabe.de** (`/unterlagen/`) | 7,2 % | **ohne Registrierung** — Deeplink-Download | ✅ ohne Account holbar |
| **AI evergabe.bieter** (`evergabe.bieter/`) | 4,3 % | **ohne Registrierung** (gleiche AI-Plattform) | ✅ ohne Account holbar |
| **Healy-Hudson / NetServer** (`/NetServer/`) | 13,3 % | **Registrierung nötig** — keine öffentlichen Download-Buttons | 🟡 Login-Wand |
| **subreport ELViS** | 7,3 % | (kostenlose) **Registrierung** üblich | 🟡 Login-Wand (zu bestätigen) |
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
| **Login-Wand** (NetServer + subreport + RIB) | **≈ 28 %** | Registrierung nötig → **ich darf mich nicht einloggen** (Regelgrenze), egal welche Accounts |
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
