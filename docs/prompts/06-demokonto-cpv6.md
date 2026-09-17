# demo_konto.py erzeugt ein groeberes Profil als das echte Onboarding

## Was passiert
Ein per `scripts/demo_konto.py` angelegtes Konto zeigt schlechter passende
Ausschreibungen als dieselbe Firma nach echtem Onboarding. Waehrend einer Vorfuehrung
mussten die gewerkscharfen Codes von Hand in Supabase nachgetragen werden, damit die
Liste taugte.

## Befund (gemessen 2026-09-17)
Der Produktweg ist vollstaendig:

    suppliers.json         → fields6 bei 37.216 von 37.946 Firmen (98,1 %)
    /api/entity-search:52  → fields6: v.fields6 ?? []
    onboarding/page.tsx:622→ cpvFields6: (matched.fields6 || []).map(f => f.cpv6)
    profileEngine.js:157   → has6 trennt Volltreffer von Nachbarfeld

Der Demoweg ist es nicht:

    scripts/demo_konto.py:132  felder = f.get("fields") or []      ← nur CPV-4
    scripts/demo_konto.py:202  "cpv_fields": [x["cpv4"] ...]
    scripts/demo_konto.py:211  "cpvFields":  [x["cpv4"] ...]

`fields6` kommt im ganzen Skript nicht vor. Das Demokonto faellt damit auf
CPV-4-Verhalten zurueck, und `profileEngine.js:154` sagt genau das an: „Alt-Profile
ohne cpvFields6 → CPV-4-Verhalten". Aufzug und Elektro sind dann dasselbe Gewerk.

Zur Groessenordnung: nach dem Nachtragen der zwoelf Codes fuer H. Klostermann standen
598 Volltreffer gegen 1.170 Nachbarfeld. Vorher war beides eine Menge.

## Warum das mehr ist als ein Demo-Fehler
Das Demokonto ist das, was Aussenstehende vom Produkt sehen. Ein Skript, das ein
schwaecheres Profil baut als der echte Weg, zeigt das Produkt unter Wert. Und es
verdeckt Regressionen: waere der Onboarding-Pfad kaputt, wuerde der Demolauf es nicht
bemerken, weil er ihn nicht benutzt.

## Aufgabe
1. `fields6` in `demo_konto.py` mitnehmen, in beide Profilformen (Zeile 202 und 211).
2. Besser noch: das Skript soll das Profil nicht selbst zusammenbauen, sondern
   dieselbe Ableitung benutzen wie das Onboarding. Zwei Stellen, die aus derselben
   Quelle ein Profil bauen, laufen auseinander. Sie sind hier bereits auseinander.
3. Eine Gegenprobe, die fuer eine Testfirma beide Wege durchspielt und die Profile
   Feld fuer Feld vergleicht. Nicht die Summe der Felder, sondern jedes einzeln.
   `web/scripts/pruefe-profilform.mjs` prueft bereits 18 Felder einzeln und ist die
   Vorlage dafuer.

## Falle
`pruefe-profilform.mjs:44` fuehrt `cpvFields6` in seiner Feldliste. Der Waechter kennt
das Feld also und hat trotzdem nichts gemeldet, weil er die Profilform prueft und
nicht den Demoweg. Ein Waechter, der das richtige Feld kennt und die falsche Stelle
ansieht, ist gefaehrlicher als keiner: er erzeugt Vertrauen.

## Abnahme
- Fuer eine Testfirma: Zahl der Volltreffer und der Nachbarfeld-Treffer auf beiden
  Wegen, im Commit. Sie muessen gleich sein.
- Der Test muss rot werden, wenn man `fields6` aus `demo_konto.py` wieder entfernt.
