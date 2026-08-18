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
    Vierter Anlauf, und der letzte Umbau kam vom Aussehen: die Stufen standen als
    gleich grosse Kästchen nebeneinander und sahen deshalb aus wie eine Aufzählung.
    Ein Trichter, dessen Stufen gleich breit sind, verschenkt seine einzige Aussage.

    Jetzt trägt die BREITE die Zahl — logarithmisch, weil 8.297 zu 35 linear ein
    unsichtbares letztes Glied ergäbe (0,4 % Breite). Die kleinste Stufe behält
    deshalb einen Mindestanteil; die Reihenfolge bleibt in jedem Fall ablesbar.
  */
  const max = Math.max(...stufen.map((s) => s.n), 1);
  const breite = (n: number) =>
    Math.max(14, Math.round((Math.log10(Math.max(n, 1)) / Math.log10(max)) * 100));
  return (
    <div className="lg-kettewrap">
      {satz && <p className="lg-kettesatz">{satz}</p>}
      <ol className="lg-kette">
        {stufen.map((s, i) => (
          <li className="lg-glied" key={i}>
            <div className="lg-glied-bar" style={{ width: `${breite(s.n)}%` }}>
              <span className="lg-n">{s.n.toLocaleString("de-DE")}</span>
            </div>
            <span className="lg-lb">{s.label}</span>
            {s.hinweis && <span className="lg-hw">{s.hinweis}</span>}
          </li>
        ))}
        <li className="lg-glied lg-offen">
          <div className="lg-glied-bar" style={{ width: "10%" }}>
            <span className="lg-n">→</span>
          </div>
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
  const kette = fuerEuch.find((b) => (b.trichter?.length ?? 0) > 0) ?? null;
  const uebrigeFuerEuch = fuerEuch.filter((b) => b !== aufmacher);

  const slides = ["was", aufmacher && "fuer", ueberEuch.length > 0 && "ueber",
                  kette && "markt", "konto"].filter(Boolean) as string[];
  const [aktiv, setAktiv] = useState(slides[0]);

  /* Fortschrittsanzeige: welcher Abschnitt gerade im Bild ist. Ein Beobachter statt
     eines Scroll-Zaehlers — der haette bei jedem Pixel gerechnet. */
  useEffect(() => {
    const ziele = Array.from(document.querySelectorAll<HTMLElement>("[data-slide]"));
    if (!ziele.length) return;
    const beob = new IntersectionObserver(
      (eintraege) => {
        const sichtbar = eintraege.filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (sichtbar) setAktiv((sichtbar.target as HTMLElement).dataset.slide!);
      },
      { threshold: [0.35, 0.6] });
    ziele.forEach((z) => beob.observe(z));
    return () => beob.disconnect();
  }, [slides.length]);

  const naechste = fuerEuch
    .flatMap((b) => b.zeilen ?? [])
    .filter((z) => z.endeISO && (restTage(z.endeISO) ?? -1) >= 0)
    .sort((a, b) => (a.endeISO ?? "").localeCompare(b.endeISO ?? ""))[0] ?? null;

  return (
    <Rahmen>
      {/* ── DIE SEITE ALS DECK ────────────────────────────────────────────────────
          Sven: „was ist wenn man das zum durchklicken macht? wie ein slide deck?"

          Übernommen ist die REGEL, nicht die Klickmechanik: ein Gedanke pro Bildschirm,
          und jeder Abschnitt darf kräftig sein, weil nichts mehr mit ihm konkurriert.
          Genau daran scheiterten die Vorfassungen („nichts hervorgehoben, einfach
          überladen").

          Eingerastet wird beim SCROLLEN, nicht geklickt. Bei einer kalten Ansprache ist
          ein Klick eine Entscheidung und Scrollen keine: wer den Link eines Fremden
          öffnet, arbeitet sich nicht durch ein Deck, um herauszufinden, ob es sich lohnt.
          Ausserdem bliebe das Leckerli hinter Slide 1 verborgen, und ein weitergeleiteter
          Link landete wieder am Anfang. `proximity` statt `mandatory`, damit ein
          Abschnitt, der höher als der Bildschirm ist, trotzdem frei scrollt. */}

      <div className="ds-fortschritt" aria-hidden="true">
        {slides.map((k) => <span key={k} className={k === aktiv ? "ds-an" : ""} />)}
      </div>

      {/* 1 — was das hier ist */}
      <section className="ds-slide" id="s-was" data-slide="was">
        <div className="ds-inhalt">
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
          {aufmacher && <div className="ds-weiter">{t("Für {firma} haben wir das schon gemacht", { firma: d.name })}</div>}
        </div>
      </section>

      {/* 2 — das Leckerli */}
      {aufmacher && (
        <section className="ds-slide ds-hell" id="s-fuer" data-slide="fuer">
          <div className="ds-inhalt">
            <div className="lg-eyebrow">{t("Für euch schon gemacht")} · {t("Stand")} {d.stand}</div>
            <div className="ds-kopfzeile">
              <div className="ds-zahl">{aufmacher.zeilen!.length}</div>
              <h2 className="lg-kt-gross">{aufmacher.kern}</h2>
            </div>
            <Vertragstabelle zeilen={aufmacher.zeilen!} spalte="Frist" />
            <div className="lg-grenze">{aufmacher.grenze}</div>
          </div>
        </section>
      )}

      {/* 3 — was öffentlich über sie dasteht */}
      {ueberEuch.length > 0 && (
        <section className="ds-slide ds-dunkel" id="s-ueber" data-slide="ueber">
          <div className="ds-inhalt">
            <div className="lg-eyebrow">{t("Das steht öffentlich über euch")}</div>
            {d.kern && <h2 className="lg-kt-gross">{d.kern}</h2>}
            {folge && <p className="lg-folge">{folge}</p>}
            {kacheln(ueberEuch).length > 0 && <KennzahlenLeiste teile={kacheln(ueberEuch)} />}
            {/* NUR der stärkste Befund. Alles Weitere ist der Grund für ein Konto —
                fünf Blöcke hintereinander waren wieder die Textwüste, nur weiter unten. */}
            {karten(ueberEuch).slice(0, 1).map((b) => (
              <div key={b.id}>
                {b.befund && <div className="lg-befund">{b.befund}</div>}
                <div className="lg-grenze">{b.grenze}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 4 — wie weit der Markt reicht */}
      {kette && (
        <section className="ds-slide" id="s-markt" data-slide="markt">
          <div className="ds-inhalt">
            <div className="lg-eyebrow">{t("Wie wir eingrenzen")}</div>
            <Kette stufen={kette.trichter!} satz={kette.kette} />
            <div className="lg-grenze">{kette.grenze}</div>
          </div>
        </section>
      )}

      {/* 5 — die Brücke */}
      <section className="ds-slide ds-hell" id="s-konto" data-slide="konto">
        <div className="ds-inhalt">
          <h2 className="lg-kt-gross">{t("Weiter im Konto")}</h2>
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
        </div>
      </section>
    </Rahmen>
  );
}
