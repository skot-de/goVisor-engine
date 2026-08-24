# 09 · Frontend und Sprache

> Gehört zu Tor 5. Die Pipeline kann alles richtig machen und die Oberfläche zeigt es
> trotzdem nicht.

## Der Vertrag ist englisch, die Anzeige ist es nicht

`lead_export` ist durchgehend **englisch — Spalten UND Werte**, damit der Vertrag für
weitere Länder trägt:

```
phase          expiring | open | planned
*_source       actual | estimated | uncertain | unknown
Bänder         high | medium | low | na
```

Das Vokabular ist in `tests/test_plumbing.py::_EXPORT_VOCAB` festgenagelt. **Wächst das
Mapping, muss die Allow-Liste mitwachsen** — sonst rutscht ein roher Code wie `cga-mun`
ins Frontend.

Die Übersetzung gehört in die Oberfläche, nicht in die Pipeline.

## i18n-Mechanik

Der **deutsche Satz ist der Schlüssel**. In `explorerCore.js` läuft die Übersetzung über
`tk()`, weil die Prototyp-Renderer die Sprache aus dem Modulzustand holen.

⚠ **Vier Fallen, alle schon zugeschlagen** — Details in der Auto-Memory
`govisor-i18n-mechanik`. Die wichtigste: `lang` **muss** in die React-Abhängigkeiten. Ohne
sie wechselt die Oberfläche die Sprache und der Detail-Körper bleibt deutsch stehen.

## Zwei verschiedene Sprachen

Nicht verwechseln:

- **Oberflächensprache** — was der Nutzer eingestellt hat.
- **Dokumentsprache** — in welcher Amtssprache die *Ausschreibung* vorliegt.

Der Umschalter für die Dokumentsprache erscheint **nur, wo es wirklich eine Wahl gibt**;
eine einzige Fassung ist keine Wahl, sondern die Sprache der Veröffentlichung. Die
gewählte Fassung muss auch den **Körper** erreichen, nicht nur die Überschrift — die
Leistungsbeschreibung ist der eigentliche Inhalt.

Gemessen 2026-08-23 nach der simap-Korrektur: **1.217 Leads** mit Sprachwahl
(CH 1.165, DE 36, AT 16). Häufigste Kombinationen de+fr 923, de+en 128, fr+it 54.

Zwei Leads zeigen **24 Sprachen** — das ist die EZB, die tatsächlich in allen EU-Amtssprachen
ausschreibt. Korrektes Verhalten, kein Fehler.

Die Schaltflächen zeigen Kürzel („DE", „FR", „IT"), wenn kein Übersetzungsschlüssel
existiert. Für einen Sprachumschalter ist das üblich und bewusst so gelassen.

## Keine Gedankenstriche in Oberflächentexten

**Sven-Vorgabe.** Oberflächentexte ohne `—` und `–`. Drei Ersetzungsregeln und drei Fallen
stehen in der Auto-Memory `govisor-keine-gedankenstriche`.

⚠ Gilt für **Oberflächentexte**, nicht für Quelltext-Kommentare oder Dokumentation.

## Länderkennzeichnung in der Anzeige

Es gibt bereits Bausteine:

```js
LAND_LABEL = {DE:'Deutschland', AT:"Österreich", CH:'Schweiz'}
```

und eine Kennzeichnung für Felder, die es nur in einem Land gibt („🇨🇭 nur Schweiz",
„🇦🇹 nur Österreich"). **Für ein neues Land beide erweitern**, sonst steht dort der rohe
Ländercode oder — schlimmer — „Deutschland" als Vorgabe.

## Herkunft anzeigen, nicht verstecken

Das Kernprinzip des Produkts: `*_source` sagt immer, ob ein Wert belegt oder abgeleitet ist.

- `regionQuelle` unterscheidet `amtlich` / `abgeleitet`
- `deadline_source`, `duration_source`, `band_source` ebenso
- fehlende Felder bleiben `null` → der Renderer zeigt ehrlich „zu wenig Daten"

⚠ **Aber: „zu wenig Daten" ist eine Aussage über die Vergabestelle.** Wenn in Wahrheit nur
die Datei fehlt, ist es eine Lüge. Genau so geschehen: kein einziger AT/CH-Käufer bekam ein
Profil, weil der Export `buyer_stats` nur aus DE las — und die Oberfläche behauptete, über
diese Stellen sei zu wenig bekannt.

**Prüffrage bei jedem leeren Feld: fehlt der Wert oder fehlt die Leitung?**

## Was ein neues Land in der Oberfläche braucht

1. `LAND_LABEL` und die Länder-Kennzeichnung erweitern
2. Prüfen, ob der Regionsfilter mit der NUTS-Ebene dieses Landes funktioniert
   ([Kapitel 07](07-geo-und-regionen.md))
3. Prüfen, ob länderabhängige Aggregate das richtige Land ziehen
   ([Kapitel 06](06-cross-verdrahtung.md)) — `nutzerLand()` erweitern
4. PLZ-Umkreissuche: kollidieren die PLZ mit einem Nachbarland?
5. Eine Runde durch die Detail-Tabs mit einem echten Lead dieses Landes

## Paywall und Sichtbarkeit

Die abgestuften Free/Pro-Regeln (`redactStrategie`, UI-Teaser) sind gebaut und ruhen hinter
`PAYWALL_ENFORCED`. Wer länderabhängige Aggregate baut, muss sie **durch** die Redaktion
führen — die API wählt erst das Land, dann redigiert sie. Diese Reihenfolge nicht drehen.
