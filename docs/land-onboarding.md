# Ein neues Land aufnehmen

**Warum es diese Liste gibt.** Am 2026-08-22 wurde Österreich nachgemessen, sechs Wochen
nachdem es „fertig" war. Das Ergebnis: die Daten lagen vollständig da, kamen aber nicht an.

```
                DE      AT      CH        AT nach einem Tag Reparatur
Bindefrist    53 %     0 %    51 %   →   71 % (der TED-Vergaben)
Bürgschaft    39 %     0 %    51 %   →   20 %
Nebenangebote 60 %     0 %    51 %   →   34 %
Lose          79 %     0 %     0 %   →   25 % (CH: 41 %)
Link zur Quelle       57 %          →  100 %
```

Keiner dieser Fehler war ein Denkfehler. Es waren durchweg **Reste**: eine Funktion, die für
DE gebaut und für den Rest vergessen wurde. Sie fallen nicht auf, weil ein Feld leer bleibt
statt zu scheitern — und ein leeres Feld sieht aus wie eine Quelle, die nichts hergibt.

Diese Liste ist die Summe dieses Tages. Sie ist keine Theorie.

---

## 1 · Vor dem ersten Code: messen, was die Quelle wirklich trägt

⚠ **Füllquote allein entscheidet nichts.** Für Österreich stand `SpecificTendererRequirement`
bei **88 %** — es lag nahe, den Extraktor darauf umzustellen. Beim Hinsehen waren 91 % der
Werte Standard-Ausschlussgründe (`exg-mis-*`), `none` oder `epo-procurement-document`
(„steht in den Unterlagen"). Substanz trugen **37 von 435**. Der Freitext lautete wörtlich
„Gemäß den entsprechenden nationalen vergaberechtlichen Vorgaben."

**88 % Abdeckung, die nichts sagt, ist schlechter als 0 % — sie sieht aus wie eine Antwort.**

Drei Fragen, immer in dieser Reihenfolge:

1. **Welches Element nutzt das Land?** Derselbe eForms-Standard wird verschieden befüllt.
   DE liest `SelectionCriteria`; AT befüllt `SpecificTendererRequirement` und hat bei
   `SelectionCriteria` 3 von 435.
2. **Wie hoch ist die Füllquote?** Je Feld, gegen die offenen Vergaben des Landes.
3. **Wie viel davon ist Textbaustein?** Werteverteilung ansehen, nicht nur zählen. Diese
   Frage überspringt man leicht, weil die ersten beiden so schöne Zahlen liefern.

## 2 · Gold: keine „schlanke" Länder-Pipeline ohne Verfallsdatum

`build_at_gold` trug im Docstring: *„Bewusst KEINE volle DE-Gold-Pipeline (die käme später
separat, wenn AT-Volumen es rechtfertigt)."* Ein „später", das niemand wieder aufgemacht hat.
Ergebnis: 26 statt 74 Spalten, alle Anforderungs-Signale fehlten.

* **`_lead_context_sql(cfg, country)` anschliessen.** Nimmt das Land als Parameter und liefert
  Bürgschaft, Nebenangebote, Bindefrist, Fristuhrzeit, Bieterfragen-Frist. Kein zweiter Parser.
* **`documents_url` nicht an `ted_url` hängen.** Für nationale Quellen ist die leer: von
  10.877 `atv-`-Vorgängen hatten null eine `ted_url`. Die eigene Portalseite steht in Silber
  (`portal_url`) — `coalesce(n.ted_url, n.portal_url)`.
* **Jeder Glob auf `attributes` braucht einen Guard.** DuckDB wirft bei einem Glob ohne
  Treffer einen IO-Fehler; ein Land ohne geerntete Attribute bricht sonst mitten im Bau ab.
* **Wenn wirklich etwas fehlt, gehört es in den Docstring — mit dem Was, nicht nur dem Ob.**

## 3 · Export: `_union(...)`, niemals `{G}/…` für Faktentabellen

`{G}` ist `data/gold/DE`. Zwei Zeilen in `export_web_leads.py` lasen so `lead_lot` und
`entity_identity` — die AT- und CH-Fassungen existierten längst und kamen nie an.

`tests/test_plumbing.py::test_laenderuebergreifende_tabellen_werden_unioniert` prüft das
jetzt selbsttätig: es vergleicht, welche Gold-Tabellen es je Land WIRKLICH gibt, mit dem,
was der Export nur aus DE liest. `dim_*` ist ausgenommen (länderunabhängig).

## 4 · Portale: messen, nicht glauben — und Grenzen respektieren

Für jedes Portal des Landes gilt dieselbe Prüfung, und sie ist in diesem Projekt schon
mehrfach zu früh beendet worden (subreport galt erst als Bot-Sperre, dann als offen; beides
falsch):

* **Trägt der Link zur Vergabe oder nur zum Portal?** Bei `vemap.com` zeigen 189 von 189
  Links auf die Startseite. Ohne Vorgangs-ID kann kein Abrufer folgen. Die vorgangsgenauen
  Links gab es bis 2024-11-06 im alten TED-XML; seit eForms tragen die Auftraggeber nur noch
  die Wurzel ein.
* **Ein PDF ist noch keine Vergabeunterlage.** Was zurückkommt, kann die Bekanntmachung sein
  — die haben wir längst. `scripts/probe_portals.py` warnt im Modulkopf davor.
* **CAPTCHA ist eine Grenze, keine Hürde.** `vergabeportal.at` bietet den anonymen Download
  an und sperrt die Dateien per hCaptcha. Ein CAPTCHA wird nicht gelöst und nicht umgangen.
* **Was öffentlich ist, auch nehmen.** Wo die Dateien gesperrt sind, ist oft die *Dateiliste*
  offen. Aus Dateinamen lassen sich Dokumenttypen ableiten (`govisor.doctypes.classify`) —
  944 offene Vergaben ohne jeden Volltext haben darüber trotzdem eine Aussage.
  ⚠ Dann muss die Anzeige den Unterschied tragen: `gelesen: false`, und ein Satz, der sagt,
  dass niemand die Datei geöffnet hat.

## 5 · Statusklassen ehrlich halten

`gated` heisst „existiert, uns fehlt ein Zugang" und parkt Vorgänge dauerhaft. Am 2026-08-22
lagen darin drei verschiedene Lagen; 148 von 406 warteten auf ein Konto, das ihnen nicht
geholfen hätte (404/410-Fälle und Parser-Probleme). Beim Anlegen eines Connectors gilt:

* `weg` für 404/410 — dauerhaft, kein Nachfassen.
* `kein_listenlayout` (Blocker `parser`) für „Seite lädt, wir lesen sie nicht" — das ist eine
  **Arbeitsliste**, kein Schicksal. Freigabe über `scripts/entsperren.py`.
* `gated` nur für echte Anmeldeschranken.

## 6 · Zum Schluss: nachmessen statt annehmen

Nach dem Aufbau dieselbe Tabelle wie oben aufstellen — Feld für Feld, Land neben Land. Steht
irgendwo eine 0 %, wo das Nachbarland 50 % hat, ist es kein Quellenproblem, sondern ein Rest.
