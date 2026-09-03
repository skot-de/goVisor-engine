# Sondierung Slowakei

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.**

**Stand 2026-09-03.**

---

## 1. Meine Vermutung war falsch

Nach der Anbieterkarte hatte ich geschrieben: *„Die Slowakei ist praktisch ein ProeBiz-Land
— und ProeBiz ist offen. Damit wäre sie vermutlich das nächste offene Land, ohne einen
einzigen neuen Abrufer."*

**Das stimmt nicht.** Die 1.472 ProeBiz-Nennungen stammen zum größten Teil aus dem
**Abgabeort**, nicht aus dem Unterlagen-Feld:

| Feldgruppe | ProeBiz | uvo.gov.sk |
|---|---:|---:|
| `unterlagen_link` | 124 | **4.383** |
| `abgabeort` | **1.099** | 1.615 |
| `kaeuferprofil` | — | 4.388 |

Slowakische Vergabestellen **veröffentlichen** auf `uvo.gov.sk` und **nehmen Angebote**
über Josephine entgegen. Zwei verschiedene Rollen, und ich hatte sie über alle Feldgruppen
zusammengezählt.

⚠ Genau davor sollte die Trennung nach Feldgruppen schützen — ich habe sie gebaut und dann
selbst über sie hinweg summiert.

## 2. Die tatsächliche Lage: ein Land, eine Behörde

| Portal | Anteil am Unterlagen-Feld |
|---|---:|
| **`uvo.gov.sk`** (Úrad pre verejné obstarávanie) | **95,8 %** (4.383 von 4.577) |
| `josephine.proebiz.com` | 2,7 % |
| `*.eranet.sk` (6 Instanzen) | 1,2 % |
| Rest | 0,3 % |

13 Domains im Unterlagen-Feld — nach dem Baltikum der konzentrierteste Markt.

Und die Adressen sind vorbildlich tief:
`/vyhladavanie/vyhladavanie-zakaziek/**dokumenty**/546836`

## 3. ⛔ Und trotzdem gesperrt — durch eine Freigabeliste

Die robots.txt von `uvo.gov.sk` führt **benannte Bots** mit Wartezeiten auf:

```
User-agent: Googlebot        Crawl-delay: 5    Disallow: /private/
User-agent: bingbot          Crawl-delay: 10   Disallow: /private/
User-agent: Applebot         Crawl-delay: 15   Disallow: /private/
User-agent: GPTBot           Crawl-delay: 30   Disallow: /private/
User-agent: ClaudeBot        Crawl-delay: 30   Disallow: /private/
User-agent: PerplexityBot    Crawl-delay: 30   Disallow: /private/
…
User-agent: *
Disallow: /                  ← die letzte Zeile
```

**Wer nicht namentlich genannt ist, ist vollständig gesperrt.** Ein Abrufer für goVisor
fällt unter `*`.

⚠ **Dass `ClaudeBot` auf der Liste steht, ändert daran nichts.** Das ist der Suchindex-
Crawler von Anthropic, nicht dieses Werkzeug. Sich seinen Namen zu geben, um an der Regel
vorbeizukommen, wäre eine Falschangabe gegenüber dem Betreiber — und der Betreiber hat mit
der Liste genau ausgedrückt, wen er meint.

## 4. ⚠ Eigener Regelbruch, festgehalten

**Ich habe die Dokumentenseite abgerufen, bevor ich die Sperre kannte.** Der Grund ist
banal und lehrreich zugleich: ich hatte die robots.txt mit `head -c 300` angesehen, und die
Datei ist 623 Bytes lang — die Sammelregel `User-agent: * / Disallow: /` steht **ganz am
Ende** und lag jenseits des Schnitts. Was ich sah, waren nur die freundlichen Einträge für
die benannten Bots.

**Die Lehre gehört in jede weitere Prüfung: eine robots.txt wird ganz gelesen.** Die
Sammelregel steht fast immer zuletzt, und sie ist die, auf die es ankommt. Ein Ausschnitt
vom Anfang zeigt systematisch die Ausnahmen und verschweigt die Regel.

Es blieb bei einem Abruf; nichts wurde entnommen oder gespeichert.

## 5. Ergebnis

**Slowakei: 0 % skriptfähig.** Nicht aus technischen Gründen — die Adressen sind tief, das
Land ist konzentriert, die Seite antwortet — sondern weil der Betreiber eine Freigabeliste
führt und wir nicht darauf stehen.

Das ist die zweite Sorte „verboten, nicht verschlossen" nach Open Nexus, LoginTrade, START
Toscana, NEN und EU-Supply — hier aber nicht als Pfadsperre, sondern als **Positivliste**.
Eine Form, die bisher nur bei `achatpublic` (FR) und `PortaleAppalti` (IT, nur Googlebot)
vorkam.
