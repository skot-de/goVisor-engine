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

## ⚠ Die Haustür spricht nur Deutsch

Die Sprachumschaltung wirkt **hinter der Anmeldung**. Die öffentlichen Seiten tragen ihren
Text fest verdrahtet im JSX, nicht über den Katalog. Gemessen am 2026-08-30:

```
Landing.tsx   35 deutsche Textstellen · 0 im Katalog · 0 t()-Aufrufe
/start         3                      · 0            · 0
/login         2                      · 0            · 0
```

Das ist mehr als ein Schönheitsfehler, wenn ein Land dazukommt: der erste Bildschirm, den
ein französischer oder polnischer Bieter sieht, ist deutsch — und zwar der einzige, den er
ohne Konto zu sehen bekommt. Die Pipeline kann das Land vollständig tragen, und das Produkt
stellt sich trotzdem auf Deutsch vor.

**Folge für die Auffindbarkeit:** es gibt kein `hreflang`, und das ist richtig so. Die
Angabe verlangt sprachspezifische URLs mit *unterschiedlichem* Inhalt. Wer Routen wie `/en`
anlegt, bevor die Texte übersetzbar sind, liefert dort denselben deutschen Text aus —
`hreflang` wäre dann eine Falschangabe, und drei URLs mit gleichem Inhalt sind schlechter
als eine saubere.

**Reihenfolge, wenn es angegangen wird:** erst die Texte auf `t()` verdrahten und EN/FR
schreiben, dann Sprach-Routen, dann `hreflang` in `app/layout.tsx`. Nicht andersherum.

`tests/test_auffindbarkeit.py::test_hreflang_fehlt_solange_es_nichts_zu_verlinken_gibt`
bewacht **die Begründung, nicht den Zustand**: sobald die öffentlichen Seiten einen
`t()`-Aufruf bekommen, entfällt der Grund und der Test verlangt Routen samt `hreflang`.
Entscheidung vom 2026-08-30 (Sven): vorerst nur Deutsch.

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
6. ⚠ **Die öffentliche Startseite bleibt deutsch** — auch für dieses Land. Solange das so
   ist, ist der Markteintritt nach innen fertig und nach aussen nicht (s. oben,
   „Die Haustür spricht nur Deutsch"). Das gehört benannt, nicht stillschweigend
   abgehakt.

## ⚠ Es gibt ZWEI Profile, und nur eines führt zur Empfehlung

Wer etwas ins „Profil" schreibt, muss wissen, in welches. Am 2026-08-31 stolperte genau
daran eine Reparatur, die schon fertig aussah.

| | wo | wer liest es |
|---|---|---|
| **Onboarding-Profil** | `profileEngine.buildProfile`, `localStorage` + `saveProfile` | `matchLead` → Relevanz-Stufe und Passungszahl |
| **Firmenprofil** (#27) | `lib/supabase/unternehmen.ts`, serverseitig | `recommendation.js` über `profile.attributes` |

⚠ **`capabilities` im Onboarding-Profil liest heute NIEMAND.** Der Name passt zu den
Schlüsseln aus `REQUIRED_KEYS`, die Werte landen aber im falschen Behälter:
`recommendation.js` liest `attributes`, nicht `capabilities`. Wer dorthin schreibt, baut
eine Reparatur, die aussieht wie eine und keine ist.

**Beim Schreiben ins Firmenprofil gilt `zustand`:** `"angegeben"` ist Selbstauskunft,
`"belegt"` heisst, wir haben einen Nachweis, `"abgeleitet"` zählt in `coverage()` nicht mit.
Ein Klick-Check auf der Startseite liefert `"angegeben"` — nie `"belegt"`.

## ⚠ Eine fehlende Leitung wirft keine Ausnahme

Der Eignungs-Check sammelte sechs Angaben, rechnete eine Auswertung, und der Aufruf ins
Onboarding war ein blankes `<a href="/onboarding">`. Beide Enden funktionierten tadellos.
Nur dazwischen war nichts. Kein Test wurde rot, keine Ausnahme flog, und aufgefallen ist es
erst, als jemand den Weg von Hand abging.

> **Für jeden mehrstufigen Weg im Frontend die Frage stellen: was trägt der Übergang?**
> Ein Verweis trägt nichts ausser der Adresse. Wer Angaben sammelt und danach weiterleitet,
> braucht eine Übergabe — mit EINER Datei für beide Seiten, sonst laufen Schlüssel und Form
> auseinander.

⚠ **Nicht gestellte Fragen sind keine Neins.** Der Check zeigt je Fachgebiet nur die
Nachweise, die dort vorkommen (Bau 2, IT 3). Die übrigen stehen als `false` im Zustand, weil
das der Vorgabewert ist. Wer den Zustand einfach übernimmt, schreibt dem Nutzer eine Antwort
zu, die er nie gegeben hat — und `coverage()` zählt sie mit. Deshalb fährt mit, WELCHE
Fragen gestellt wurden.

⚠ **Eine Übernahme muss sichtbar sein.** Vorbelegte Zahlen wirken auf jede spätere
Bewertung; wer sich vertippt hat, muss es bemerken können. Still ist schlechter als gar
nicht.

## ⚠ Eine Regel, die dem Hinweis daneben widerspricht

Unter dem Passwortfeld stand „Länge zählt mehr als Sonderzeichen, eine Passphrase aus vier
Wörtern ist sicherer als P@ssw0rt!" — und der Prüfer wies genau diese Passphrase ab, weil
ihr die Ziffer fehlte. Beide Seiten waren für sich vertretbar, und **Widersprüche zwischen
zwei richtigen Dingen fängt keine Zusicherung ab.**

Dazu standen drei Regeln für dieselbe Sache nebeneinander: Anlegen 12 Zeichen plus Klassen,
Zurücksetzen 8, Einstellungen 8. **Die schwächste gewinnt, weil sie erreichbar bleibt** —
man konnte später ein Passwort setzen, mit dem man sich nicht hätte registrieren dürfen.

> **Wo dieselbe Regel an mehreren Stellen gilt, gehört sie in eine Datei.** Und wo eine
> Oberfläche etwas verspricht, gehört die Zusage in einen Test, nicht die Bedingung.

⚠ **Serverseite mitdenken:** Supabase führt eine eigene Passwortregel („Password
Requirements" im Dashboard). Sie steht in keiner Codezeile und kann eine Passphrase
trotzdem abweisen.

## ⚠ Zwei Bedeutungen in einem Wort

Der Abschlussbildschirm meldete „Nicht bestätigt" und zwei Zeilen darunter
„Identität: bestätigt ✓". Die Zeile hing an `matched` (wir haben die Firma GEFUNDEN), der
Kasten am Beleg (wir wissen, dass ihr dazugehört). Beides hiess „bestätigt".

**Wo zwei Anzeigen dieselbe Sache behaupten, müssen sie dieselbe Quelle lesen.** Sonst
widersprechen sie sich irgendwann, und beim Beleg-Zustand ist das kein Schönheitsfehler:
das Produkt wirbt mit „was sich nicht wörtlich belegen lässt, verwerfen wir".

## Paywall und Sichtbarkeit

Die abgestuften Free/Pro-Regeln (`redactStrategie`, UI-Teaser) sind gebaut und ruhen hinter
`PAYWALL_ENFORCED`. Wer länderabhängige Aggregate baut, muss sie **durch** die Redaktion
führen — die API wählt erst das Land, dann redigiert sie. Diese Reihenfolge nicht drehen.
