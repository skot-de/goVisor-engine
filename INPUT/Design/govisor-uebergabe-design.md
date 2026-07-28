# goVisor — Übergabe an die Umsetzung

**Stand:** Prototyp `govisor-explorer-v4.4.html`, `govisor-onboarding-v1.3.html`
**Zweck:** Dieses Dokument hält die Entscheidungen fest, die man dem Prototyp **nicht ansieht** —
weil sie sich als Weglassungen, Zurückhaltung oder bewusste Grenzen zeigen statt als Funktionen.
Wer nur den Code liest, baut sie versehentlich weg.

---

## 1 · Der Markenkern in einem Satz

> Lieber unbekannt zeigen als falsch.

Alles Folgende ist eine Anwendung dieses Satzes. Wenn im Zweifel eine Regel mit einer
Bequemlichkeit kollidiert, gewinnt die Regel.

---

## 2 · Herkunfts-Grammatik — sechs Kategorien

Jeder angezeigte Wert trägt eine Herkunft. Die Kennzeichnung ist bewusst **asymmetrisch**:
Belegtes bekommt kein Zeichen (ruhiger Normalfall), nur Abweichungen werden markiert.

| Kategorie | Darstellung | Bedeutung |
|---|---|---|
| gemessen / belegt | **kein Zeichen** | aus der Quelle, unverändert |
| geschätzt | grauer Punkt | abgeleitet, mit Begründung im Tooltip |
| unsicher | amber Punkt | z. B. Entity nur über Namensähnlichkeit |
| unbekannt | grauer Text „nicht angegeben" | Quelle nennt nichts |
| **amtlich mit Stichtag** | Label „Stand 2023" **am Feld** | Destatis u. a. — belegt, aber nicht tagesaktuell |
| **von euch angegeben** | eigene Chip-Form, weiß mit Rand | Nutzer-Eingabe, **nicht überprüft** |

**Regeln:**
- Der Stichtag steht **am Feld**, nie in einer Fußzeile. Sonst wirken Zahlen von 2023
  so aktuell wie die Ausschreibungsdaten von heute.
- Es gibt eine siebte Variante, sobald `FieldsPrivacy` erschlossen ist: statt „unbekannt"
  dann **„Wert zurückgehalten — Grund: Geschäftsgeheimnis"**. Der Unterschied ist wichtig:
  wir wissen es nicht ⟷ es wurde bewusst nicht veröffentlicht.
- **Blur ≠ unbekannt.** Verwischt heißt „vorhanden, im Pro-Zugang". Grau heißt „wir haben es nicht".
  Diese beiden dürfen visuell nie verwechselbar sein, sonst hält ein Free-Nutzer die Ehrlichkeit
  für eine Verkaufsmasche.

### Herkunft gilt auch für abgeleitete Werte
Die Chance-Bewertung trägt einen Schätz-Punkt, wenn die Bieterzahl fehlt. Zwei Fälle:
- **offene Ausschreibungen (f02):** `num_tenders` zu 0 % gefüllt — es hat noch niemand geboten
  (~7.962 Leads)
- **UVgO / unterschwellig:** Bieterzahlen werden nicht veröffentlicht

Beide zeigen denselben Punkt mit unterschiedlicher Begründung. Ein Score, dessen wichtigste
Achse blind ist, darf nicht aussehen wie ein Score mit voller Information.

⚠️ **Prüffälle nötig.** Diese Kennzeichnungen sind Randfälle und fallen beim normalen
Durchklicken nicht auf. In dieser Sitzung war eine davon monatelang wirkungslos, ohne dass
es jemand merkte — die Bedingung passte zu keinem Demo-Lead.

---

## 3 · Datenblatt-Prinzip

**Leere Felder bleiben sichtbar.** Sie verschwinden nicht.

Begründung: gleiche Struktur = schneller scannbar, Export hat immer dieselben Spalten — und
der Nutzer sieht, **was die Vergabestelle nicht veröffentlicht hat.** Das ist selbst eine
Information.

Gilt für alle Faktenblöcke: Eckdaten, Zuschnitt, Fristen, Vergabestelle, Markt.
Gilt **nicht** für Abschnitte, die es fachlich nicht gibt (z. B. „Partner nötig?" ohne Lose).

---

## 4 · Erfolgsprämie — die härtesten Regeln

Die Prämie ist ein bindendes Geschäftsereignis. Entsprechend eng:

1. **Auslöser ist ausschließlich der Klick auf den Tab „Bewertung".**
   Nicht Übersicht, nicht Teilnahme, nicht Vergabestelle, nicht Markt, nicht Netzwerk.
   Der Tab-Name macht das selbsterklärend — der Zähler „1/3" hängt sichtbar daran.
2. **Nur auf gemessene Identität.** Entity-Match über Handelsregister oder nationale Kennung
   (~81 % der Siege). Bei reinem Namens-Match (~19 %) wird **nicht** abgerechnet.
3. **Niemals auf erklärte Profilangaben.** Was der Nutzer selbst einträgt (Schwerpunkte,
   Nachweise, Regionen) verbessert Relevanz und Anforderungs-Check — berührt aber die
   Abrechnung nie. Sonst könnte man Prämien durch Angaben steuern.
4. **Nur auf die geklickte Ausschreibung**, nicht auf Nachfolge-Verfahren. 12-Monats-Cutoff.
5. Der Bestätigungsklick im Onboarting („Ja, das sind wir") setzt `entity_confidence='confirmed'`
   und ist damit das eigentliche Gate. Der Nutzer muss beim Klicken verstehen, was er bestätigt —
   deshalb steht dort im Klartext, wozu die Bestätigung dient.

**Wichtig fürs UI:** Jeder Weg in die Bewertung muss seinen Preis nennen. Ein beiläufiger
Link, der still ein Drittel des Monatskontingents verbraucht, ist ein Vertrauensbruch.
Im Prototyp steht deshalb an solchen Verweisen „nutzt eine deiner drei Bewertungen".

---

## 5 · Preismodell — was frei ist und warum

| Bereich | Free | Begründung |
|---|---|---|
| Lead-Liste, Suche, Filter | ∞ | Kern-Nutzen, muss erlebbar sein |
| Übersicht, Teilnahme | ∞ | Fakten über die Ausschreibung |
| Bewertung | 3 / 30 Tage | das eigentliche Produkt |
| Vergabestelle, Markt | Struktur sichtbar, Werte verwischt | Alleinstellung, eigene Daten, kostet pro Abruf nichts → unbegrenzt in Pro |
| Potenzial → Chancen | Markt-Blöcke frei, Analyse verwischt | gefilterte Lead-Listen sind ohnehin frei |
| Potenzial → Position | Pro | reine Rechenleistung |
| Potenzial → Profil | frei | eigene Daten; gepflegte Profile nützen auch uns |
| **Netzwerk** | **Teilnahme frei**, 3 gleichzeitige Meldungen | s. u. |

### Netzwerk muss frei sein
Ein Netzwerk ist so viel wert wie seine Dichte. Würde man die Teilnahme hinter Pro legen,
vermarktet man ein Netzwerk, bevor es existiert. **Free-Nutzer sind für Pro-Kunden der Wert.**
Monetarisiert wird der Umfang (gleichzeitige Meldungen) und die Voraussicht (wie viele suchen
hier schon — *bevor* man sich selbst meldet), nicht der Zugang.

**Ausdrücklich verworfen:** Kontaktdaten hinter Pro. „Jemand will euch erreichen, zahlt um zu
erfahren wer" ist der meistgehasste Mechanismus vergleichbarer Plattformen — und ein Match,
bei dem nur eine Seite zahlen kann, ist kein Match.

### ⚠️ Blur ist keine Sicherheit
Im Prototyp sind verwischte Werte echte Platzhalter. **In der Umsetzung dürfen die echten
Werte niemals an einen Free-Client gesendet werden.** Struktur und Beschriftungen ja, Zahlen
serverseitig zurückhalten.

---

## 6 · Netzwerk — die Schutzregeln

Das ist der einzige Teil mit echtem Netzwerkeffekt und gleichzeitig der gefährlichste.

1. **Gematcht wird auf Fähigkeit, nie auf beobachtetes Verhalten.**
   Profil, Schwerpunkte, frühere Verträge, Größenklasse — ja.
   Merkliste, Klicks, geöffnete Leads, Bewertungen — **niemals**.
   Sonst verratet ihr Bietabsichten, und das erwartet niemand.
2. **Die Ergänzungs-Prüfung ist der Spionageschutz.** Wer sich meldet, um zu sehen wer sonst
   bietet, bekommt nichts: Ein Wettbewerber mit gleichem Profil ergänzt nicht, also kein Match,
   also keine Offenlegung. Diese Eigenschaft muss erhalten bleiben.
3. **Gegenseitigkeit.** Man sieht andere nur, wenn man selbst sichtbar ist. Löst den Kaltstart
   und ist ehrlich.
4. **Meldung gilt je Ausschreibung, nicht pauschal.**
5. **Beidseitige Freigabe** vor Offenlegung der Kontaktdaten. Firmenname bleibt bis dahin verdeckt.
6. **Kein Chat.** Moderation, Benachrichtigungen, Datenschutz — ein eigenes Produkt. Nach der
   Freigabe stehen Telefonnummer und E-Mail da, den Rest machen die beiden selbst.

---

## 7 · Bewusst verworfene Alternativen

Damit sie nicht versehentlich wieder eingesammelt werden:

| Verworfen | Grund |
|---|---|
| Verschachtelte Tabs (Tab im Tab) | zwei Navigationsebenen, Nutzer verliert die Orientierung |
| „Sonstiges"-Tab für Restfelder | Eingeständnis fehlender Sortierarbeit; wird nie geöffnet, wächst unbegrenzt. Stattdessen: Rohdatensatz eingeklappt am Ende, klar als Quelle gekennzeichnet |
| **Bestand als eigener Modus** | Median = **1 Sieg** je Firma. Ein Hauptmenüpunkt für eine Zeile ist unverhältnismäßig. Eigene Verträge stehen jetzt markiert in der normalen Liste |
| Globaler Angriff/Verteidigung-Umschalter | ersetzt durch **pro Lead**: bei eigenem Vertrag heißt die Chance „Verdrängungs-Risiko", die Treue-Quote dreht ihre Deutung. Ein Modus, den man umzustellen vergisst, ist schlechter als eine automatische Ableitung |
| Markt als eigener Bereich in der Leiste | Kaltstart-Problem („welche Region?"). Als Tab am Lead ist die Region immer der Leistungsort |
| Nutzer stellt sich KPI-Dashboard zusammen | Konfiguration ist ein Kosten-, kein Feature-Faktor. Fast niemand konfiguriert; man baut für die wenigen und verschlechtert den Standard. Stattdessen: Personalisierung ohne Konfiguration (Branche hebt „dein Feld" hervor, Sicht dreht die Deutung) |
| **Gewinnquote** | strukturell unmöglich — TED veröffentlicht Gewinner, nicht Verlierer. Nicht durch einen Proxy ersetzen, der so aussieht. Nächstbeste Annäherung: `CompanySizeCode` („bei dieser Stelle gewinnen zu 67 % KMU") |
| Anbieterdichte als Chancen-Argument | gemessen widerlegt (r = 0,099, über alle Quartile flach). Baufirmen arbeiten überregional |
| Marktanteil nach Wert | beide Seiten zu lückenhaft (65 % / 12–37 %). **Anteile immer nach Anzahl** |
| Nachfolge-Versprechen („das ist die Neuausschreibung eures Vertrags") | Kette nur ~35 % sicher. Verlässlich sagbar: „diese Stelle hat etwas Neues in eurem Feld" |

---

## 8 · Datengetriebene Design-Entscheidungen

Diese Zahlen haben das Layout bestimmt — wer sie nicht kennt, hält die Lösungen für Willkür.

| Befund | Folge im Design |
|---|---|
| Beschreibungstext: **Median 129 Zeichen, 61 % unter 200** | Der **kurze** Fall ist der Normalfall. Zweispaltiges Layout mit Begriffs-Extraktion nur für die ~33 % mit echtem Text. Leerzustand mit Erklärung, nicht Verschwinden |
| `lot_count > 1` bei nur **8,9 %** | Lose sind die Ausnahme. Kein eigener Tab dafür; „nicht teilbar — ganz oder gar nicht" ist die häufigere und ebenso wichtige Aussage |
| **60,6 % der Firmen haben genau 1 Sieg**, nur 13,4 % haben 5+ | Der Potenzial-Bereich muss **ohne Historie funktionieren**. Markt-Blöcke hängen nur an Branche × Region und sind immer gefüllt. Analyse-Blöcke erscheinen, wenn Daten da sind — sie fehlen nicht, sie kommen dazu |
| Legacy-Felder **100 %** vs. eForms **~45 %** | Für Aggregate je Vergabestelle (über die ganze Historie) Legacy nehmen, eForms nur für die feine Auflösung der letzten Jahre |
| Leistungsort ≠ Käufersitz bei **18,3 %** | Marktkontext hängt an `market_nuts3`, nie am Sitz. Gate auf `market_region_ok` (91 %) — lieber nichts als der falsche Markt |
| Wert-Abdeckung **65 %** (Vergaben), **12–37 %** (Regionen) | Volumen **immer als Untergrenze** mit Coverage-Prozent **an der Zahl**, nie in einer Fußnote |
| Entity: **81 % belegt, 19 % nur Name**, Fragmentierung 4,9 % | Bestand als **Vorschlag** darstellen, nicht als Wahrheit. Korrekturweg in beide Richtungen (+/−). Jede Ablehnung ist Trainingsmaterial für die Entity-Resolution |
| AUC **0,767** (Stand 2026-07-23, vorher 0,806) | Modellzahlen **driften**. Jede angezeigte Score-Zahl braucht Stand und Reproduktionsbefehl. Im UI steht sie derzeit bewusst nirgends |

---

## 9 · Prototyp-Behelfe, die NICHT übernommen werden dürfen

| Behelf | Richtige Umsetzung |
|---|---|
| Sprungliste in der Bewertung per JS-`transform` verschoben | nativer `position:sticky` mit sauber aufgesetztem Scroll-Container; Scroll-Spy über `IntersectionObserver` |
| Kopf-Filtermenüs als `position:fixed` Overlay | Portal ans Dokument-Ende — die Tabelle hat `overflow:auto` und schneidet sonst ab |
| Trefferbeleg („gefunden in: Beschreibung") clientseitig gesucht | `ts_headline` liefert Ausschnitt und Hervorhebung direkt aus Postgres |
| Blur mit echten Werten im DOM | serverseitig zurückhalten |
| Demo-Umschalter (Beispiel-Käufer, Datenlage, Match-Fall, Kontostatus) | ersatzlos entfernen |
| Konzentrations-Schwellen (fragmentiert/moderat/oligopol) im UI berechnet | gehört als fertiges Feld in den Gold Layer, sonst driften Badge, Skala und Farbe auseinander |
| Kontaktdaten frei erfunden | wo TED nichts nennt: „nicht angegeben". **Keine plausiblen Adressen konstruieren** — gerade weil die Kontaktzeile zum Handeln auffordert |

---

## 10 · Technische Notizen aus der Design-Arbeit

**Design-Token.** Abstände (`--s1`…`--s6`, 4er-Raster) und Typo (`--t-meta` … `--t-title`,
fünf Stufen) sind im Prototyp definiert und sollen die Umsetzung treiben. Ohne sie entstehen
beim Nachbauen wieder krumme Zwischenwerte — das war vor dem Design-Durchgang der Fall.

**Maßsystem der Detailseite.** Inhaltsspalte 820 px, Seitenspalte 200 px, Abstand 32 px,
außen 1120 px. Gilt in **allen** Tabs. 13 Zoll (≈1280 px) ist die Standard-Annahme —
Bid Manager arbeiten am Laptop. Zwei Spalten sind ein Bonus für große Bildschirme,
kein Fundament.

**Sichtbare Beschriftungen** gehören in eine zentrale Textquelle; interne Schlüssel bleiben
stabil (`auslauf`/`f02`/`f01`, `angriff`/`verteidigung`, Tab-Key `analyse` trotz Label
„Bewertung"). So kostet eine Umbenennung eine Zeile statt vier Fundstellen.

**Arbeitsplatz-Profil je Nutzer:** Trennlinien-Höhe (relativ als Anteil der Fensterhöhe,
**nicht in Pixeln**), Spaltenauswahl, Spaltenreihenfolge, Sortierung. Am **Konto** speichern,
nicht im Browser — sonst stimmt es am zweiten Rechner nicht. Unauffälliger Zurücksetzen-Weg nötig.

**Datenmodell:** `lead_status` (RLS auf Firma) und `lead_comments` getrennt. Analyse-Zähler
aus **einer** Quelle, die Zähler und Schranke gleichzeitig speist. Erfolgsprämien-Spur im
Team-Verlauf.

**Volltextsuche:** `tsvector` + GIN über Titel, Beschreibung und Lostexte, deutsche
Wortstammerkennung. ⚠️ **Snowball zerlegt keine Komposita** — „Pumpe" findet nicht
„Wärmepumpe". Für deutsche Vergabetexte spürbar; entweder Hunspell mit Kompositazerlegung
oder bei wenigen Treffern verwandte Begriffe vorschlagen.

**Skalierung:** Tabellen-Virtualisierung ab ~1000 Zeilen, Vorschlagssuche serverseitig,
Lead-Zahlen je Branche vorberechnet, Zentroid-Distanzmatrix für die Umkreissuche.

---

## 11 · Offene Fragen

1. **„Gesehen" pro Person oder pro Firma?** Wenn zwei Kollegen denselben Bestand teilen, ist
   „gesehen" vermutlich persönlich. Betrifft auch „alle als gesehen markieren".
2. **Profil-Branche als Menge.** Mischbetriebe brauchen mehrere Branchen; im Prototyp ist es
   eine. Von Anfang an als Set anlegen, sonst baut ihr euch eine Ecke.
3. **Ist `regulatory_regime` wirklich orthogonal zur Branche?** VOB *ist* Bau, VsVgV *ist*
   Verteidigung. Der Spread von 7 % auf 53 % Single-Bidder könnte die Branchenachse in neuem
   Gewand sein. Zu messen ist die **inkrementelle** AUC mit und ohne Regime, nicht der
   univariate Unterschied.
4. **Vergabeunterlagen:** nur verlinken (heute), abrufen und durchsuchbar machen, oder
   auswerten? Nur die dritte Stufe macht Textähnlichkeit für die Nachfolge-Erkennung und
   die Zuschnitt-Erkennung auf den Amtsinhaber möglich. **97 % sind frei zugänglich** —
   das ist der größte einzelne Hebel im Produkt.
   Solange nur verlinkt wird: nicht so aussehen, als hätten wir sie gelesen.
5. **Käufer-Ähnlichkeitsmaß** (Vektorisierung aus `buyer_profile` + `AA_AUTHORITY_TYPE` +
   `MA_MAIN_ACTIVITIES`) — entscheidet über „Vergabestellen wie eure Kunden".

---

## 12 · Was als Nächstes gestaltet wird

Landingpage → Registrierungsfluss (setzt auf `govisor-onboarding-v1.3.html` auf) →
Profil und Einstellungen.

Die Landingpage zuerst, weil dort die Antwort auf **„warum sollte ich das benutzen"**
formuliert werden muss — die fehlt bisher, weil wir immer *im* Produkt gearbeitet haben.
