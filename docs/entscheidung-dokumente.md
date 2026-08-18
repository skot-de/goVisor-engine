# Vergabeunterlagen: intern verwerten, nicht weitergeben

**Entschieden am 2026-08-18 von Sven.** Gilt bis jemand sie ausdrücklich revidiert.

## Die Entscheidung in einem Satz

Wir laden Vergabeunterlagen herunter, werten sie aus und spielen **die gewonnenen
Informationen** im Lead-Detail aus. Das Originaldokument wird **nicht zum Download
angeboten**, aber **aufbewahrt**.

Svens Formulierung: *„wir laden die dokumente intern runter, verwerten sie, spielen die
informationen aus den dokumenten in den details aus, das original dokument wird nur
genutzt, aber nicht zum download angeboten. das dokument an sich will ich aber behalten,
falls fehler/probleme auftreten und um den vergabebereich später besser zu machen mit
mustererkennung aus alten dokumenten."*

## Warum nicht zum Download

**Der stärkste Grund ist Produktsicherheit, nicht Recht.** Vergabeunterlagen werden
nachträglich geändert — Bieterfragen, Korrekturen, Nachträge. Wer auf unseren Stand bietet
statt auf den des Portals, bietet womöglich auf ein überholtes Leistungsverzeichnis. Das
kostet ihn das Angebot, nicht uns.

Zum Portal muss der Bieter ohnehin: dort registriert er sich, dort reicht er ein. Eine
Kopie bei uns spart ihm keinen Schritt und fügt eine Fehlerquelle hinzu.

Dazu kommen drei Gründe, die alleine nicht getragen hätten:

* **Rechtlich unnötiger Streit.** Die Archive stammen von Vergabeportalen, teils hinter
  Registrierung. Fakten aus ihnen zu extrahieren ist etwas anderes als sie weiterzugeben.
* **Es skaliert EU-weit.** Weitergaberechte für dutzende Portale in dutzenden Ländern
  bekommen wir nie. Auslesen funktioniert überall.
* **125 GB entfallen als Deploy-Problem.** Kein Objektspeicher, kein Egress. Die
  Ableitungen sind Megabytes.

## Warum aufbewahren

Zwei Zwecke, beide von Sven benannt:

1. **Fehlerprüfung.** Wenn wir behaupten „Präqualifikation nötig" und jemand widerspricht,
   müssen wir gegen das Original prüfen können. Ohne Aufbewahrung ist jede Aussage
   unwiderlegbar — und damit wertlos.
2. **Mustererkennung.** Alte Unterlagen sind das Trainingsmaterial, mit dem der
   Vergabebereich besser wird. Was heute eine Handregel ist, kann daraus ein Modell werden.

**Diese Zwecke gehören hierher geschrieben, weil sich sonst in zwei Jahren niemand mehr
erinnert, warum 125 GB herumliegen — und jemand räumt auf.**

## Was das dem Produkt auferlegt

Die Last verschiebt sich von *hosten* zu *richtig sein*. Wenn wir sagen „Bindefrist 90
Tage" und es stimmt nicht, verliert jemand ein Angebot. Das ist ein höheres Risiko, als ein
PDF zu zeigen.

Die Antwort darauf ist bereits gebaut und muss so bleiben — `govisor/docextract.py`:

> jede Aussage der Stufen *Zitat*/*Extrahiert* muss ein **wörtliches, im Quelltext
> verifizierbares Zitat** tragen (§6a.2, Belegpflicht) — sonst wird der Eintrag verworfen.

**Die Regel, die diesen Weg tragfähig macht: wir zeigen nicht das Dokument, aber wir zeigen
den Satz, auf den wir uns stützen.** Der Nutzer kann jede Aussage gegen das Original prüfen,
ohne dass wir das Original verteilen.

Gemessen am 2026-08-18 tragen **11.783 von 15.662 Aussagen (75 %)** ein wörtliches Zitat;
10.460 sind als `Zitat` markiert, 2.138 als `Extrahiert`.

## Wie es technisch läuft

```
data/docs/DE/                    4.711 ZIPs, 125 GB, nur lokal
  → index-docs                   Text auslesen        → doc_text.parquet
  → export_doc_text.py           ins Frontend         → web/data/doc-text.json
  → signals-docs                 Anforderungs-Signale → doc-signals.json
  → analyze_docs.py              LLM + Belegpflicht   → doc-analysis.json
  → /api/lead-detail             lbText, lbSignals, lbAnalyse
  → explorerCore.js:870          <div class="quote">…
```

`/api/lead/dokumente` listet auf, **was** in einem Archiv steckt (Namen, Typen, Grössen) und
liefert dabei JSON, keinen Dateiinhalt. Es gibt bewusst keinen Download-Endpunkt.

Auf einem Deployment ohne `data/docs` liefert diese Route eine **leere Liste mit Begründung**
— ehrlich leer, nicht kaputt.

## Offene Punkte, die diese Entscheidung nicht löst

* **Kein Backup.** Die 125 GB liegen auf einer externen Platte an dieser einen Maschine.
  Stirbt sie, ist der Rohbestand weg — und mit ihm genau die Möglichkeit, eine falsche
  Aussage gegen das Original zu prüfen. Sven am 2026-08-18: beim Go-live wandern die Daten
  zu einem Hoster, lokal bleibt das Backup. **Bis dahin gibt es keins.**
* **Durchsatz, nicht Verdrahtung.** Die Kette ist vollständig; sie ist ausgehungert.
  Gemessener Trichter über die offenen Leads:

  | Stufe | Vorgänge | Anteil |
  |---|---:|---:|
  | offene Leads | 16.096 | |
  | mit Unterlagen-Link | 12.547 | 78 % |
  | ZIP geholt | 4.259 | 34 % |
  | Signale ausgelesen | 3.974 | 93 % |
  | Volltext im Frontend | 14 | 0,1 % |
  | LLM-Analyse | 239 | 1,5 % |

  Dagegen läuft seit dem 2026-08-18 `scripts/dokumente_arbeiter.sh` als launchd-Dauerläufer.
* **AT/CH haben null Dokumente.** Der Abrufer deckt nur deutsche Portalfamilien ab. Nach der
  EU-weit-Regel in `CLAUDE.md` ist das ein offener Punkt, kein erledigter.
