"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { EV, track } from "@/lib/analytics";
import { AppRail, AppTop } from "@/components/explorer/Rail";
import { useSprache } from "@/lib/i18n";
import type { Baustein, Landing, Zeile } from "@/lib/outreach";

/* Client-Hälfte der Outreach-Landing (die Server-Hälfte liegt in `page.tsx`).
 *
 * **Warum geteilt.** `page.tsx` liest die vorberechnete `outreach.json` vom Dateisystem
 * und muss Server-Komponente bleiben. `useSprache` ist ein Hook, den es dort nicht gibt.
 *
 * **Der Bogen der Seite** (Sven, 2026-08-16): „das wissen wir bereits über euch, schärfe
 * dein profil und wir helfen dir die ausschreibungen mit dem besten fit zu finden".
 * Daraus folgen zwei Gruppen, nicht eine:
 *
 *     ÜBER EUCH   was öffentlich über die Firma dasteht (Zuschläge, Konzentration,
 *                 laufende Vorhaben). Der Beleg dafür, dass wir hinsehen können.
 *     FÜR EUCH    was im Markt offen ist. Der Beleg dafür, wofür sich das lohnt.
 *
 * Beides in EINE Kennzahlenleiste zu legen wäre kürzer und würde den Bogen zerstören:
 * „507 Zuschläge" und „8.080 offene Ausschreibungen" sind Aussagen über verschiedene
 * Dinge, und dazwischen liegt der ganze Grund für ein Konto.
 *
 * Nicht übersetzt und mit Absicht: Baustein-Titel, Kern- und Grenz-Sätze, Firmen- und
 * Vergabestellen-Namen, Beträge, Daten. Das ist generierter Befund, keine Oberfläche.
 *
 * **Was diese Datei NICHT tun darf:** einen fehlenden Baustein durch einen Platzhalter
 * ersetzen. Fehlt einer, dann weil er für diese Firma nicht belegt ist. */

function Vertragstabelle({ zeilen }: { zeilen: Zeile[] }) {
  const { t } = useSprache();
  const mitVolumen = zeilen.some((z) => z.vol);
  return (
    <div className="lg-tblwrap">
      <table className="lg-tbl">
        <thead>
          <tr>
            <th>{t("Vorhaben")}</th>
            <th>{t("Vergabestelle")}</th>
            {mitVolumen && <th className="lg-r">{t("Volumen")}</th>}
            <th className="lg-r">{t("Endet")}</th>
          </tr>
        </thead>
        <tbody>
          {zeilen.map((z, i) => (
            <tr key={i} className={z.art === "auslauf" ? "lg-auslauf" : ""}>
              <td className="lg-titel">{z.titel || t("(ohne Titel)")}</td>
              <td className="lg-buyer">{z.buyer}</td>
              {mitVolumen && <td className="lg-r lg-m">{z.vol ?? ""}</td>}
              <td className="lg-r lg-m">{z.ende ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Schrittweise Eingrenzung auf die Firma.
 *
 * Sven zur flachen Marktzahl: „8.080 offene ausschreibungen, schön und gut, aber wie
 * viele genau für klostermann?" Genau das zeigt der Trichter. Die letzte Stufe bleibt
 * offen und ist der Grund für das Profil: was Eignung und Kapazität hergeben, steht in
 * keiner Bekanntmachung.
 */
function Kette({ stufen, satz }: {
  stufen: NonNullable<Baustein["trichter"]>; satz?: string | null;
}) {
  const { t } = useSprache();
  /*
    Vierter Anlauf, und der letzte Umbau kam nicht von der Optik, sondern vom Inhalt.
    Sven: „den trichter sollten wir als kette zeigen: '8.080 Ausschreibungen sagt der
    Markt, wir sagen 194 und weniger die wirklich zu euch passen'."

    Ein gestapeltes Balkendiagramm laesst sich ansehen; eine Kette liest man. Und weil
    der Satz darueber dieselbe Aussage in Worten macht, traegt die Grafik nicht mehr die
    ganze Last: wer nur den Satz liest, hat es trotzdem verstanden.
  */
  return (
    <div className="lg-kettewrap">
      {satz && <p className="lg-kettesatz">{satz}</p>}
      <ol className="lg-kette">
        {stufen.map((s, i) => (
          <li className={`lg-glied${i === stufen.length - 1 ? " lg-letzte" : ""}`} key={i}>
            <span className="lg-n">{s.n.toLocaleString("de-DE")}</span>
            <span className="lg-lb">{s.label}</span>
            {s.hinweis && <span className="lg-hw">{s.hinweis}</span>}
          </li>
        ))}
        {/* Das offene Glied: keine Zahl. Es ist der Grund fuers Profil. */}
        <li className="lg-glied lg-offen">
          <span className="lg-n">?</span>
          <span className="lg-lb">{t("die wirklich zu euch passen")}</span>
        </li>
      </ol>
    </div>
  );
}

/** Kennzahlen-Leiste: je Baustein eine Kachel mit der tragenden Zahl. */
function KennzahlenLeiste({ teile }: { teile: Baustein[] }) {
  return (
    <>
      <div className="lg-leiste">
        {teile.map((b) => {
          const [erste, ...weitere] = (b.zahlen ?? []).filter((z) => z.wert);
          if (!erste) return null;
          return (
            <div className="lg-kachel" key={b.id}>
              <div className="lg-v">{erste.wert}</div>
              <div className="lg-k">{erste.label}</div>
              {typeof b.anteil === "number" && (
                <div className="lg-balken"><span style={{ width: `${Math.round(b.anteil * 100)}%` }} /></div>
              )}
              {weitere.length > 0 && (
                <div className="lg-neben">
                  {weitere.map((z, i) => <span key={i}>{z.wert} {z.label}</span>)}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {/* Die Grenz-Sätze bleiben sichtbar, gebündelt unter der Leiste. Sie in ein
          Sprechblasen-Symbol zu verstecken hiesse, sie abzuschaffen: eine Einschränkung,
          die man aufklappen muss, wird nach der Schlussfolgerung gelesen oder nie. */}
      <div className="lg-grenzen">
        {teile.map((b) => <p key={b.id}>{b.grenze}</p>)}
      </div>
    </>
  );
}

function Rahmen({ children }: { children: React.ReactNode }) {
  return (
    <div className="app">
      <AppTop ohneSuche />
      <div className="body">
        <AppRail gesperrt />
        <div className="main seitenmain landing">{children}</div>
      </div>
    </div>
  );
}

/** Unbekanntes oder abgelaufenes Token. Kein Grund, den Rahmen wegzulassen. */
export function LandingMissing() {
  const { t } = useSprache();
  return (
    <Rahmen>
      <div className="lg-hero">
        <h1>{t("Auswertung nicht gefunden")}</h1>
        <p className="lg-quelle">{t("Dieser Link ist ungültig oder abgelaufen.")}</p>
      </div>
    </Rahmen>
  );
}

export function LandingView({ d, token }: { d: Landing; token: string }) {
  const { t } = useSprache();
  // „Konto anlegen" führt ins ONBOARDING, nicht auf die Anmeldeseite. Vorher zeigte es auf
  // `/login?t=…`, eine Seite, die den Parameter nicht liest und „Willkommen zurück" sagt.
  const signup = `/onboarding?t=${encodeURIComponent(token)}`;

  /*
    MESSUNG (Sven, 2026-08-16): „was ist, wenn der nutzer nicht scrollt, weil er denkt
    die seite ist zuende?" Der Wegweiser ist die Antwort darauf, aber ob er wirkt, ist
    eine Behauptung, solange es niemand zaehlt.

    Drei Ereignisse, weil der Klick allein nicht deutbar ist: wenige Klicks koennen
    heissen „niemand kommt in die zweite Haelfte" oder „alle scrollen ohnehin". Erst
    `finden` (der zweite Teil war wirklich im Bild) trennt die beiden Faelle.

    `viaWegweiser` wird MITGESCHICKT statt spaeter aus der Reihenfolge erschlossen. Aus
    zwei Ereignissen im Nachhinein abzuleiten, welches das andere ausgeloest hat, geht
    schief, sobald jemand erst klickt, hochscrollt und wieder herunterkommt.
  */
  const [sicht, setSicht] = useState<"heute" | "morgen">("heute");
  const wegweiserBenutzt = useRef(false);
  const findenGemeldet = useRef(false);

  useEffect(() => {
    track(EV.LANDING_GESEHEN, { token, bausteine: d.belegt.length, belegt: d.belegt });
  }, [token, d.belegt]);

  // Gemessen wird, sobald die zweite Haelfte WIRKLICH sichtbar ist. Der fruehere
  // IntersectionObserver auf `#finden` passte zum Scrollen; bei Reitern ist die Frage
  // dieselbe, die Antwort steht aber schon im Zustand. `viaWegweiser` bleibt mitgeschickt:
  // ohne es waere im Nachhinein nicht zu trennen, ob jemand den Schalter benutzt hat oder
  // ob die Seite gar keine zweite Haelfte hatte.
  useEffect(() => {
    if (sicht !== "morgen" || findenGemeldet.current) return;
    findenGemeldet.current = true;
    track(EV.LANDING_FINDEN, { token, viaWegweiser: wegweiserBenutzt.current });
  }, [sicht, token]);

  const ueberEuch = d.bausteine.filter((b) => b.gruppe === "ueber_euch");
  const fuerEuch = d.bausteine.filter((b) => b.gruppe === "fuer_euch");   // auch im Kopf gebraucht
  // Ein Baustein mit Kette bekommt KEINE Kachel: die Kette nennt dieselbe Zahl und
  // erklaert sie dazu. Beides nebeneinander liest sich wie zwei verschiedene Befunde.
  const kacheln = (bs: Baustein[]) => bs.filter((b) => b.form === "kpi" && !b.kette);
  const karten = (bs: Baustein[]) => bs.filter((b) => b.form !== "kpi");

  return (
    <Rahmen>
      <div className="lg-hero">
        <div className="lg-eyebrow">{t("Auswertung · Stand {datum}", { datum: d.stand })}</div>
        {/*
          Zweizeilig, und das ist keine Typografie-Laune: „Unsere Sicht auf H. Klostermann
          Baugesellschaft mbH" als EIN Satz brach mitten im Firmennamen um. Ein zerrissener
          Firmenname im ersten Bildschirm ist genau die Sorte Schlamperei, die einem
          Empfaenger sagt, wie sorgfaeltig der Rest wohl ist.
          Der Name steht deshalb allein, `nowrap`, und die Schriftgroesse schrumpft per
          `clamp` mit — lieber kleiner als gebrochen.
        */}
        <h1>
          <span className="lg-h-vor">{t("Unsere Sicht auf")}</span>
          <span className="lg-h-firma">{d.name}</span>
        </h1>
        {/* Der Kernbefund kommt aus dem ÜBERRASCHENDSTEN Baustein, nicht dem belegtesten:
            „507 Zuschläge seit 2010" ist gut belegt und langweilig, „99 % von zwei
            Auftraggebern" ist dieselbe Datenlage und eine Nachricht. */}
        {d.kern && <p className="lg-kern">{d.kern}</p>}
        <p className="lg-quelle">{t("Alles aus öffentlichen Vergabebekanntmachungen. Keine Daten von Ihnen, kein Konto nötig.")}</p>
        {/*
          Sven: „was ist, wenn der nutzer nicht scrollt, weil er denkt die seite ist
          zuende?" Genau das droht: die Überschrift „Das wissen wir bereits über euch"
          klingt abgeschlossen, und der erste Bildschirm sieht aus wie die ganze Seite.
          Der Wegweiser nennt den zweiten Teil beim Namen UND führt hin. Ein blosser
          Pfeil hätte nur gesagt, dass da noch etwas ist, nicht was.
        */}
        {/*
          UMSCHALTER statt Wegweiser (Sven, 2026-08-17). Der Pfeil nach unten setzte
          voraus, dass jemand scrollt; zwei benannte Schalter zeigen beide Haelften als
          Wahl. Und sie sagen in vier Woertern, worum es geht: was ihr HEUTE seid, was
          MORGEN moeglich ist.
          Der Tracking-Name bleibt `LANDING_WEGWEISER` — sonst reisst die Zeitreihe, und
          gemessen werden soll dieselbe Frage („kommt jemand in die zweite Haelfte?").
        */}
        {fuerEuch.length > 0 && (
          <div className="lg-umschalter" role="tablist">
            <button role="tab" aria-selected={sicht === "heute"}
                    className={sicht === "heute" ? "lg-an" : ""}
                    onClick={() => setSicht("heute")}>{t("Euer Profil heute")}</button>
            <button role="tab" aria-selected={sicht === "morgen"}
                    className={sicht === "morgen" ? "lg-an" : ""}
                    onClick={() => { setSicht("morgen"); wegweiserBenutzt.current = true;
                                     track(EV.LANDING_WEGWEISER, { token }); }}>
              {t("Euer Potenzial morgen")}</button>
          </div>
        )}
      </div>

      {sicht === "heute" && kacheln(ueberEuch).length > 0 && (
        <KennzahlenLeiste teile={kacheln(ueberEuch)} />
      )}

      {sicht === "heute" && karten(ueberEuch).map((b) => (
        <section className="lg-karte" key={b.id}>
          <h2 className="lg-kt">{b.titel}</h2>
          {b.zeilen && b.zeilen.length > 0 && <Vertragstabelle zeilen={b.zeilen} />}
          {/* Der Befund ist die Schlussfolgerung aus der Tabelle. Er ersetzt die frühere
              Spalte „Art", die achtmal „wird fertig" sagte. */}
          {b.befund && <div className="lg-befund">{b.befund}</div>}
          {/* Was NICHT dasteht, gehoert dazu. Eine gefilterte Liste ohne diesen Satz
              behauptet Vollstaendigkeit, die sie nicht hat. */}
          {b.verschwiegen_text && <div className="lg-vergleich">{b.verschwiegen_text}</div>}
          {b.vergleich && <div className="lg-vergleich">{b.vergleich}</div>}
          <div className="lg-grenze">{b.grenze}</div>
        </section>
      ))}

      {sicht === "heute" && d.muster && (
        <p className="lg-muster">{d.muster}</p>
      )}

      {sicht === "morgen" && fuerEuch.length > 0 && (
        <div className="lg-wende" id="finden">
          <h2>{t("Und das können wir für euch finden")}</h2>
          <p className="lg-wende-lede">{t("Was davon zu euch passt, entscheidet euer Profil. Je schärfer es ist, desto weniger müsst ihr selbst durchsehen.")}</p>
          <KennzahlenLeiste teile={kacheln(fuerEuch)} />
          {fuerEuch.filter((b) => b.trichter?.length).map((b) => (
            <Kette key={b.id} stufen={b.trichter!} satz={b.kette} />
          ))}
        </div>
      )}

      <div className="lg-schluss">
        <h3>{t("Schärft euer Profil, dann übernehmen wir das Suchen")}</h3>
        <p>{t("Das Konto ist kostenlos. Die Auswertung oben ist bereits eingerichtet, ihr ergänzt nur, was wir aus öffentlichen Daten nicht sehen können.")}</p>
        {/* Ein Weg nach vorn, nicht sechs. Die Produktbereiche stehen als Ausblick
            darunter, statt als konkurrierende Verweise an jeder einzelnen Karte. */}
        <Link className="lg-cta" href={signup}
              onClick={() => track(EV.LANDING_CTA, { token, erreicht: findenGemeldet.current })}>
          {t("Profil einrichten, kostenlos")}
        </Link>
        {d.bereiche && d.bereiche.length > 0 && (
          <div className="lg-bereiche">
            {t("Danach offen:")} {d.bereiche.join(" · ")}
          </div>
        )}
        <div className="lg-fein">{t("Kostenlos dauerhaft nutzbar · keine Zahlungsdaten · keine Angaben, die nicht ohnehin öffentlich sind")}</div>
      </div>
    </Rahmen>
  );
}
