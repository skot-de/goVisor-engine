# Vorführung am Donnerstag, 17.09.2026 — Ablauf

Für eine Investorendemo auf dem iPad, über einen Cloudflare-Tunnel vom Mac mini.
Gesprächspartner kennt Hamm; gezeigt wird **H. Klostermann Baugesellschaft mbH**.

⚠ **Was NICHT geprüft ist:** der Live-Registrierungsweg. Er hängt an einer Supabase-
Einstellung, die erst am Termintag gesetzt wird (Schritt 1) — bis dahin lässt sich nicht
messen, ob er durchläuft. Alles andere in diesem Papier ist einmal durchlaufen worden.

## 1 · Vorher (einmalig, dauert zehn Minuten)

**a) Bestätigungspflicht aus.** Ohne das scheitert die Live-Registrierung: Supabase
verweigert ohne eigenen SMTP-Server jede Zustellung an fremde Adressen
(„Email address not authorized"), und der Registrierungsaufruf schlägt fehl — nicht nur
die Mail.

    supabase.com/dashboard/project/tegznbkbvbbbgzhsvoza/auth/providers
    → Email → Bestätigungspflicht ausschalten

⚠ **Nach der Demo wieder einschalten.** Solange sie aus ist, kann sich jeder mit einer
fremden Adresse registrieren, ohne sie zu besitzen.

**b) Vorschau-Schlüssel tauschen.** In `web/.env.local` steht `PREVIEW_KEY=lokal-dev` —
acht Zeichen, raterbar, gedacht für lokal. Über einen öffentlichen Tunnel ist er das
einzige Schloss vor der App. Ersetzen durch etwas Zufälliges:

    python3 -c "import secrets; print('PREVIEW_KEY=' + secrets.token_urlsafe(18))"

## 2 · Start (kurz vor dem Termin, nicht früher)

    scripts/demo_tunnel.sh

Baut den Produktionsstand, startet den Server, öffnet den Tunnel und druckt die Adresse
samt Schlüssel. ⚠ **Fenster offen lassen** — die Adresse gilt nur, solange das Skript
läuft, und ein Neustart vergibt eine neue.

Der Mac wird per `caffeinate` wach gehalten, solange das Skript läuft. Er steht sonst auf
„Ruhezustand nach 1 Minute", und ein schlafender Mac heisst: Tunnel tot.

**Auf dem iPad einmal mit Schlüssel öffnen**, danach trägt ein Cookie. Ohne Schlüssel
sieht jeder Fremde eine leere schwarze Seite — so gewollt.

## 3 · Der Weg

| | Was | Konto nötig |
|---|---|---|
| 1 | `/t/017d72c50939b898` — „Für euch haben wir das schon gemacht" | nein |
| 2 | Kernaussage: **99 % der Aufträge von zwei Auftraggebern** (DB Netz, DB Station&Service), gezählt über 507 Zuschläge | nein |
| 3 | Fünf offene Ausschreibungen bei Verkehrsbetrieben, **alle mit laufender Frist** | nein |
| 4 | Weiter ins Onboarding, Firma suchen: **507 Zuschläge, 6 Auftraggeber, seit 2010** erscheinen, bevor ein Konto existiert | nein |
| 5 | Registrieren mit **info@klostermann-hamm.de** → Beleg wird grün | wird angelegt |
| 6 | Explorer: ~300 von 19.000 Vorgängen auf das Profil gefiltert, Relevanz-Werte | ja |
| 7 | Ein Vorgang mit voller Dokumentanalyse öffnen | ja |

⚠ **Die Adresse muss `info@…` sein, nicht `demo@…`.** `demo@klostermann-hamm.de`
existiert seit dem 11.09. als vorbereitetes Konto; eine erneute Registrierung damit
scheitert mit „User already registered" — vor Publikum. Der Beleg funktioniert für jede
Adresse der Domain, weil der Landing-Token ihn trägt (gemessen).

## 4 · Wenn etwas hakt

**Registrierung scheitert** → auf das vorbereitete Konto wechseln. Vorher einen Link
erzeugen, er gilt eine Stunde und genau einmal:

    python3 scripts/demo_konto.py --firma "H. Klostermann Baugesellschaft mbH" \
                                  --email demo@klostermann-hamm.de

**Netz bricht weg** → Schritte 1–4 laufen ohne Supabase und überstehen einen Aussetzer.
Ab Schritt 5 prüft die App das Anmelde-Token bei **jeder** Seitenanfrage gegen Supabase;
reisst das Netz, landet man auf der Anmeldemaske. Notausgang: bei Schritt 4 aufhören —
„eure Firma, bevor ihr überhaupt ein Konto habt" trägt für sich.

**Tunnel bleibt hängen** → `pkill -f 'cloudflared tunnel --url'; lsof -ti tcp:3000 | xargs kill`

## 5 · Was die Zahlen aushalten

Sie sind gemessen, nicht gerundet — ein Investor, der nachfragt, bekommt eine Antwort:

* **507 Zuschläge** für Klostermann stammen aus der Lieferantenbasis, dieselbe Quelle, die
  das Onboarding durchsucht. Die Schreibvariante ohne Leerzeichen (107) ist darin
  **enthalten**, nicht daneben.
* **178 Vorgänge** im Demo-Datensatz haben alle sieben Analyse-Blöcke gefüllt (belegte
  Zitate, K.-o.-Kriterien, Eignung, Zuschlag, Fristen, LV-Positionen, Aufwand) — von
  10.431 Analysen insgesamt. Die Liste zeigt bewusst auch gewöhnliche Vorgänge: eine
  Trefferliste, in der jeder Vorgang vollständig ausgewertet ist, wäre eine Behauptung.
* **Der Spitzenvorgang** trägt 122 belegte Zitate, 19 K.-o.-Kriterien, 35
  Eignungsnachweise und 40 Zuschlagskriterien.
* Was **nicht** stimmt, wenn jemand nachbohrt: die Entity-Auflösung trennt dieselbe Firma
  noch über Schreibvarianten hinweg (`Bauges.` gegen `Baugesellschaft`, ARGE-Formen). Das
  ist bekannt, gemessen und bewusst nicht automatisch behoben — die naheliegende Regel
  zöge 25.250 Zuschläge in einen Klumpen. Siehe `scripts/pruefe_entity_dubletten.py`.
