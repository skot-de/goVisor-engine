"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { EV, track } from "@/lib/analytics";
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

/* „19.08.2026" sagt nicht jedem sofort, dass das übermorgen ist.
 *
 * Sven: „nicht jeder hat direkt auf dem schirm das der 19. in zwei tagen ist. ist ein
 * guter absprungpunkt zu 'komm in die app, schau dir die analyse an und bewirb dich'."
 *
 * Gerechnet wird beim Anzeigen, nicht beim Erzeugen: `outreach.json` ist statisch und
 * liegt Wochen im Deploy. Eine eingefrorene Restlaufzeit wäre irgendwann eine Lüge. */
function restTage(iso?: string | null): number | null {
  if (!iso) return null;
  const tag = 86_400_000;
  const ziel = new Date(iso + "T00:00:00").getTime();
  const heute = new Date(new Date().toDateString()).getTime();
  return Math.round((ziel - heute) / tag);
}

function Restfrist({ iso }: { iso?: string | null }) {
  const { t } = useSprache();
  const d = restTage(iso);
  if (d === null) return null;
  if (d < 0) return <span className="lg-rest lg-rest-weg">{t("abgelaufen")}</span>;
  if (d === 0) return <span className="lg-rest lg-rest-eng">{t("heute")}</span>;
  return (
    <span className={`lg-rest${d <= 7 ? " lg-rest-eng" : ""}`}>
      {d === 1 ? t("noch 1 Tag") : `${t("noch")} ${d} ${t("Tage")}`}
    </span>
  );
}

function Vertragstabelle({ zeilen, spalte }: { zeilen: Zeile[]; spalte?: string }) {
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
            {/* „Endet" bei eigenen Vorhaben, „Frist" bei fremden Chancen — dieselbe
                Spalte trägt zwei verschiedene Aussagen, und die Überschrift muss sagen
                welche. Ein Datum ohne Bedeutung ist Zierrat. */}
            <th className="lg-r">{t(spalte ?? "Endet")}</th>
          </tr>
        </thead>
        <tbody>
          {zeilen.map((z, i) => (
            <tr key={i} className={z.art === "auslauf" ? "lg-auslauf" : ""}>
              <td className="lg-titel">{z.titel || t("(ohne Titel)")}</td>
              <td className="lg-buyer">{z.buyer}</td>
              {mitVolumen && <td className="lg-r lg-m">{z.vol ?? ""}</td>}
              <td className="lg-r lg-m">
                {z.ende ?? ""}
                <Restfrist iso={z.endeISO} />
              </td>
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
        {/* Das letzte Glied trug ein Fragezeichen. Gemeint war Ehrlichkeit: wie viele
            wirklich passen, haengt an Eignung und Kapazitaet und steht in keiner
            Bekanntmachung. Gelesen wurde etwas anderes. Wir belegen eine Seite lang, dass
            wir etwas ueber diese Firma wissen, und schliessen dann ausgerechnet bei der
            einen Zahl, die den Empfaenger interessiert, mit „?". Das entwertet alles
            davor.
            Jetzt steht dort, was wir tatsaechlich anbieten: die Auswahl uebernehmen wir.
            Kein erfundener Wert, aber auch keine Ratlosigkeit. */}
        <li className="lg-glied lg-offen">
          <span className="lg-n">→</span>
          <span className="lg-lb">{t("die Auswahl übernehmen wir")}</span>
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

/* DOKUMENTRAHMEN, NICHT APP-HUELLE.
 *
 * Vorher steckte die Seite in `AppTop` + `AppRail gesperrt`: links eine ausgegraute
 * Navigationsleiste, oben eine Suchzeile ohne Funktion. Der erste Eindruck war „du bist
 * ausgesperrt", nicht „wir haben etwas fuer dich vorbereitet" — bei einer KALTEN Ansprache
 * die falsche erste Sekunde.
 *
 * Jetzt gibt sich die Seite als das, was sie ist: eine vorbereitete Auswertung. Ein
 * Dokument mit Kopf, Absender und Kapiteln. Vertrauen durch Nuechternheit, nicht durch
 * Produktkulisse.
 */
function Rahmen({ children }: { children: React.ReactNode }) {
  const { t } = useSprache();
  return (
    <div className="dossier">
      <header className="ds-kopf">
        <span className="ds-marke">goVisor</span>
        {/* WER SCHREIBT DA UND WARUM. Bei einer kalten Ansprache ist das keine Fussnote:
            wer ungefragt eine Auswertung ueber die eigene Firma bekommt, fragt zuerst,
            woher die Daten stammen. Steht die Antwort erst am Seitenende, ist der
            Empfaenger vorher weg. */}
        <span className="ds-absender">
          {t("Wir werten öffentliche Vergabebekanntmachungen aus. Diese Seite entstand ohne euer Zutun und ohne Daten von euch.")}
        </span>
      </header>
      <main className="ds-blatt">{children}</main>
      <footer className="ds-fuss">
        <span>{t("goVisor · Auswertung öffentlicher Vergabedaten")}</span>
        <Link href="/impressum">{t("Impressum")}</Link>
      </footer>
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
  // Die Folge haengt am Abhaengigkeits-Baustein, gehoert aber in den Seitenkopf unter
  // den Kernbefund. Gesucht wird ueber das FELD, nicht ueber die Baustein-Id: welcher
  // Baustein eine Folge traegt, ist eine Sache des Generators.
  const folge = d.bausteine.find((b) => b.folge)?.folge ?? null;
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
  /* Die früheste noch offene Frist über ALLE Chancen-Bausteine. Sie trägt den Abschluss.
     Gesucht wird über die Zeilen, nicht über einen bestimmten Baustein: welcher Baustein
     Chancen mit Fristen liefert, ist eine Sache des Generators und darf hier nicht
     festverdrahtet sein. */
  /* Das „Leckerli" ist der Baustein mit konkreten Vorgängen. Gibt es keinen (bei den
     meisten Firmen), fällt der Abschnitt aus und die Seite bleibt trotzdem vollständig:
     erklären, zeigen was wir wissen, einladen. */
  const aufmacher = fuerEuch.find((b) => (b.zeilen?.length ?? 0) > 0) ?? null;
  const uebrigeFuerEuch = fuerEuch.filter((b) => b !== aufmacher);

  const naechste = fuerEuch
    .flatMap((b) => b.zeilen ?? [])
    .filter((z) => z.endeISO && (restTage(z.endeISO) ?? -1) >= 0)
    .sort((a, b) => (a.endeISO ?? "").localeCompare(b.endeISO ?? ""))[0] ?? null;

  return (
    <Rahmen>
      {/* ── 1. WAS GOVISOR IST ───────────────────────────────────────────────────
          Sven: „was ist, wenn man die seite so aufbaut, dass sie für sich selbst
          spricht. erklärt was goVisor ist, was es kann, was es bietet. dann ein
          leckerlie mit passenden ausschreibungen und ein bisschen schau mal was wir
          über dich wissen."

          Das löst, woran beide Vorfassungen scheiterten: eine Diagnose über das
          Unternehmen eines Fremden ist anmassend, eine Liste ohne Absender unerklärt.
          Wer kalt angeschrieben wird, muss zuerst wissen, WAS das hier ist. Erst danach
          ist die personalisierte Hälfte ein Beweis statt einer Zumutung. */}
      <div className="lg-hero">
        <h1 className="lg-h1">{t("Jede öffentliche Ausschreibung in Deutschland, gelesen und sortiert.")}</h1>
        <p className="lg-lede">{t("goVisor wertet die öffentlichen Vergabebekanntmachungen aus und sagt euch, welche davon zu eurem Betrieb passen. Ihr müsst sie nicht mehr selbst durchsehen.")}</p>
        <ul className="lg-kann">
          <li><b>{t("Passende Ausschreibungen finden")}</b>
            <span>{t("Zugeschnitten auf euer Fach, eure Gegend und eure Auftraggeber.")}</span></li>
          <li><b>{t("Fristen im Blick behalten")}</b>
            <span>{t("Ihr seht, wie lange ihr noch bieten könnt, bevor es zu spät ist.")}</span></li>
          <li><b>{t("Wissen, wer sonst bietet")}</b>
            <span>{t("Wer den Auftrag bisher hatte, wie oft gewechselt wurde, wie dünn der Wettbewerb ist.")}</span></li>
        </ul>
      </div>

      {/* ── 2. DAS LECKERLI ─────────────────────────────────────────────────────── */}
      {aufmacher && (
        <section className="lg-karte lg-aufmacher">
          <div className="lg-eyebrow">{t("Für euch schon gemacht")} · {t("Stand")} {d.stand}</div>
          <h2 className="lg-kt lg-kt-gross">{aufmacher.kern}</h2>
          <Vertragstabelle zeilen={aufmacher.zeilen!} spalte="Frist" />
          <div className="lg-grenze">{aufmacher.grenze}</div>
        </section>
      )}

      {/* ── 3. SCHAU MAL, WAS WIR ÜBER EUCH WISSEN ──────────────────────────────── */}
      {ueberEuch.length > 0 && (
        <section className="lg-ueber">
          <h2 className="lg-kt">{t("Das steht öffentlich über euch")}</h2>
          {d.kern && <p className="lg-kern-zwei">{d.kern}</p>}
          {folge && <p className="lg-folge">{folge}</p>}
          {kacheln(ueberEuch).length > 0 && <KennzahlenLeiste teile={kacheln(ueberEuch)} />}
          {karten(ueberEuch).map((b) => (
            <div className="lg-karte" key={b.id}>
              <h3 className="lg-kt3">{b.titel}</h3>
              {b.zeilen && b.zeilen.length > 0 && <Vertragstabelle zeilen={b.zeilen} />}
              {b.befund && <div className="lg-befund">{b.befund}</div>}
              {b.verschwiegen_text && <div className="lg-vergleich">{b.verschwiegen_text}</div>}
              <div className="lg-grenze">{b.grenze}</div>
            </div>
          ))}
        </section>
      )}

      {/* Der Rest als Ausblick auf die Tiefe im Konto, nicht als eigenes Kapitel. */}
      {uebrigeFuerEuch.map((b) => (
        <section className="lg-karte" key={b.id}>
          <h2 className="lg-kt">{b.titel}</h2>
          {b.trichter?.length
            ? <Kette stufen={b.trichter} satz={b.kette} />
            : (b.zahlen?.length ? <KennzahlenLeiste teile={[b]} />
                                : <div className="lg-grenze">{b.grenze}</div>)}
        </section>
      ))}

      {/* ── 4. DIE BRÜCKE ──────────────────────────────────────────────────────
          Sven: „fokus brücke schlagen um leute in die app zu bringen und pro/premium zu
          nutzen." Zwei Stufen, ehrlich getrennt: was das kostenlose Konto kann, und was
          Pro dazulegt. Die Angaben stammen aus dem Produkt (lib/redact.ts,
          app/onboarding), nicht aus einem Versprechen. */}
      <div className="lg-schluss">
        <h2>{t("Weiter im Konto")}</h2>
        {naechste && (
          <p className="lg-dringend">
            {t("Die nächste Frist läuft am")} <strong>{naechste.ende}</strong>{" "}
            {t("ab:")} {naechste.titel} ({naechste.buyer}).{" "}
            <Restfrist iso={naechste.endeISO} />
          </p>
        )}
        <div className="lg-stufen">
          <div className="lg-stufe">
            <div className="lg-stufe-k">{t("Kostenlos")}</div>
            <ul>
              <li>{t("Die volle Lead-Liste mit allen Eckdaten, dauerhaft")}</li>
              <li>{t("Fristen und Auftraggeber zu jeder Ausschreibung")}</li>
              <li>{t("Drei ausführliche Bewertungen je 30 Tage")}</li>
            </ul>
            <Link className="lg-cta" href={signup}
                  onClick={() => track(EV.LANDING_CTA, { token, erreicht: findenGemeldet.current })}>
              {t("Konto anlegen, kostenlos")}
            </Link>
            <div className="lg-klein">{t("Keine Zahlungsdaten. Keine Angaben, die nicht ohnehin öffentlich sind.")}</div>
          </div>
          <div className="lg-stufe lg-stufe-pro">
            <div className="lg-stufe-k">{t("Mit Pro")}</div>
            <ul>
              <li>{t("Jede Ausschreibung ausführlich bewertet, ohne Monatsgrenze")}</li>
              <li>{t("Wettbewerb und Strategie: wer bisher gewann, wie dünn das Feld ist")}</li>
              <li>{t("E-Mail, sobald etwas Passendes veröffentlicht wird")}</li>
            </ul>
            <div className="lg-klein">{t("Im Konto jederzeit umschaltbar. Erst ausprobieren, dann entscheiden.")}</div>
          </div>
        </div>
        {d.bereiche && d.bereiche.length > 0 && (
          <div className="lg-bereiche">{t("Danach offen:")} {d.bereiche.join(" · ")}</div>
        )}
      </div>
    </Rahmen>
  );
}
