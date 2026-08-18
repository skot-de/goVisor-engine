"use client";

/**
 * Betriebs-Dashboard: lief der Tageslauf, und wie groß ist der Dokumenten-Rückstand?
 *
 * **Warum es das gibt.** Am 2026-08-15 war die Antwort auf „ist der Tageslauf sauber
 * durchgelaufen?" nur durch Durchsuchen von Logdateien zu bekommen — und die Antwort war
 * nein: der Lauf vom 14.08. endete mit einem gescheiterten Supabase-Upload, der vom 13.08.
 * brach mitten im Herunterladen ab, und beide Male fiel es tagelang niemandem auf.
 *
 * **Die eine Regel dieser Seite: ein ausbleibender Lauf muss ALARM auslösen, nicht Stille.**
 * Deshalb ist „abgebrochen" ein eigener, roter Zustand — er entsteht, wenn die Schlusszeile
 * im Log fehlt. Ein Dashboard, das bei Ausfall den letzten guten Stand zeigt, ist schlimmer
 * als keins: es beruhigt genau dann, wenn es warnen müsste.
 */
import { useEffect, useState } from "react";
import { AppRail, AppTop } from "@/components/explorer/Rail";
import "../../explorer.css";
import "./lauf.css";

/** Ertragsbericht aus `govisor/ertrag.py`. Bewusst locker typisiert: der Bericht waechst
 *  mit jeder neuen Kennzahl, und eine ANZEIGE darf nicht am naechsten Feld zerbrechen. */
type Ertrag = {
  stand?: string;
  trichter?: { stufe: string; n: number | null; pct: number | null }[];
  auslesen?: { lesbar_pct?: number | null; dateien?: number | null };
  belegt_pct?: Record<string, number | null>;
  blockiert_nach_grund?: Record<string, number>;
  veraenderung?: Record<string, number>;
};

type Schritt = {
  name: string; zeit: string | null; dauerSek: number | null;
  normalSek: number | null; zustand: "fertig" | "laeuft" | "offen";
};

type Antwort = {
  ertrag?: Ertrag | null;
  schritte?: Schritt[];
  erzeugt: string;
  lauf: {
    datum: string | null;
    ergebnis: "durch" | "mit_fehlern" | "abgebrochen" | "laeuft" | "keiner";
    dauerSek: number | null;
    endeUm: string | null;
    alterStunden: number | null;
    fehlerZeilen: string[];
    letzterSchritt: string | null;
    schrittListe: { zeit: string; name: string }[];
    logZeilen: string[];
  };
  fortschritt: { fertig: number; erwartet: number; anteil: number;
                 verbleibendSek: number | null; massstabAus: string | null };
  /** Startversuche, die es nicht bis zum eigenen Log geschafft haben (z. B. gesperrte
   *  Datenplatte). Ohne sie waere ein Lauf, der sofort stirbt, unsichtbar. */
  vorLog: { zeit: number; zeilen: string[] } | null;
  dokumente: {
    aufPlatte: number; indiziert: number | null; rueckstand: number | null;
    stand: string | null; zeichen: number;
    status: Record<string, number>; abgeschossen: number;
    /* Was tatsächlich im Frontend liegt — nicht, was auf der Platte liegt.
       null heisst „Datei fehlt", nicht „null Stück". Der Unterschied ist der
       ganze Zweck dieser Anzeige. */
    trichter: { signale: number | null; volltext: number | null;
                analyse: number | null; struktur: number | null };
    arbeiter: { laeuft: boolean; letzte: string[] };
  };
};

const AMPEL: Record<Antwort["lauf"]["ergebnis"], { farbe: string; text: string }> = {
  durch:       { farbe: "gut",  text: "sauber durchgelaufen" },
  mit_fehlern: { farbe: "warn", text: "durchgelaufen, aber mit Fehlern" },
  laeuft:      { farbe: "info", text: "läuft gerade" },
  abgebrochen: { farbe: "bad",  text: "ABGEBROCHEN — keine Schlussmeldung im Log" },
  keiner:      { farbe: "bad",  text: "kein Lauf gefunden" },
};

function dauer(sek: number | null): string {
  if (!sek) return "—";
  const h = Math.floor(sek / 3600), m = Math.round((sek % 3600) / 60);
  return h ? `${h} h ${m} min` : `${m} min`;
}

/** Sekunden lesbar. Unter einer Minute bleibt es bei Sekunden — „0 min" fuer einen
 *  Schritt, der 12 s brauchte, liest sich wie ein Fehler. */
function minuten(sek: number): string {
  if (sek < 60) return `${sek} s`;
  if (sek < 5400) return `${Math.round(sek / 60)} min`;
  return `${(sek / 3600).toFixed(1).replace(".", ",")} h`;
}

export default function LaufPage() {
  const [d, setD] = useState<Antwort | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);

  useEffect(() => {
    const holen = () => fetch("/api/intern/lauf", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setD)
      .catch((e) => setFehler(String(e.message || e)));
    holen();
    // Alle 60 s nachladen: der Index laeuft stundenlang, und man will den Rueckstand
    // schrumpfen sehen, ohne die Seite anzufassen.
    // Waehrend eines Laufs alle 10 s, sonst jede Minute. Ein Log, das man beim Zusehen
    // manuell neu laden muss, wird nicht angesehen.
    const t = setInterval(holen, 10_000);
    return () => clearInterval(t);
  }, []);

  const ertrag = d?.ertrag ?? null;
  const schritte = d?.schritte ?? [];
  const [alleSchritte, setAlleSchritte] = useState(false);
  const ampel = d ? AMPEL[d.lauf.ergebnis] : null;
  // Der Lauf ist fuer 13:00 und 22:00 eingeplant — aelter als 14 h heisst, einer ist
  // ausgefallen, selbst wenn der letzte sauber war.
  const ueberfaellig = d?.lauf.alterStunden != null && d.lauf.alterStunden > 14;

  return (
    <div className="app">
      <AppTop />
      <div className="body">
        <AppRail />
        {/* NICHT `main`: die Klasse traegt das Drei-Zeilen-Raster der Lead-Ansicht
              (Liste / Griff / Detail, `grid-template-rows:1fr 6px 34vh`). Sie sieht wie ein
              generischer Inhaltsbereich aus und ist keiner — meine drei Karten wurden darin
              in die Zeilen gequetscht, die mittlere bekam 6 px (die Hoehe des Griffs).
              `seitenmain` allein ist der richtige Wrapper: Spalte aus `.body`, eigener
              Scroll, kein Raster. */}
          <div className="seitenmain lauf-page">
          {fehler ? <div className="lauf-fehler">Konnte den Zustand nicht laden: {fehler}</div> : null}
          {!d ? <p className="lauf-laedt">lädt …</p> : (
            <>
              <section className={`lauf-karte lauf-${ampel!.farbe}`}>
                <div className="lauf-kopf">
                  <span className="lauf-punkt" aria-hidden="true" />
                  <b>Tageslauf {d.lauf.datum ?? ""}</b>
                  <span className="lauf-urteil">{ampel!.text}</span>
                </div>
                <dl className="lauf-werte">
                  <div><dt>Dauer</dt><dd>{dauer(d.lauf.dauerSek)}</dd></div>
                  <div><dt>Ende</dt><dd>{d.lauf.endeUm ?? "—"}</dd></div>
                  <div><dt>Letzte Regung</dt>
                    <dd className={ueberfaellig ? "ist-alt" : undefined}>
                      {d.lauf.alterStunden != null ? `vor ${d.lauf.alterStunden} h` : "—"}
                    </dd></div>
                </dl>
                {ueberfaellig ? (
                  <p className="lauf-hinweis">
                    Geplant sind 13:00 und 22:00 — bei diesem Alter ist mindestens ein Lauf
                    ausgefallen.
                  </p>
                ) : null}
                {d.lauf.ergebnis === "abgebrochen" && d.lauf.letzterSchritt ? (
                  <p className="lauf-hinweis">Zuletzt begonnen: <code>{d.lauf.letzterSchritt}</code></p>
                ) : null}

                {/* FORTSCHRITT. Der Massstab ist der letzte VOLLSTAENDIGE Lauf, nicht die
                    `step`-Zeilen im Skript: davon gibt es 30, gelaufen sind zuletzt 20 (der
                    Rest haengt an Bedingungen). Ein Balken, der nie 100 % erreicht, wird
                    nicht geglaubt. */}
                {d.fortschritt.erwartet > 0 ? (
                  <div className="lauf-fortschritt">
                    <div className="lf-kopf">
                      <span>Schritt <b>{d.fortschritt.fertig}</b> von ~{d.fortschritt.erwartet}</span>
                      {d.fortschritt.verbleibendSek != null ? (
                        <span className="lf-rest">noch ~{dauer(d.fortschritt.verbleibendSek)}</span>
                      ) : null}
                    </div>
                    <div className="lf-bahn" role="progressbar"
                         aria-valuenow={Math.round(d.fortschritt.anteil * 100)}
                         aria-valuemin={0} aria-valuemax={100}>
                      <div className="lf-fuell" style={{ width: `${d.fortschritt.anteil * 100}%` }} />
                    </div>
                    {d.lauf.letzterSchritt ? (
                      <p className="lf-aktuell">{d.lauf.letzterSchritt}</p>
                    ) : null}
                    {d.fortschritt.massstabAus ? (
                      <p className="lf-fuss">Restzeit geschätzt aus dem letzten vollständigen Lauf —
                        ändert sich der Umfang, stimmt sie nicht.</p>
                    ) : null}
                  </div>
                ) : null}
              </section>

              {d.lauf.logZeilen.length ? (
                <section className="lauf-karte">
                  <div className="lauf-kopf">
                    <b>Log — die letzten {d.lauf.logZeilen.length} Zeilen</b>
                    <span className="lauf-urteil">
                      aktualisiert {new Date(d.erzeugt).toLocaleTimeString("de-DE")}
                    </span>
                  </div>
                  {/* Von unten nach oben lesbar: `column-reverse` haelt die JUENGSTE Zeile
                      im Blick, ohne bei jeder Aktualisierung scrollen zu muessen. */}
                  <pre className="lauf-log">{d.lauf.logZeilen.join("\n")}</pre>
                </section>
              ) : null}

              <section className="lauf-karte">
                <div className="lauf-kopf"><b>Vergabeunterlagen — Rückstand beim Auspacken</b></div>
                <dl className="lauf-werte">
                  <div><dt>Archive auf der Platte</dt><dd>{d.dokumente.aufPlatte.toLocaleString("de-DE")}</dd></div>
                  <div><dt>davon im Index</dt>
                    <dd>{d.dokumente.indiziert?.toLocaleString("de-DE") ?? "?"}</dd></div>
                  <div><dt>Rückstand</dt>
                    <dd className={(d.dokumente.rueckstand ?? 0) > 0 ? "ist-offen" : undefined}>
                      {d.dokumente.rueckstand?.toLocaleString("de-DE") ?? "unbekannt"}
                    </dd></div>
                </dl>
                {/* Getrennt ausgewiesen, weil es KEIN Rueckstand ist: diese Archive sind
                    bearbeitet, sie haben nur keinen Text ergeben. Sie in den Rueckstand zu
                    zaehlen hiesse, eine Zahl zu zeigen, die nie auf null geht. */}
                {/* ── WAS BEIM NUTZER ANKOMMT ──────────────────────────────────
                    „Archive auf der Platte" ist die halbe Wahrheit: entscheidend ist,
                    wie viel davon im Frontend landet. Am 2026-08-18 lagen 4.499
                    Volltexte bereit und 14 kamen an, weil ein Export-Aufruf im Tageslauf
                    fehlte. Nichts war rot — die Datei existierte ja, sie war nur uralt.
                    Diese vier Zahlen machen genau das sichtbar. */}
                <div className="lauf-trichter">
                  <div className="lauf-trichter-h">Im Frontend angekommen</div>
                  <dl>
                    <div><dt>Signale</dt>
                      <dd>{d.dokumente.trichter.signale?.toLocaleString("de-DE") ?? "?"}</dd></div>
                    <div><dt>Leistungsverzeichnis</dt>
                      <dd>{d.dokumente.trichter.struktur?.toLocaleString("de-DE") ?? "?"}</dd></div>
                    <div><dt>Volltext</dt>
                      <dd>{d.dokumente.trichter.volltext?.toLocaleString("de-DE") ?? "?"}</dd></div>
                    <div><dt>LLM-Analyse</dt>
                      <dd>{d.dokumente.trichter.analyse?.toLocaleString("de-DE") ?? "?"}</dd></div>
                  </dl>
                </div>

                {/* Der Dauer-Arbeiter. Er schläft, solange der Tageslauf läuft — das ist
                    kein Fehler, sondern die Kollisionssperre. Ohne diese Zeile sähe es
                    aus, als täte er nichts. */}
                <div className="lauf-arbeiter">
                  <div className="lauf-trichter-h">
                    Dokumenten-Arbeiter{" "}
                    <span className={d.dokumente.arbeiter.laeuft ? "ist-an" : "ist-aus"}>
                      {d.dokumente.arbeiter.laeuft ? "läuft" : "gestoppt"}
                    </span>
                  </div>
                  {d.dokumente.arbeiter.letzte.length ? (
                    <pre className="lauf-log">{d.dokumente.arbeiter.letzte.join("\n")}</pre>
                  ) : <p className="lauf-hinweis">Noch keine Meldung.</p>}
                </div>

                {d.dokumente.abgeschossen > 0 ? (
                  <p className="lauf-hinweis">
                    {d.dokumente.abgeschossen} Archive an der Speicher- oder Zeitgrenze
                    abgebrochen — bearbeitet, aber ohne Text. Kein Rückstand.
                  </p>
                ) : null}
                {d.dokumente.rueckstand == null ? (
                  <p className="lauf-hinweis">
                    Noch kein Indexlauf, der seinen Stand hinterlassen hat — die Zahl kommt
                    mit dem nächsten Durchlauf. Bis dahin wird hier <b>nichts geschätzt</b>.
                  </p>
                ) : null}
                <p className="lauf-fuss">
                  Indexstand: {d.dokumente.stand ? d.dokumente.stand.replace("T", " ") : "keiner"}
                  {d.dokumente.zeichen ? ` · ${(d.dokumente.zeichen / 1e6).toFixed(0)} Mio. Zeichen` : ""}
                </p>
                {Object.keys(d.dokumente.status).length ? (
                  <ul className="lauf-status">
                    {Object.entries(d.dokumente.status).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                      <li key={k}><span>{k}</span><b>{v.toLocaleString("de-DE")}</b></li>
                    ))}
                  </ul>
                ) : null}
              </section>

              {d.vorLog ? (
                <section className="lauf-karte lauf-bad">
                  <div className="lauf-kopf">
                    <span className="lauf-punkt" aria-hidden="true" />
                    <b>Startversuch gescheitert — vor dem ersten Logeintrag</b>
                  </div>
                  <p className="lauf-hinweis">
                    Ein geplanter Lauf ist angesprungen und sofort gestorben. Er hat es nicht
                    bis zu seiner eigenen Logdatei geschafft; das hier kommt aus dem
                    launchd-Fehlerlog und ist <b>neuer</b> als der letzte richtige Lauf.
                  </p>
                  <ul className="lauf-fehlerliste">
                    {d.vorLog.zeilen.map((z, i) => <li key={i}>{z}</li>)}
                  </ul>
                </section>
              ) : null}

              {/* ── ERTRAG ─────────────────────────────────────────────────────────
                  Der Trichter steht ZUERST und als groesstes Element. Er beantwortet die
                  einzige Frage, an der sich entscheidet, ob das Produkt traegt: wie viele
                  offene Ausschreibungen koennen wir ueberhaupt inhaltlich beurteilen?
                  Gemessen 2026-08-16 sind das 21 % — die Auslesequalitaet liegt bei 92 %,
                  aber an vier von fuenf Vergaben kommen wir gar nicht heran. Die beiden
                  Zahlen einzeln sehen harmlos aus; nebeneinander zeigen sie die Schwaeche. */}
              {ertrag?.trichter?.length ? (
                <section className="lauf-karte">
                  <div className="lauf-kopf">
                    <b>Ertrag</b>
                    <span className="lauf-neben">
                      Stand {(ertrag.stand || "").replace("T", " ").slice(0, 16)}
                    </span>
                  </div>

                  <ol className="ert-trichter">
                    {ertrag.trichter.map((s) => {
                      const d2 = ertrag.veraenderung?.[`trichter.${s.stufe}`];
                      return (
                        <li key={s.stufe}>
                          <span className="ert-t-name">{s.stufe}</span>
                          <span className="ert-t-bahn">
                            <span className="ert-t-fuell" style={{ width: `${s.pct ?? 0}%` }} />
                          </span>
                          <span className="ert-t-n">{(s.n ?? 0).toLocaleString("de-DE")}</span>
                          <span className="ert-t-p">{s.pct != null ? `${s.pct} %` : "—"}</span>
                          {/* Veraenderung nur zeigen, wenn es eine gibt. Ein ewiges „±0"
                              trainiert das Auge, die Spalte zu ueberspringen. */}
                          <span className={`ert-t-d ${(d2 ?? 0) > 0 ? "auf" : (d2 ?? 0) < 0 ? "ab" : ""}`}>
                            {d2 ? (d2 > 0 ? `+${d2}` : `${d2}`) : ""}
                          </span>
                        </li>
                      );
                    })}
                  </ol>

                  <div className="ert-zeilen">
                    <div>
                      <span className="ert-k">Dateien lesbar</span>
                      <span className="ert-v">{ertrag.auslesen?.lesbar_pct ?? "—"} %</span>
                      <span className="ert-n">
                        von {(ertrag.auslesen?.dateien ?? 0).toLocaleString("de-DE")}
                      </span>
                    </div>
                    {Object.entries(ertrag.belegt_pct || {}).map(([k, v]) => (
                      <div key={k}>
                        <span className="ert-k">{k} belegt</span>
                        <span className="ert-v">{v ?? "—"} %</span>
                      </div>
                    ))}
                  </div>

                  {Object.keys(ertrag.blockiert_nach_grund || {}).length ? (
                    <p className="ert-block">
                      <b>Blockiert:</b>{" "}
                      {Object.entries(ertrag.blockiert_nach_grund ?? {}).map(([g, n], i) => (
                        <span key={g}>{i ? " · " : ""}{g} {(n as number).toLocaleString("de-DE")}</span>
                      ))}
                      <em>— Vorgänge, an deren Unterlagen wir ohne Zugang nicht herankommen.</em>
                    </p>
                  ) : null}
                </section>
              ) : null}

              {/* ── WO STEHT DER LAUF ─────────────────────────────────────────────
                  Der Balken allein sagt „64 von 64" und damit fast nichts. Diese Liste
                  beantwortet die eigentliche Frage: WELCHER Schritt laeuft, seit wann,
                  und was kommt noch. Die Normaldauer daneben stammt aus dem letzten
                  vollstaendigen Lauf — „subreport dauert normal 88 min" ist eine
                  Auskunft, „noch 3 h" ist eine Zahl. */}
              {schritte.length ? (
                <section className="lauf-karte">
                  <div className="lauf-kopf">
                    <b>Schritte</b>
                    <span className="lauf-neben">
                      {schritte.filter((x) => x.zustand === "fertig").length} von {schritte.length}
                      {schritte.some((x) => x.zustand === "offen")
                        ? "" : " · keine Vergleichsdaten für Offenes"}
                    </span>
                  </div>
                  <ol className="schrittliste">
                    {(alleSchritte ? schritte : schritte.filter(
                        (x, i) => x.zustand !== "fertig" || i >= schritte.length - 40))
                      .map((x, i) => (
                      <li key={`${x.name}-${i}`} className={`sl-${x.zustand}`}>
                        <span className="sl-mark" aria-hidden="true" />
                        <span className="sl-zeit">{x.zeit || ""}</span>
                        <span className="sl-name">{x.name}</span>
                        <span className="sl-dauer">
                          {x.dauerSek != null ? minuten(x.dauerSek) : ""}
                        </span>
                        {/* Normaldauer nur bei dem, was noch aussteht oder gerade laeuft —
                            bei Erledigtem steht die ECHTE Dauer daneben und ein Vergleich
                            waere Beiwerk. */}
                        <span className="sl-normal">
                          {x.zustand !== "fertig" && x.normalSek ? `normal ${minuten(x.normalSek)}` : ""}
                        </span>
                      </li>
                    ))}
                  </ol>
                  {schritte.length > 40 ? (
                    <button className="sl-mehr" onClick={() => setAlleSchritte((v) => !v)}>
                      {alleSchritte ? "weniger zeigen" : `alle ${schritte.length} Schritte zeigen`}
                    </button>
                  ) : null}
                </section>
              ) : null}

              {d.lauf.fehlerZeilen.length ? (
                <section className="lauf-karte">
                  <div className="lauf-kopf"><b>Gemeldete Fehler des letzten Laufs</b></div>
                  <ul className="lauf-fehlerliste">
                    {d.lauf.fehlerZeilen.map((z, i) => <li key={i}>{z}</li>)}
                  </ul>
                </section>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
