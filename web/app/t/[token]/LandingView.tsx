"use client";

import Link from "next/link";
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
            {mitVolumen && <th className="r">{t("Volumen")}</th>}
            <th className="r">{t("Endet")}</th>
          </tr>
        </thead>
        <tbody>
          {zeilen.map((z, i) => (
            <tr key={i} className={z.art === "auslauf" ? "lg-auslauf" : ""}>
              <td className="lg-titel">{z.titel || t("(ohne Titel)")}</td>
              <td className="lg-buyer">{z.buyer}</td>
              {mitVolumen && <td className="r m">{z.vol ?? ""}</td>}
              <td className="r m">{z.ende ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
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
              <div className="v">{erste.wert}</div>
              <div className="k">{erste.label}</div>
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

  const ueberEuch = d.bausteine.filter((b) => b.gruppe === "ueber_euch");
  const fuerEuch = d.bausteine.filter((b) => b.gruppe === "fuer_euch");
  const kacheln = (bs: Baustein[]) => bs.filter((b) => b.form === "kpi");
  const karten = (bs: Baustein[]) => bs.filter((b) => b.form !== "kpi");

  return (
    <Rahmen>
      <div className="lg-hero">
        <div className="lg-eyebrow">{t("Auswertung · Stand {datum}", { datum: d.stand })}</div>
        <h1>{t("Das wissen wir bereits über {firma}", { firma: d.name })}</h1>
        {/* Der Kernbefund kommt aus dem ÜBERRASCHENDSTEN Baustein, nicht dem belegtesten:
            „507 Zuschläge seit 2010" ist gut belegt und langweilig, „99 % von zwei
            Auftraggebern" ist dieselbe Datenlage und eine Nachricht. */}
        {d.kern && <p className="lg-kern">{d.kern}</p>}
        <p className="lg-quelle">{t("Alles aus öffentlichen Vergabebekanntmachungen. Keine Daten von Ihnen, kein Konto nötig.")}</p>
      </div>

      {kacheln(ueberEuch).length > 0 && <KennzahlenLeiste teile={kacheln(ueberEuch)} />}

      {karten(ueberEuch).map((b) => (
        <section className="lg-karte" key={b.id}>
          <h2 className="lg-kt">{b.titel}</h2>
          {b.zeilen && b.zeilen.length > 0 && <Vertragstabelle zeilen={b.zeilen} />}
          {/* Der Befund ist die Schlussfolgerung aus der Tabelle. Er ersetzt die frühere
              Spalte „Art", die achtmal „wird fertig" sagte. */}
          {b.befund && <div className="lg-befund">{b.befund}</div>}
          {b.vergleich && <div className="lg-vergleich">{b.vergleich}</div>}
          <div className="lg-grenze">{b.grenze}</div>
        </section>
      ))}

      {fuerEuch.length > 0 && (
        <div className="lg-wende">
          <h2>{t("Und das können wir für euch finden")}</h2>
          <p className="lg-wende-lede">{t("Was davon zu euch passt, entscheidet euer Profil. Je schärfer es ist, desto weniger müsst ihr selbst durchsehen.")}</p>
          <KennzahlenLeiste teile={kacheln(fuerEuch)} />
        </div>
      )}

      <div className="lg-schluss">
        <h3>{t("Schärft euer Profil, dann übernehmen wir das Suchen")}</h3>
        <p>{t("Das Konto ist kostenlos. Die Auswertung oben ist bereits eingerichtet, ihr ergänzt nur, was wir aus öffentlichen Daten nicht sehen können.")}</p>
        {/* Ein Weg nach vorn, nicht sechs. Die Produktbereiche stehen als Ausblick
            darunter, statt als konkurrierende Verweise an jeder einzelnen Karte. */}
        <Link className="lg-cta" href={signup}>{t("Profil einrichten, kostenlos")}</Link>
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
