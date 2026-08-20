"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

/**
 * Öffentlicher Eignungs-Check — der Einstieg, den die Startseite nicht hatte.
 *
 * **Was es drinnen schon gab und warum das nicht reichte.** Der Abgleich Profil gegen
 * Anforderung steckt seit Ticket #27 in der Anwendung und entscheidet dort mit („Nicht
 * bewerben, Pflichtanforderung verletzt"). Er setzt aber ein Konto, ein Onboarding und ein
 * gepflegtes Profil voraus. Wer die Seite zum ersten Mal sieht, hat nichts davon — und die
 * Frage, die ihn wirklich umtreibt, ist eine Nummer kleiner: *komme ich da überhaupt in
 * Frage?* Hier beantwortet sie drei Auswahlen, ohne Anmeldung und ohne Firmendaten.
 *
 * **Warum das ehrlich bleibt, obwohl es wirbt.** Verglichen wird gegen GEMESSENE Werte:
 * die Größenverteilung nur über Vorgänge mit VERÖFFENTLICHTEM Auftragswert (der Bestand
 * trägt auch geschätzte — die zählen hier nicht), die Schwellen nur aus ausgewerteten
 * Vergabeunterlagen. Jede Aussage nennt ihre Grundlage mit; wo ein Fachgebiet zu dünn
 * belegt ist (unter 30 Fundstellen), fällt der Vergleich sichtbar auf den Gesamtbestand
 * zurück. Der Würfel dahinter kommt aus `scripts/export_landing.py` und steckt in
 * `web/data/landing.json` — knapp 14 KB, damit hier gerechnet werden kann, ohne 40 MB
 * Leaddateien zu verschicken.
 *
 * **Warum hier auch die Fachgebiete stehen.** Bis zum 2026-08-20 gab es zwei Abschnitte
 * direkt untereinander: „Offen in eurem Fachgebiet" (sechs Zahlen zum Anschauen) und den
 * Check (der dieselbe Auswahl noch einmal als Aufklappmenü stellte). Sven: „sollte man
 * besser verbinden." Jetzt SIND die Kacheln die Auswahl — und sie rechnen mit: wer eine
 * Region wählt, sieht alle sechs Zahlen auf diese Region umspringen. Aus einer Anzeige
 * wird ein Werkzeug, und eine doppelte Frage verschwindet.
 *
 * **Eingeklappt, aber nicht leer.** Sven: „sonst nimmt er zu viel platz weg". Sichtbar
 * bleibt der obere Rand — zwei Auswahlfelder und die Zahl der offenen Vergaben in diesem
 * Zuschnitt. Wer weiterklickt, bekommt die drei Fragen und den Vergleich.
 *
 * **Kein Ergebnis wird verschickt.** Alles bleibt im Browser: keine Eingabe geht an einen
 * Server, es gibt keinen Endpunkt dafür. Das ist nicht nur Datenschutz, sondern der Grund,
 * warum jemand die Zahlen überhaupt eintippt.
 */

export type Check = {
  regionen: { schluessel: string; label: string; offen: number }[];
  stufen: { von: number; bis: number | null }[];
  zellen: Record<string, { offen: number; mitWert: number; stufen: number[] }>;
  anforderungen: Record<string, {
    frage: string; einheit: string; unten: string; stufen: number[];
    je_fach: Record<string, { n: number; median: number; kum: number[] }>;
  }>;
  wert: { n: number; min: number | null; median: number | null; max: number | null; unter25k: number };
};

const nf = (n: number) => n.toLocaleString("de-DE");
const ZAHLWORT: Record<number, string> = { 2: "Zwei", 3: "Drei", 4: "Vier", 5: "Fünf", 6: "Sechs" };

/** 250000 → „250.000 €", 3000000 → „3 Mio €". Auf einer Auswahlleiste zählt Kürze. */
function euro(n: number): string {
  if (n >= 1_000_000) {
    const m = n / 1_000_000;
    return `${(Math.round(m * 10) / 10).toLocaleString("de-DE")} Mio €`;
  }
  return `${nf(n)} €`;
}

function stufenLabel(s: { von: number; bis: number | null }): string {
  if (s.von === 0) return `bis ${euro(s.bis as number)}`;
  if (s.bis === null) return `über ${euro(s.von)}`;
  return `${euro(s.von)} – ${euro(s.bis)}`;
}

/** Eine Auswahlleiste: Knöpfe statt Aufklappmenü, weil man die Nachbarwerte sehen soll. */
function Leiter({ titel, optionen, wert, setzen }: {
  titel: string; optionen: string[]; wert: number; setzen: (i: number) => void;
}) {
  return (
    <div className="ec-frage">
      <span className="ec-frage-t">{titel}</span>
      <div className="ec-leiter" role="group" aria-label={titel}>
        {optionen.map((o, i) => (
          <button key={o} type="button" aria-pressed={wert === i}
                  className={wert === i ? "ec-opt ec-opt-an" : "ec-opt"}
                  onClick={() => setzen(i)}>{o}</button>
        ))}
      </div>
    </div>
  );
}

export function EignungsCheck({ check, fachgebiete }: {
  check: Check; fachgebiete: { schluessel: string; label: string; offen: number }[];
}) {
  const [fach, setFach] = useState(fachgebiete[0]?.schluessel ?? "bau");
  const [region, setRegion] = useState("alle");
  const [groesse, setGroesse] = useState(2);          // 100.000 – 500.000 €: der dichteste Bereich
  const [antwort, setAntwort] = useState<Record<string, number>>({
    haftpflicht: 2, referenzen: 2, umsatz: 2,
  });
  // Eingeklappt startet der Abschnitt, weil er sonst ein Drittel der Startseite frisst.
  // Sichtbar bleibt trotzdem etwas, das rechnet: Fachgebiet, Region und die Zahl der
  // offenen Vergaben darin. Ein Knopf, der nur ein leeres Formular verspricht, wird nicht
  // gedrückt — einer, unter dem schon eine Zahl steht, schon.
  const [offen, setOffen] = useState(false);

  const zelle = check.zellen[`${fach}|${region}`] ?? { offen: 0, mitWert: 0, stufen: [0, 0, 0, 0, 0, 0] };
  const fachLabel = fachgebiete.find((f) => f.schluessel === fach)?.label ?? fach;
  const regionLabel = check.regionen.find((r) => r.schluessel === region)?.label ?? region;

  // „In eurer Größenordnung" heisst: alles bis zu der Grösse, die ihr stemmt. Wer 2 Mio
  // stemmt, kann auch 40.000 — die umgekehrte Lesart („genau diese Stufe") wäre für die
  // Frage, ob man mitbieten kann, die falsche.
  const passend = zelle.stufen.slice(0, groesse + 1).reduce((a, b) => a + b, 0);

  const TITEL: Record<string, string> = {
    haftpflicht: "Betriebshaftpflicht", referenzen: "Vergleichbare Referenzen",
    umsatz: "Jahresumsatz",
  };

  const zeilen = useMemo(() => Object.entries(check.anforderungen).map(([name, a]) => {
    const basis = a.je_fach[fach] ?? a.je_fach["alle"];
    const eigenesFach = Boolean(a.je_fach[fach]);
    const i = antwort[name] ?? 0;
    const erfuellt = i < 0 || !basis ? 0 : (basis.kum[i] ?? 0);
    const anteil = basis && basis.n ? Math.round((erfuellt / basis.n) * 100) : 0;
    return {
      name, a, basis, eigenesFach, anteil, erfuellt,
      titel: TITEL[name] ?? name,
      quelle: basis
        ? `Median ${a.einheit === "€" ? euro(basis.median) : basis.median} · ${nf(basis.n)} Fundstellen`
          + (eigenesFach ? "" : ", fachgebietsübergreifend")
        : "keine Fundstellen",
      grund: basis ? `${anteil} % verlangen nicht mehr` : "nicht belegt",
    };
  }), [check.anforderungen, fach, antwort]);

  // Die Auftragsgrösse ist die vierte Zeile derselben Tabelle — nur kommt ihre Zahl aus den
  // veröffentlichten Auftragswerten, nicht aus den Unterlagen. Sie steht oben, weil sie die
  // Frage beantwortet, die vor allen anderen kommt: ist da überhaupt etwas in meiner Grösse?
  const wertAnteil = zelle.mitWert ? Math.round((passend / zelle.mitWert) * 100) : 0;
  const alleZeilen = [
    {
      name: "groesse", titel: "Auftragsgrösse", anteil: wertAnteil,
      quelle: `${nf(zelle.mitWert)} von ${nf(zelle.offen)} nennen ihren Wert`,
      grund: zelle.mitWert ? `${nf(passend)} liegen in eurer Grösse` : "kein Wert veröffentlicht",
      genug: zelle.mitWert >= 20,
    },
    ...zeilen.map((z) => ({ ...z, genug: Boolean(z.basis) })),
  ];

  const stark = alleZeilen.filter((z) => z.genug && z.anteil >= 50).length;
  /** Fünf Segmente wie drinnen in der Lead-Liste: ein Balken lügt weniger als eine Note. */
  const segmente = (anteil: number) => Math.max(0, Math.min(5, Math.round(anteil / 20)));

  return (
    <section className="lp-check" id="check">
      <div className="ec-kacheln-block">
        <h2 className="lp-h2">Was heute offen ist. Und ob ihr drankommt.</h2>
        <ul className="ec-kacheln" role="group" aria-label="Fachgebiet wählen">
          {fachgebiete.map((f) => {
            const z = check.zellen[`${f.schluessel}|${region}`];
            return (
              <li key={f.schluessel}>
                <button type="button" aria-pressed={fach === f.schluessel}
                        aria-label={`${f.label}: ${nf(z?.offen ?? 0)} offene Vergaben`}
                        className={fach === f.schluessel ? "ec-kachel ec-kachel-an" : "ec-kachel"}
                        onClick={() => setFach(f.schluessel)}>
                  <b>{nf(z?.offen ?? 0)}</b>
                  <span>{f.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
        <p className="lp-klein">
          Gezählt sind Vorgänge mit laufender Frist, {regionLabel === "überall" ? "in allen drei Ländern"
            : regionLabel}. Dazu alles, was sich keinem dieser Gebiete zuordnen lässt:
          Lieferungen, Dienstleistungen, Sonderfälle. Der Zuschnitt läuft über CPV-Codes,
          nicht über Schlagworte.
        </p>
      </div>

      <div className="ec-text">
        <p className="lp-auge">Eignungs-Check</p>
        <h2 className="lp-h3">Jeder kann mitbieten. Auch ihr.</h2>
        <p>
          Öffentliche Aufträge gelten als eine Sache für Grosse. Der kleinste offene Auftrag
          im Bestand liegt bei {check.wert.min !== null ? euro(check.wert.min) : "—"},
          {" "}{nf(check.wert.unter25k)} offene Vergaben liegen unter 25.000 €, nach oben
          hört es bei {check.wert.max !== null ? euro(check.wert.max) : "—"} auf.
        </p>
        <p>
          Sagt uns, was ihr habt. Wir zeigen euch, wie nah ihr an dem seid, was in eurem
          Fachgebiet tatsächlich verlangt wird. Ohne Anmeldung, ohne Firmendaten, nichts
          davon verlässt euren Browser.
        </p>
      </div>

      <div className="ec-panel">
        <div className="ec-kopf">
          <label>
            <span>Region — die Kacheln oben rechnen mit</span>
            <select value={region} onChange={(e) => setRegion(e.target.value)}>
              {check.regionen.map((r) => (
                <option key={r.schluessel} value={r.schluessel}>{r.label}</option>
              ))}
            </select>
          </label>
        </div>

        <p className="ec-vorschau">
          <b>{nf(zelle.offen)}</b> offene Vergaben in {fachLabel}, {regionLabel}.
        </p>

        {!offen ? (
          <button type="button" className="ec-mehr" onClick={() => setOffen(true)}>
            {/* ⚠ Stand hier bis zum 2026-08-20 als getippte „Drei Fragen", während vier
                gestellt wurden. Gezählt statt getippt: eine Frage mehr, und der Satz
                stimmt weiter. */}
            Wie nah seid ihr dran? {ZAHLWORT[1 + Object.keys(check.anforderungen).length]
              ?? String(1 + Object.keys(check.anforderungen).length)} Fragen, keine Anmeldung
            <span aria-hidden="true">→</span>
          </button>
        ) : null}

        <div className={offen ? "ec-tief" : "ec-tief ec-zu"} hidden={!offen}>
        <Leiter titel="Aufträge bis zu welcher Grösse könnt ihr stemmen?"
                optionen={check.stufen.map(stufenLabel)} wert={groesse} setzen={setGroesse} />

        {Object.entries(check.anforderungen).map(([name, a]) => (
          <Leiter key={name} titel={a.frage}
                  optionen={[a.unten, ...a.stufen.map((s) => (a.einheit === "€" ? euro(s) : String(s)))]}
                  wert={(antwort[name] ?? 0) + 1}
                  setzen={(i) => setAntwort({ ...antwort, [name]: i - 1 })} />
        ))}

        {/* ERGEBNIS als Tabelle. Die Vorlage (`INPUT/…/govisor-landing-v28.html`) zeigt ihre
            Urteile in einer Zeile je Fall: Balken für die Stärke, ein Punkt für das Urteil,
            der Grund klein darunter. Sven: „die optik aus dem html bei der ergebnisanzeige
            fand ich sexier." Sie ist es auch — und zwar nicht nur hübscher: vier Zeilen
            gleicher Bauart lassen sich vergleichen, vier Fliesstexte nicht. Der Unterschied
            zur Vorlage bleibt, dass hier nichts erfunden ist; jede Zeile nennt ihre
            Grundlage in der Spalte daneben. */}
        <div className="ec-ergebnis">
          <table className="ec-tabelle">
            <thead>
              <tr>
                <th>Anforderung</th>
                <th>Wie ihr dasteht</th>
                <th>Urteil</th>
              </tr>
            </thead>
            <tbody>
              {alleZeilen.map((z) => {
                const gut = z.genug && z.anteil >= 50;
                return (
                  <tr key={z.name} className={!z.genug ? "ec-tr-leer" : gut ? "ec-tr-gut" : "ec-tr-knapp"}>
                    <td>
                      {/* Titel und Grundlage in EINER Spalte, wie in der Vorlage: vier
                          Spalten drängeln sich in einem 570 px breiten Kasten, drei atmen. */}
                      <span className="ec-tit">{z.titel}</span>
                      <span className="ec-quelle">{z.quelle}</span>
                    </td>
                    <td className="ec-mess">
                      <span className={`ec-meter ec-m${segmente(z.anteil)}`} aria-hidden="true">
                        <i /><i /><i /><i /><i />
                      </span>
                      <span className="ec-prozent">{z.genug ? `${z.anteil} %` : "—"}</span>
                    </td>
                    <td className="ec-urteil">
                      <span className={gut ? "ec-note ec-note-gut" : "ec-note ec-note-blass"}>
                        {!z.genug ? "zu dünn belegt" : gut ? "passt" : "knapp"}
                      </span>
                      <span className="ec-grund">{z.grund}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <p className="ec-fazit">
            <span className="ec-punkt" aria-hidden="true" />
            <span>
              {stark === alleZeilen.length
                ? "Ihr liegt bei allen vier Punkten über dem, was üblicherweise verlangt wird."
                : stark === 0
                  ? "Bei den üblichen Vorgaben liegt ihr noch darunter. Das heisst nicht, dass nichts passt: die Anforderungen wachsen mit der Auftragsgrösse, und der kleinste offene Auftrag kostet weniger als ein Werkzeugkoffer."
                  : `Ihr liegt bei ${stark} von ${alleZeilen.length} Punkten über dem, was üblicherweise verlangt wird.`}
            </span>
            <span className="ec-marke">gemessen, nicht geschätzt</span>
          </p>

          <Link className="lp-knopf" href="/onboarding">Die passenden Vergaben ansehen</Link>
          <p className="ec-fuss">
            Verglichen wird gegen veröffentlichte Auftragswerte und gegen Schwellen aus den
            ausgewerteten Vergabeunterlagen. Was ein einzelnes Verfahren verlangt, steht
            drinnen an jedem Vorgang, mit dem wörtlichen Zitat daneben.
          </p>
        </div>
        </div>
      </div>
    </section>
  );
}
