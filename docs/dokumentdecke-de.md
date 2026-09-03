# Warum der deutsche Abrufer nicht schneller wird

**Stand 2026-09-03.** Sven: *„schraub den abrufer von D hoch."* — Die Stellschrauben gibt
es (`ABRUF_LIMIT=150`, `ABRUF_STUNDEN=1`, nachts 3 parallel), aber **sie tun nichts.**

---

## 1. Die Abrufer melden „nichts zu holen"

Im Protokoll steht in **jeder** Runde dasselbe:

```
[03.09. 15:38]   Runde 1453 — dran: cosinex subreport netserver
══ cosinex (govisor.docfetch) — bis zu 1 h, 150 je Runde
  Runde 1: kein Reststand gemeldet — Abrufer sagt:
══ subreport (govisor.subreport) — bis zu 1 h, 150 je Runde
  Runde 1: kein Reststand gemeldet — Abrufer sagt:
══ netserver — Runde 1: noch 0 offen
[03.09. 15:38] Runde beendet — 2 min Pause
```

Die Runde ist **in derselben Minute** durch. Direkt geprüft:

```
$ python3 -m govisor.cli fetch-docs --country DE --limit 10
  übersprungen (bekannter Ausgang): fehler=1, nicht_abrufbar=51
  643 Vorgänge liegen schon auf der Platte — vor dem Limit aussortiert.
  Unterlagen-Fetch DE: 0 Vorgänge | 0.0 MB neu
```

Mit `--limit 1` dasselbe Ergebnis wie mit `--limit 10`. **Es ist keine Drossel.**

## 2. Die 39 % sind eine Decke, kein Rückstau

13.626 offene Leads mit Unterlagen-Link, jeder gegen die Prädikate der 13 Abrufer geprüft:

| | Anzahl | Anteil | |
|---|---:|---:|---|
| von einem Abrufer abgedeckt | **9.040** | **66 %** | ✅ und abgearbeitet |
| Open House | 2.059 | 15 % | ⛔ man tritt bei, statt zu bieten |
| DTVP `secured/projectForwarding.do?pid=` | **1.508** | **11 %** | ⛔ Keycloak-Login |
| vergabe24 (`bund.vergabe24.de`, `vergabe24.de`) | 339 | 2 % | ⛔ weist den Client ab |
| `deutsche-evergabe.de` | 460 | 3 % | ⛔ Registrierung |
| Rest (≈40 Kleinportale) | ~220 | 2 % | ungeprüft |

Und innerhalb der abgedeckten 66 % sind die Manifest-Zustände gelernte Sackgassen:

```
downloaded            6.134     ✅
exists                3.203     schon auf der Platte
nur_liste             1.162     subreport liefert konstruktionsbedingt NIE ZIPs
kein_downloadbereich    541     Healy Hudson hat keinen Downloadbereich
gated                   295     hinter Anmeldung
fehler / leer / …       ~700
```

**Die Decke ist die Abdeckung, nicht das Tempo.**

## 3. ⚠ Drei Messfehler auf dem Weg — alle meine

**a) `--rueckstand` überzeichnet.** Es meldet für cosinex „1258 / 1699" und liest sich wie
ein Rückstau. Der Docstring sagt aber: **erwartete Ausbeute** (Rückstau × Trefferquote),
und beides zieht `gated`/`nicht_abrufbar` nicht ab. Der Abrufer selbst sieht 0 — und er hat
recht.

**b) „1.508 identische Adressen".** Ich hatte die Abfrage abgeschnitten
(`u.split('?')[0]`) und daraus geschlossen, alle 1.508 zeigten auf **eine** Adresse ohne
Kennung. Sie tragen sehr wohl eine: `?pid=2582842`. Erst danach war die richtige Frage
stellbar — und die Antwort war der Keycloak-Login.

**c) „dtvp hat keinen Abrufer".** Meine Zählschleife sagte das, während `is_cosinex` auf
`dtvp.de/Satellite/notice/CX…` sauber trifft. Beides stimmt: 2.009 der 3.518 dtvp-Adressen
werden erkannt, 1.509 nicht — **weil sie die Login-Form sind.** Das Prädikat hat recht,
nicht ich.

> **Lehre:** drei Anläufe, drei Mal „Befund" gerufen, drei Mal war es die Messung. Bei einer
> Zahl, die eine Entscheidung trägt, gehört eine Gegenprobe **in den Code** — beim vierten
> Anlauf stand `assert treffer` drin, und der lief sofort richtig.

## 4. Was wirklich helfen würde

⛔ **Nicht:** `ABRUF_LIMIT` hochsetzen, mehr Parallelität, längere Nachtfenster.

Der Reihe nach nach Ertrag:

1. **Nichts.** 66 % Abdeckung sind bei dieser Portallandschaft das Erreichbare — 28 % der
   offenen Leads liegen hinter Anmeldung oder Beitritt, und daran ändert kein Abrufer etwas.
2. Die ~220 Kleinportale (2 %) prüfen — 40 Einzelfälle für 220 Vorgänge.
3. ⚠ **Den Zulauf sichern statt den Bestand jagen.** Deutschland löscht binnen Monaten
   ([sondierung/haltbarkeit.md](sondierung/haltbarkeit.md) §11). Was zählt, ist dass der
   Abrufer **neue** Vergaben schnell erwischt — und das tut er: die Abrufer sind leer, weil
   sie mitkommen.

**Der deutsche Abrufer ist nicht zu langsam. Er ist fertig.**
