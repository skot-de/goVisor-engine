"use client";

import Link from "next/link";
import { AppRail, AppTop } from "@/components/explorer/Rail";
import { useSprache } from "@/lib/i18n";
import type { Baustein, Landing, Zeile } from "@/lib/outreach";

/* Client-Hälfte der Outreach-Landing (die Server-Hälfte liegt in `page.tsx`).
 *
 * **Warum geteilt.** `page.tsx` liest die vorberechnete `outreach.json` vom Dateisystem
 * und muss Server-Komponente bleiben. Die Oberflächensprache steht im `localStorage`,
 * und `useSprache` ist ein Hook, den es auf dem Server nicht gibt.
 *
 * **Warum im App-Rahmen.** Die Seite trug bis zum 2026-08-16 eine eigene Hülle mit
 * eigenem Wortzeichen (ein `<span>govisor</span>` statt der Bildmarke). Sven beim
 * Durchsehen: „das govisor logo ist ein anderes." Es war nicht nur das Logo, sondern
 * die ganze zweite Hülle: der erste Eindruck sah aus wie ein anderes Produkt als das,
 * in das er führt. Jetzt derselbe Rahmen wie Anmeldung und Onboarding, Rail sichtbar
 * aber gesperrt.
 *
 * Nicht übersetzt und mit Absicht: Baustein-Titel, Kern- und Grenz-Sätze, Firmen- und
 * Vergabestellen-Namen, Beträge, Daten. Das ist generierter Befund, keine Oberfläche.
 *
 * **Was diese Datei NICHT tun darf:** einen fehlenden Baustein durch einen Platzhalter
 * ersetzen. Fehlt einer, dann weil er für diese Firma nicht belegt ist. */

function Vertragstabelle({ zeilen }: { zeilen: Zeile[] }) {
  const { t } = useSprache();
  // Volumenspalte nur, wenn irgendwo ein belegter Wert steht.
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

function BausteinKarte({ b, signup }: { b: Baustein; signup: string }) {
  // Die erste Zahl trägt den Baustein und wird gross gesetzt, der Rest steht daneben.
  // Vorher waren alle Zahlen gleich gross in einem Raster: gleichmässig und dadurch
  // ohne Aussage. Sven: „optisch ist die seite echt langweilig. keine highlights."
  const [erste, ...weitere] = (b.zahlen ?? []).filter((z) => z.wert);
  return (
    <section className="lg-karte">
      <h2 className="lg-kt">{b.titel}</h2>

      {erste && (
        <div className="lg-zahlen">
          <div className="lg-gross">
            <div className="v">{erste.wert}</div>
            <div className="k">{erste.label}</div>
          </div>
          {weitere.map((z, i) => (
            <div className="lg-klein" key={i}>
              <div className="v">{z.wert}</div>
              <div className="k">{z.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Ein Balken sagt „fast alles" schneller als die Zahl daneben. */}
      {typeof b.anteil === "number" && (
        <div className="lg-balken"><span style={{ width: `${Math.round(b.anteil * 100)}%` }} /></div>
      )}

      {b.namen && b.namen.length > 1 && <div className="lg-namen">{b.namen.join(" · ")}</div>}

      {b.zeilen && b.zeilen.length > 0 && <Vertragstabelle zeilen={b.zeilen} />}

      {/* Der Befund ist die Schlussfolgerung aus der Tabelle und darf sie überstrahlen.
          Er ersetzt die frühere Spalte „Art", die achtmal „wird fertig" sagte. Sven:
          „die wissen doch woran sie gerade arbeiten?" */}
      {b.befund && <div className="lg-befund">{b.befund}</div>}
      {b.vergleich && <div className="lg-vergleich">{b.vergleich}</div>}

      {/* Was die Zahlen NICHT abdecken. Im Baustein, nicht als Fussnote am Seitenende. */}
      <div className="lg-grenze">{b.grenze}</div>

      <Link className="lg-bruecke" href={signup}>
        <span className="bp">{b.bruecke.produkt}</span>
        <span className="bt">{b.bruecke.text}</span>
      </Link>
    </section>
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
      <section className="lg-karte">
        <h2 className="lg-kt">{t("Auswertung nicht gefunden")}</h2>
        <div className="lg-grenze">{t("Dieser Link ist ungültig oder abgelaufen.")}</div>
      </section>
    </Rahmen>
  );
}

export function LandingView({ d, token }: { d: Landing; token: string }) {
  const { t } = useSprache();
  // „Konto anlegen" führt ins ONBOARDING, nicht auf die Anmeldeseite. Vorher zeigte es auf
  // `/login?t=…`, eine Seite, die den Parameter nicht liest und „Willkommen zurück" sagt.
  const signup = `/onboarding?t=${encodeURIComponent(token)}`;

  return (
    <Rahmen>
      <div className="lg-hero">
        <div className="lg-eyebrow">{t("Auswertung · Stand {datum}", { datum: d.stand })}</div>
        <h1>{d.name}</h1>
        {/* Der Kernbefund ist die eine Aussage, die ohne Umgebung trägt. Er kommt aus dem
            ÜBERRASCHENDSTEN Baustein, nicht aus dem belegtesten: „507 Zuschläge seit 2010"
            ist gut belegt und langweilig, „99 % von zwei Auftraggebern" ist dieselbe
            Datenlage und eine Nachricht. */}
        {d.kern && <p className="lg-kern">{d.kern}</p>}
        <p className="lg-quelle">{t("Alles aus öffentlichen Vergabebekanntmachungen. Keine Daten von Ihnen, kein Konto nötig.")}</p>
        <Link className="lg-cta" href={signup}>{t("Konto anlegen, kostenlos")}</Link>
      </div>

      {d.bausteine.map((b) => <BausteinKarte key={b.id} b={b} signup={signup} />)}

      <div className="lg-schluss">
        <h3>{t("Diese Auswertung gehört Ihnen")}</h3>
        <p>{t("Mit einem Konto bleibt sie erhalten, wird täglich fortgeschrieben und um die Ausschreibungen ergänzt, die zu Ihrem Profil passen.")}</p>
        <Link className="lg-cta" href={signup}>{t("Konto anlegen, kostenlos")}</Link>
        <div className="lg-fein">{t("Kostenlos dauerhaft nutzbar · keine Zahlungsdaten · Auswertung bereits eingerichtet")}</div>
      </div>
    </Rahmen>
  );
}
