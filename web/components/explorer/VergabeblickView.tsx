"use client";
import { useEffect, useMemo, useState } from "react";
import { useSprache } from "@/lib/i18n";

/* Vergabeblick — die Vergabestellen-Sicht (contracting_authority).
 * Liest denselben vorberechneten Bestand wie die Anbieter-Strategie (/api/strategie),
 * nur anders orientiert: die Stelle sieht IHRE eigene Zeile (Dashboard) + ihr Marktumfeld.
 * Rollen-agnostischer Kern (Architekturprinzip): identische Aggregate, gespiegelte Sicht.
 *
 * Phase 1: Onboarding-Picker + Dashboard aus echten Daten. Bereiche A/B/C/D folgen. */

type Quote = { pct: number; n: number; treffer: number };
type Stelle = {
  id: string; name: string; vergaben36: number; vergabenFeld: number; vergabenJahr: number;
  volEcht: number; volN: number; bieterMedian: number | null; bieterN: number;
  kmu: Quote; preis: Quote; wechsel: Quote; neuzugangJahr: number;
  neueAnbieter: number; anbieterGesamt: number; top1: number;
  top: { n: string; wins: number; pct: number }[];
  vorschau?: { titel: string | null; monate: number | null; ende: string | null }[];
  branche?: string;
};
type Anbieter = { id: string; name: string; wins: number; stellen: number; vol: number; trend: number };
type Feld = {
  cpv4: string; label: string; vergaben36: number; vergabenJahr: number; trend: number;
  bieterMedian: number | null; bieterN: number; kleinstesLos: number | null;
  wertband?: string | null; wertN?: number;
};

// #20 Wertplausibilität — die 7 Euro-Bänder (aus value_band_effektiv), aufsteigend.
const BANDS = ["<100k", "100-250k", "250-500k", "500k-1,3M", "1,3-5M", "5-25M", ">25M"];
const BAND_MAX = [1e5, 2.5e5, 5e5, 1.3e6, 5e6, 2.5e7, Infinity];
function bandOf(v: number): number { for (let i = 0; i < BAND_MAX.length; i++) if (v <= BAND_MAX[i]) return i; return BANDS.length - 1; }
type Strat = { stellen: Stelle[]; wettbewerb?: { anbieter?: Anbieter[] }; felder?: Feld[] };

const SEKTIONEN = [
  { key: "dashboard", label: "Dashboard", frage: "Wie steht meine Stelle da?" },
  { key: "markt", label: "Markterkundung", frage: "Wen erreiche ich?" },
  { key: "zuschnitt", label: "Zuschnitt", frage: "Wie bekomme ich mehr Bieter?" },
  { key: "controlling", label: "Controlling", frage: "Habe ich gut vergeben?" },
  { key: "pflichten", label: "Pflichten", frage: "KMU, Preis vs. Qualität" },
];

const nf = new Intl.NumberFormat("de-DE");
const eur = (v: number) =>
  v >= 1e9 ? (v / 1e9).toFixed(1).replace(".", ",") + " Mrd €"
  : v >= 1e6 ? (v / 1e6).toFixed(1).replace(".", ",") + " Mio €"
  : nf.format(Math.round(v)) + " €";

type T = (k: string, v?: Record<string, string | number>) => string;

/* Fallzahl-Schwelle (Ticket #10 §3.1): <3 Fälle → kein Prozentwert.
   `t` wird hereingereicht — die Funktion ist kein Hook-Kontext. */
function quoteText(q: Quote | undefined, t: T): { val: string; thin: boolean } {
  if (!q || q.n === 0) return { val: "—", thin: false };
  if (q.n < 3) return { val: t("{treffer} von {n}", { treffer: q.treffer, n: q.n }), thin: true };
  return { val: `${q.pct} %`, thin: q.n < 8 };
}

/* Benchmark-Vergleich: Ihre Stelle gegen den Median vergleichbarer Stellen.
   `label`/`note` kommen bereits übersetzt von der Aufrufstelle. */
function Bench({ label, mine, med, fmt, scale, goodHigh, note }: {
  label: string; mine: number | null; med: number | null;
  fmt: (v: number) => string; scale: number; goodHigh?: boolean; note?: string;
}) {
  const { t } = useSprache();
  const w = (v: number | null) => (v == null || !scale ? 0 : Math.max(2, Math.min(100, (v / scale) * 100)));
  const worse = mine != null && med != null && (goodHigh ? mine < med : mine > med);
  return (
    <div className="vb-bench">
      <div className="vb-bench-h">{label}</div>
      <div className="vb-bench-row">
        <span className="vb-bench-k">{t("Ihre Stelle")}</span>
        <div className="vb-bar"><i className={worse ? "warn" : "mine"} style={{ width: w(mine) + "%" }} /></div>
        <span className={`vb-bench-v ${worse ? "warn" : ""}`}>{mine != null ? fmt(mine) : "—"}</span>
      </div>
      <div className="vb-bench-row">
        <span className="vb-bench-k">{t("Marktüblich")}</span>
        <div className="vb-bar"><i className="med" style={{ width: w(med) + "%" }} /></div>
        <span className="vb-bench-v">{med != null ? fmt(med) : "—"}</span>
      </div>
      {note && <p className="vb-note">{note}</p>}
    </div>
  );
}

export function VergabeblickView() {
  const { t } = useSprache();
  const [strat, setStrat] = useState<Record<string, Strat> | null>(null);
  const [branche, setBranche] = useState("it");
  const [stelleId, setStelleId] = useState<string | null>(null);
  const [sektion, setSektion] = useState("dashboard");
  const [suche, setSuche] = useState("");
  // Ausschreibungscheck (B.1) — Entwurfs-Eckdaten
  const [ckFeld, setCkFeld] = useState("");
  const [ckLose, setCkLose] = useState(1);
  const [ckBuerg, setCkBuerg] = useState(false);
  const [ckPreis, setCkPreis] = useState(false);
  const [ckUmsatz, setCkUmsatz] = useState(0); // #21 geforderter Mindestjahresumsatz in Mio €
  const [ckReferenzen, setCkReferenzen] = useState(0); // #21 geforderte Referenzanzahl
  const [ckISO, setCkISO] = useState(false); // #21 ISO 27001 zwingend (Datenlage dünn)
  const [ckWert, setCkWert] = useState(""); // #20 eigener Schätzwert (€)
  // Ticket #23 §B.2 — Entwurf mitprüfen: Nachweisdichte gegen den Korpus-Median
  const [draftNw, setDraftNw] = useState<{ count: number; median: number | null } | null>(null);
  const [draftBusy, setDraftBusy] = useState(false);

  useEffect(() => {
    fetch("/api/strategie").then((r) => r.json()).then(setStrat).catch(() => {});
  }, []);

  const alleStellen = useMemo(() => {
    if (!strat) return [];
    // Stellen über alle Branchen, nach Vergabevolumen; Duplikate je id zusammenführen (größte Zeile).
    const byId = new Map<string, Stelle & { branche: string }>();
    for (const [br, d] of Object.entries(strat)) {
      for (const s of d.stellen || []) {
        const prev = byId.get(s.id);
        if (!prev || s.vergaben36 > prev.vergaben36) byId.set(s.id, { ...s, branche: br });
      }
    }
    return [...byId.values()].sort((a, b) => b.volEcht - a.volEcht);
  }, [strat]);

  const stelle = useMemo(
    () => alleStellen.find((s) => s.id === stelleId) || null,
    [alleStellen, stelleId]
  );
  // Branchen-Marktdaten der gewählten Stelle (Anbieter-Landschaft + Felder für Bereich A).
  const markt = useMemo(
    () => (stelle?.branche && strat ? strat[stelle.branche] : null),
    [stelle, strat]
  );

  const treffer = useMemo(() => {
    const q = suche.trim().toLowerCase();
    if (!q) return alleStellen.slice(0, 8);
    return alleStellen.filter((s) => s.name.toLowerCase().includes(q)).slice(0, 8);
  }, [alleStellen, suche]);

  if (!strat) return <div className="vb-load">{t("Lade Marktdaten …")}</div>;

  // ── Onboarding: Stelle wählen ──────────────────────────────────────────
  if (!stelle) {
    return (
      <div className="vb-wrap">
        <a className="vb-toswitch vb-toswitch-top" href="/leads">↔ {t("Zur Anbieter-Sicht")}</a>
        <div className="vb-onboard">
          <h2>{t("Vergabeblick")}</h2>
          <p className="vb-lead">
            {t("Der Blick Ihrer Vergabestelle auf den eigenen Markt — wen Sie erreichen, wie Sie mehr Bieter bekommen, ob Sie marktüblich vergeben. Wählen Sie zuerst Ihre Stelle.")}
          </p>
          <input className="vb-search" autoFocus placeholder={t("Ihre Vergabestelle suchen …")}
            value={suche} onChange={(e) => setSuche(e.target.value)} />
          <div className="vb-picklist">
            {treffer.map((s) => (
              <button key={s.id} className="vb-pick" onClick={() => setStelleId(s.id)}>
                <span className="vb-pick-n">{s.name}</span>
                <span className="vb-pick-m">{t("{n} Vergaben · {vol}", { n: nf.format(s.vergaben36), vol: eur(s.volEcht) })}
                  {s.id.startsWith("unresolved:") && <span className="vb-frag" title={t("Diese Stelle liegt in den Daten fragmentiert vor — wir zeigen den größten zusammengeführten Teil, nicht garantiert die volle Historie.")}> · {t("Teilbild")}</span>}
                </span>
              </button>
            ))}
            {!treffer.length && <div className="vb-empty">{t("Keine Stelle gefunden. Öffentliche Stellen liegen oft fragmentiert vor — versuchen Sie einen kürzeren Namensteil.")}</div>}
          </div>
        </div>
      </div>
    );
  }

  // ── Hauptsicht ─────────────────────────────────────────────────────────
  const bieterRot = stelle.bieterMedian != null && stelle.bieterMedian < 2.5;
  const kmuQ = quoteText(stelle.kmu, t);
  const preisQ = quoteText(stelle.preis, t);
  const wechselQ = quoteText(stelle.wechsel, t);

  return (
    <div className="vb-wrap">
      <header className="vb-head">
        <div>
          <span className="vb-eyebrow">{t("Vergabeblick")}</span>
          <h2>{stelle.name}</h2>
        </div>
        <div className="vb-head-actions">
          <a className="vb-toswitch" href="/leads">↔ {t("Anbieter-Sicht")}</a>
          <button className="vb-switch" onClick={() => { setStelleId(null); setSuche(""); }}>{t("Stelle wechseln")}</button>
        </div>
      </header>

      <nav className="vb-nav">
        {SEKTIONEN.map((s) => (
          <button key={s.key} className={`vb-nav-i ${sektion === s.key ? "on" : ""}`}
            onClick={() => setSektion(s.key)}>{t(s.label)}</button>
        ))}
      </nav>

      {sektion === "dashboard" ? (
        <div className="vb-main">
          <p className="vb-frage">{t("Wie steht Ihre Stelle da? — rollierend 36 Monate, alle Werte mit Fallzahl.")}</p>
          <div className="vb-tiles">
            <div className="vb-tile">
              <span className="vb-t-num">{nf.format(stelle.vergaben36)}</span>
              <span className="vb-t-lbl">{t("Vergaben (36 Mon.)")}</span>
              <span className="vb-t-sub">{t("{n}/Jahr", { n: Math.round(stelle.vergabenJahr) })}</span>
            </div>
            <div className={`vb-tile ${bieterRot ? "risk" : ""}`}>
              <span className="vb-t-num">{stelle.bieterMedian != null ? stelle.bieterMedian.toLocaleString("de-DE") : "—"}</span>
              <span className="vb-t-lbl">{t("Ø Bieter je Verfahren")}</span>
              <span className="vb-t-sub">{bieterRot ? t("⚠ Ein-Bieter-Gefahr") : t("aus {n} Losen", { n: nf.format(stelle.bieterN) })}</span>
            </div>
            <div className="vb-tile">
              <span className={`vb-t-num ${kmuQ.thin ? "thin" : ""}`}>{kmuQ.val}</span>
              <span className="vb-t-lbl">{t("KMU-Anteil")}</span>
              <span className="vb-t-sub">{kmuQ.thin ? t("dünn · {n} Fälle", { n: stelle.kmu?.n ?? 0 }) : t("der Zuschläge")}</span>
            </div>
            <div className="vb-tile">
              <span className={`vb-t-num ${preisQ.thin ? "thin" : ""}`}>{preisQ.val}</span>
              <span className="vb-t-lbl">{t("Rein über Preis")}</span>
              <span className="vb-t-sub">{t("niedrigster Preis entscheidet")}</span>
            </div>
            <div className="vb-tile">
              <span className={`vb-t-num ${wechselQ.thin ? "thin" : ""}`}>{wechselQ.val}</span>
              <span className="vb-t-lbl">{t("Wechselquote")}</span>
              <span className="vb-t-sub">{wechselQ.thin ? t("dünn · {n} Fälle", { n: stelle.wechsel?.n ?? 0 }) : t("anderer Gewinner bei Nachfolge")}</span>
            </div>
            <div className="vb-tile">
              <span className="vb-t-num">{Math.round(stelle.neuzugangJahr)}</span>
              <span className="vb-t-lbl">{t("Neuzugänge/Jahr")}</span>
              <span className="vb-t-sub">{t("Firmen mit Erstzuschlag")}</span>
            </div>
          </div>

          {stelle.top?.length > 0 && (
            <div className="vb-top">
              <h4>{t("Stärkste Anbieter bei Ihnen")}</h4>
              <div className="vb-toplist">
                {stelle.top.slice(0, 5).map((w, i) => (
                  <div className="vb-toprow" key={i}>
                    <span className="vb-top-r">#{i + 1}</span>
                    <span className="vb-top-n">{w.n}</span>
                    <span className="vb-top-w">{t("{n} Zuschläge · {pct} %", { n: nf.format(w.wins), pct: w.pct })}</span>
                  </div>
                ))}
              </div>
              <p className="vb-note">{t("Faktische Zuschlagszahlen, keine Wertung. Anbieter mit unsicherer Auflösung sind ausgeschlossen, nicht als „Sonstige\" gebündelt.")}</p>
            </div>
          )}
        </div>
      ) : sektion === "markt" ? (
        <div className="vb-main">
          <p className="vb-frage">{t("Wen erreichen Sie? — Ihr Anbieter-Umfeld und die Wettbewerbsdichte in Ihren Feldern.")}</p>

          {/* A.4 Markt-Vitalität */}
          {(() => {
            const w = stelle.wechsel;
            if (!w || w.n < 3) return null;
            const retention = 100 - w.pct;
            const vals = (markt?.stellen || []).filter((s) => s.wechsel && s.wechsel.n >= 3)
              .map((s) => 100 - s.wechsel.pct).sort((a, b) => a - b);
            const feldMed = vals.length ? vals[Math.floor(vals.length / 2)] : null;
            const fest = retention >= 60;
            return (
              <div className={`vb-vital ${fest ? "risk" : ""}`}>
                <span className="vb-vital-k">{t("Markt-Vitalität")}</span>
                <p><b>{t("Bei Ihren Nachfolgevergaben gewinnt zu {pct} % wieder derselbe Anbieter.", { pct: retention })}</b>
                  {feldMed != null && <> {t("Marktüblich in Ihrer Branche: {pct} %.", { pct: feldMed })}</>}
                  {fest ? ` ${t("Das ist festgefahren — hier lohnt aktive Marktansprache.")}` : ` ${t("Ihr Markt bewegt sich.")}`}</p>
                {stelle.top1 != null && <p className="vb-note">{t("Ihr stärkster Anbieter hält {pct} % aller Ihrer Vergaben (Konzentration).", { pct: stelle.top1 })}</p>}
              </div>
            );
          })()}

          {/* A.2 Wettbewerbsdichte */}
          {markt?.felder?.length ? (
            <>
              <h4 className="vb-h">{t("Wettbewerbsdichte je Feld")}</h4>
              <div className="vb-felder">
                {markt.felder.slice(0, 12).map((f) => {
                  const bm = f.bieterMedian;
                  const amp = bm == null ? "" : bm < 2.5 ? "risk" : bm < 4 ? "flag" : "ok";
                  return (
                    <div className="vb-feld" key={f.cpv4}>
                      <span className={`vb-amp ${amp}`} title={amp === "risk" ? t("Monopol-Gefahr") : amp === "flag" ? t("dünner Wettbewerb") : t("gesunder Wettbewerb")} />
                      <span className="vb-feld-l">{f.label}</span>
                      <span className="vb-feld-b">{t("Ø {n} Bieter", { n: bm != null ? bm.toLocaleString("de-DE") : "—" })}</span>
                      <span className="vb-feld-v">{t("{n}/Jahr", { n: Math.round(f.vergabenJahr) })}</span>
                      <span className={`vb-feld-t ${f.trend > 0 ? "up" : f.trend < 0 ? "down" : ""}`}>{f.trend > 0 ? "+" : ""}{f.trend} %</span>
                    </div>
                  );
                })}
              </div>
              <p className="vb-note">{t("Ampel nach Ø Bieterzahl: rot = Monopol-Gefahr (< 2,5), gelb = dünn, grün = gesund. Aus entschiedenen Vergaben des Feldes.")}</p>
            </>
          ) : null}

          {/* A.1 Anbieter-Landschaft */}
          {markt?.wettbewerb?.anbieter?.length ? (
            <>
              <h4 className="vb-h">{t("Aktive Anbieter in Ihrem Markt")}</h4>
              <div className="vb-anb">
                <div className="vb-anb-h"><span>{t("Anbieter")}</span><span>{t("Zuschläge")}</span><span>{t("Stellen")}</span><span>{t("Volumen")}</span><span>{t("Trend")}</span></div>
                {markt.wettbewerb.anbieter.slice(0, 15).map((a) => {
                  const beiMir = stelle.top?.some((w) => w.n === a.name);
                  return (
                    <div className={`vb-anb-r ${beiMir ? "mine" : ""}`} key={a.id}>
                      <span className="vb-anb-n">{a.name}{beiMir && <span className="vb-mine-tag">{t("bei Ihnen")}</span>}</span>
                      <span className="vb-anb-w">{nf.format(a.wins)}</span>
                      <span className="vb-anb-s">{nf.format(a.stellen)}</span>
                      <span className="vb-anb-v">{eur(a.vol)}</span>
                      <span className={`vb-anb-t ${a.trend > 0 ? "up" : a.trend < 0 ? "down" : ""}`}>{a.trend > 0 ? "+" : ""}{a.trend} %</span>
                    </div>
                  );
                })}
              </div>
              <p className="vb-note">{t("Marktweite Zuschlagszahlen (36 Mon.), gruppen-bewusst aufgelöst. „bei Ihnen\" = auch unter Ihren Top-Anbietern.")}</p>
            </>
          ) : null}
        </div>
      ) : sektion === "controlling" ? (
        <div className="vb-main">
          <p className="vb-frage">{t("Haben Sie marktüblich vergeben? — Ihre Werte gegen den Median vergleichbarer Stellen Ihrer Branche.")}</p>
          {(() => {
            const med = (pick: (s: Stelle) => number | null | undefined) => {
              const v = (markt?.stellen || []).map(pick).filter((x): x is number => x != null).sort((a, b) => a - b);
              return v.length ? v[Math.floor(v.length / 2)] : null;
            };
            const bieterMed = med((s) => s.bieterMedian);
            const volMed = med((s) => (s.volN >= 3 ? s.volEcht : null));
            return (
              <>
                <Bench label={t("Ø Bieter je Verfahren")} mine={stelle.bieterMedian} med={bieterMed}
                  fmt={(v) => (v != null ? v.toLocaleString("de-DE") : "—")} scale={Math.max(stelle.bieterMedian || 0, bieterMed || 0, 5)}
                  goodHigh note={t("Mehr Bieter = mehr Wettbewerb = bessere Angebote. Unter Median bedeutet: Sie erreichen weniger Markt als vergleichbare Stellen.")} />
                <Bench label={t("Vergabevolumen (belegt, 36 Mon.)")} mine={stelle.volEcht} med={volMed}
                  fmt={eur} scale={Math.max(stelle.volEcht, volMed || 0)}
                  note={t("Nur veröffentlichte Auftragswerte — die tatsächliche Kaufkraft liegt höher. Untergrenze, kein Vollbild.")} />
                <h4 className="vb-h">{t("Vergleichbare Stellen (Comps)")}</h4>
                <div className="vb-anb">
                  <div className="vb-anb-h" style={{ gridTemplateColumns: "1fr 90px 80px 90px" }}><span>{t("Stelle")}</span><span>{t("Vergaben")}</span><span>{t("Ø Bieter")}</span><span>{t("Volumen")}</span></div>
                  {(markt?.stellen || []).slice(0, 10).map((s) => (
                    <div className={`vb-anb-r ${s.id === stelle.id ? "mine" : ""}`} key={s.id} style={{ gridTemplateColumns: "1fr 90px 80px 90px" }}>
                      <span className="vb-anb-n">{s.name}{s.id === stelle.id && <span className="vb-mine-tag">{t("Sie")}</span>}</span>
                      <span className="vb-anb-w">{nf.format(s.vergaben36)}</span>
                      <span className="vb-anb-w">{s.bieterMedian != null ? s.bieterMedian.toLocaleString("de-DE") : "—"}</span>
                      <span className="vb-anb-v">{eur(s.volEcht)}</span>
                    </div>
                  ))}
                </div>
                <p className="vb-note">{t("Verteilung statt Punktschätzung — wo Ihre Stelle im Feld steht. Keine Wertung, nur Faktenvergleich.")}</p>
                {stelle.vorschau?.length ? (
                  <>
                    <h4 className="vb-h">{t("Ihre nächsten Auslauftermine")}</h4>
                    <div className="vb-vorschau">
                      {stelle.vorschau.map((v, i) => (
                        <div className="vb-vor-row" key={i}>
                          <span className={`vb-vor-m ${v.monate != null && v.monate <= 6 ? "soon" : ""}`}>{v.monate != null ? t("in {n} Mon.", { n: Math.round(v.monate) }) : "—"}</span>
                          <span className="vb-vor-t">{v.titel || t("(ohne Titel)")}</span>
                        </div>
                      ))}
                    </div>
                    <p className="vb-note">{t("Ihre eigenen bald auslaufenden Verträge (≤ 24 Mon.) — Planungshilfe für kommende Verfahren. Nur öffentlich sichtbare, oberschwellige.")}</p>
                  </>
                ) : null}
              </>
            );
          })()}
        </div>
      ) : sektion === "pflichten" ? (
        <div className="vb-main">
          <p className="vb-frage">{t("KMU-Förderung (§ 97 GWB) und wie stark Sie rein über den Preis vergeben — gegen vergleichbare Stellen.")}</p>
          {(() => {
            const med = (pick: (s: Stelle) => number | null | undefined) => {
              const v = (markt?.stellen || []).map(pick).filter((x): x is number => x != null).sort((a, b) => a - b);
              return v.length ? v[Math.floor(v.length / 2)] : null;
            };
            const kmuMed = med((s) => (s.kmu?.n >= 3 ? s.kmu.pct : null));
            const preisMed = med((s) => (s.preis?.n >= 3 ? s.preis.pct : null));
            const kmuThin = !stelle.kmu || stelle.kmu.n < 3;
            const preisThin = !stelle.preis || stelle.preis.n < 3;
            return (
              <>
                <Bench label={t("KMU-Anteil der Zuschläge")} mine={kmuThin ? null : stelle.kmu.pct} med={kmuMed}
                  fmt={(v) => (v != null ? v + " %" : "—")} scale={100} goodHigh
                  note={`${t("§ 97 GWB fordert Losaufteilung zur Mittelstandsförderung.")} ${kmuThin ? t("Zu wenige Fälle ({n}) für eine Quote.", { n: stelle.kmu?.n ?? 0 }) : t("Unter Median = Andockpunkt für die Begründungspflicht bei Nicht-Losaufteilung.")}`} />
                <Bench label={t("Rein über niedrigsten Preis")} mine={preisThin ? null : stelle.preis.pct} med={preisMed}
                  fmt={(v) => (v != null ? v + " %" : "—")} scale={100}
                  note={`${preisThin ? t("Zu wenige Fälle ({n}) für eine Quote.", { n: stelle.preis?.n ?? 0 }) + " " : ""}${t("Ehrlich als Preis-Benchmark benannt, nicht als Nachhaltigkeit — echte Nachhaltigkeitsdaten tragen in den Vergabedaten nicht (0–1,2 %).")}`} />
              </>
            );
          })()}
        </div>
      ) : (
        <div className="vb-main">
          <p className="vb-frage">{t("Prüfen Sie einen Entwurf gegen die Marktdaten — bevor das Verfahren startet. Ein Gutachten, kein Eingriff in Ihren Prozess.")}</p>
          <div className="vb-check-form">
            <label>{t("Feld (CPV)")}
              <select value={ckFeld} onChange={(e) => setCkFeld(e.target.value)}>
                <option value="">{t("— wählen —")}</option>
                {(markt?.felder || []).map((f) => <option key={f.cpv4} value={f.cpv4}>{f.label}</option>)}
              </select>
            </label>
            <label>{t("Geplante Lose")}
              <select value={ckLose} onChange={(e) => setCkLose(+e.target.value)}>
                <option value={1}>{t("1 Los (ganz)")}</option><option value={2}>{t("2 Lose")}</option><option value={3}>{t("3+ Lose")}</option>
              </select>
            </label>
            <label>{t("Mindestumsatz (Eignung)")}
              <select value={ckUmsatz} onChange={(e) => setCkUmsatz(+e.target.value)}>
                <option value={0}>{t("keiner")}</option><option value={1}>{t("1 Mio €/Jahr")}</option>
                <option value={5}>{t("5 Mio €/Jahr")}</option><option value={10}>{t("10 Mio €/Jahr")}</option>
              </select>
            </label>
            <label>{t("Referenzen (Eignung)")}
              <select value={ckReferenzen} onChange={(e) => setCkReferenzen(+e.target.value)}>
                <option value={0}>{t("keine")}</option><option value={2}>{t("2 vergleichbare")}</option>
                <option value={3}>{t("3 vergleichbare")}</option><option value={5}>{t("5 vergleichbare")}</option>
              </select>
            </label>
            <label className="vb-chk"><input type="checkbox" checked={ckISO} onChange={(e) => setCkISO(e.target.checked)} /> {t("ISO 27001 zwingend")}</label>
            <label>{t("Ihr Schätzwert (€)")}
              <input type="text" inputMode="numeric" placeholder={t("z. B. 300000")} value={ckWert}
                onChange={(e) => setCkWert(e.target.value.replace(/[^\d]/g, ""))} style={{ minWidth: "140px" }} />
            </label>
            <label className="vb-chk"><input type="checkbox" checked={ckBuerg} onChange={(e) => setCkBuerg(e.target.checked)} /> {t("Bürgschaft gefordert")}</label>
            <label className="vb-chk"><input type="checkbox" checked={ckPreis} onChange={(e) => setCkPreis(e.target.checked)} /> {t("Nur der Preis entscheidet")}</label>
          </div>
          <div className="vb-draft">
            <div>
              <span className="vb-draft-t">{t("Entwurf mitprüfen")} <span className="vb-draft-opt">— {t("optional")}</span></span>
              <span className="vb-draft-note">{t("Wir zählen die geforderten Nachweise und vergleichen sie mit ähnlichen Verfahren. Wird nur für diese Prüfung verarbeitet und danach verworfen.")}</span>
            </div>
            <button className="vb-draft-btn" disabled={draftBusy} onClick={() => {
              const inp = document.createElement("input");
              inp.type = "file"; inp.accept = ".zip,.pdf,.doc,.docx,.xls,.xlsx,.txt,.html";
              inp.onchange = async () => {
                const f = inp.files?.[0]; if (!f) return;
                setDraftBusy(true); setDraftNw(null);
                const fd = new FormData(); fd.append("file", f);
                try {
                  const r = await fetch(`/api/draft-check?branche=${encodeURIComponent(stelle.branche)}`, { method: "POST", body: fd });
                  const d = await r.json();
                  if (!d.error) setDraftNw({ count: d.nachweis_count, median: d.median ?? null });
                } catch { /* ignore */ }
                setDraftBusy(false);
              };
              inp.click();
            }}>{draftBusy ? t("Prüfe Entwurf …") : (draftNw ? t("Andere Datei") : t("Entwurfsdatei wählen"))}</button>
          </div>
          {(() => {
            const f = (markt?.felder || []).find((x) => x.cpv4 === ckFeld);
            if (!f) return <div className="vb-check-empty">{t("Wählen Sie ein Feld — dann prüfen wir Ihren Entwurf gegen vergleichbare Verfahren.")}</div>;
            const bm = f.bieterMedian;
            const bmT = bm != null ? bm.toLocaleString("de-DE") : t("wenigen");
            // `t` heißt hier bewusst NICHT `t` — das Feld des Hinweises heißt `text`,
            // sonst kollidiert es beim Schreiben mit der Übersetzungsfunktion.
            type H = { sev: "risk" | "warn" | "ok"; text: string };
            const hints: H[] = [];
            if (bm != null) hints.push({ sev: bm < 2.5 ? "risk" : bm < 4 ? "warn" : "ok",
              text: bm < 2.5
                ? t("Vergleichbare Verfahren in „{feld}\" erreichen im Median nur {n} Bieter — akute Ein-Bieter-Gefahr.", { feld: f.label, n: bmT })
                : t("Vergleichbare Verfahren erreichen im Median {n} Bieter.", { n: bmT }) });
            hints.push(ckLose === 1
              ? { sev: "warn", text: `${t("Mit nur 1 Los erreichen Sie tendenziell weniger Bieter.")}${f.kleinstesLos ? ` ${t("Vergleichbare Aufträge werden aufgeteilt — das kleinste Los liegt bei ~{wert}.", { wert: eur(f.kleinstesLos) })}` : ""} ${t("Eine Aufteilung öffnet das Verfahren für kleinere Anbieter.")}` }
              : { sev: "ok", text: t("Aufteilung in mehrere Lose erhöht erfahrungsgemäß Bieterzahl und KMU-Beteiligung.") });
            if (ckBuerg) hints.push({ sev: "warn", text: t("Eine Bürgschaft schließt kleinere und regionale Anbieter aus — bei im Median {n} Bietern im Feld erhöht das die Ein-Bieter-Gefahr.", { n: bmT }) });
            if (ckPreis) hints.push({ sev: "warn", text: t("Reine Preisvergabe schreckt spezialisierte Anbieter ab und senkt den Qualitätswettbewerb.") });
            // Ticket #23 §B.2 — Nachweisdichte des hochgeladenen Entwurfs gegen den Korpus-Median.
            if (draftNw && draftNw.median != null) {
              const over = draftNw.count > draftNw.median * 1.5;
              hints.push({ sev: over ? "warn" : "ok",
                text: over
                  ? t("Ihr Entwurf fordert {n} Nachweisarten — vergleichbare Verfahren im Median {median}. Hohe Nachweisdichte erhöht den Bearbeitungsaufwand und schreckt kleinere Anbieter ab.", { n: draftNw.count, median: draftNw.median })
                  : t("Ihr Entwurf fordert {n} Nachweisarten — im Rahmen des Üblichen (Feld-Median {median}).", { n: draftNw.count, median: draftNw.median }) });
            }
            const krit = hints.filter((h) => h.sev !== "ok").length;
            // B.2 Zuschnitt-Simulation: Feld-Median als Basis, Zuschnitt als DIREKTIONALE Richtung.
            let proj: number | null = bm;
            if (bm != null) {
              proj = bm;
              if (ckLose === 2) proj += 0.8; else if (ckLose >= 3) proj += 1.6;
              if (ckBuerg) proj -= 0.6;
              if (ckPreis) proj -= 0.3;
              if (ckUmsatz >= 10) proj -= 1.2; else if (ckUmsatz >= 5) proj -= 0.6; else if (ckUmsatz >= 1) proj -= 0.2;
              if (ckReferenzen >= 5) proj -= 0.6; else if (ckReferenzen >= 3) proj -= 0.3;
              if (ckISO) proj -= 0.4;   // benannte Zert-Pflicht verengt (grob, Datenlage dünn)
              if (draftNw && draftNw.median != null && draftNw.count > draftNw.median * 1.5) proj -= 0.5;
              proj = Math.max(1, Math.round(proj * 10) / 10);
            }
            return (
              <div className="vb-check-out">
                {proj != null && bm != null && (
                  <div className={`vb-proj ${proj < 2.5 ? "risk" : ""}`}>
                    <div className="vb-proj-nums">
                      <div className="vb-proj-cell"><span className="vb-proj-n">{proj.toLocaleString("de-DE")}</span><span className="vb-proj-l">{t("Bieter — Prognose Ihres Zuschnitts")}</span></div>
                      <span className="vb-proj-vs">↔</span>
                      <div className="vb-proj-cell"><span className="vb-proj-n muted">{bm.toLocaleString("de-DE")}</span><span className="vb-proj-l">{t("Feld-Median heute")}</span></div>
                    </div>
                    <p className="vb-note">{t("Richtwert, kein Versprechen: der Feld-Median ist gemessen, die Richtung Ihres Zuschnitts erfahrungsbasiert (Aufteilung öffnet, Bürgschaft/Umsatz/reiner Preis verengen). Die Deltas sind nicht pro Konfiguration gemessen.")}</p>
                  </div>
                )}
                <div className={`vb-check-sum ${krit >= 2 ? "risk" : krit ? "warn" : "ok"}`}>
                  {krit
                    ? (krit > 1
                       ? t("{n} Hinweise, die Ihre Bieterzahl senken können", { n: krit })
                       : t("{n} Hinweis, der Ihre Bieterzahl senken kann", { n: krit }))
                    : t("Keine kritischen Hinweise — der Zuschnitt sieht wettbewerbsoffen aus.")}
                </div>
                {hints.map((h, i) => <div className={`vb-hint ${h.sev}`} key={i}><span className="vb-hint-i" />{h.text}</div>)}
                {(ckUmsatz > 0 || ckReferenzen > 0 || ckISO) && markt?.wettbewerb?.anbieter?.length ? (() => {
                  // #21 Eignungs-Angemessenheit: Anteil erfüllender Anbieter je Kriterium UND kumulativ.
                  const anb = markt!.wettbewerb!.anbieter!;
                  const N = anb.length;
                  if (N < 8) return (
                    <div className="vb-eignung"><div className="vb-eig-h">{t("Eignungswirkung")}</div>
                      <p className="vb-note">{t("Zu wenige aufgelöste Anbieter im Marktausschnitt ({n}) für eine belastbare Eignungswirkung.", { n: N })}</p></div>
                  );
                  const dots = (pct: number) => { const f2 = Math.max(0, Math.min(5, Math.round(pct / 20))); return "●".repeat(f2) + "○".repeat(5 - f2); };
                  // Belastbare Kriterien (generisch): Umsatz (3-J-Volumen ≈ 3× Jahresumsatz), Referenzen (Zuschlagszahl).
                  const krit: { label: string; pred: (a: Anbieter) => boolean; pct: number }[] = [];
                  if (ckUmsatz > 0) { const pred = (a: Anbieter) => a.vol >= ckUmsatz * 1e6 * 3; krit.push({ label: t("Mindestumsatz {n} Mio €", { n: ckUmsatz }), pred, pct: Math.round(100 * anb.filter(pred).length / N) }); }
                  if (ckReferenzen > 0) { const pred = (a: Anbieter) => a.wins >= ckReferenzen; krit.push({ label: t("{n} vergleichbare Referenzen", { n: ckReferenzen }), pred, pct: Math.round(100 * anb.filter(pred).length / N) }); }
                  // Kumulativ: Anbieter, die ALLE belastbaren Kriterien erfüllen (ISO bleibt draußen — dünn).
                  const alle = krit.length ? anb.filter((a) => krit.every((k) => k.pred(a))) : anb;
                  const kombPct = Math.round(100 * alle.length / N);
                  const med = f.bieterMedian;
                  const eng = (krit.length > 0 && kombPct < 40) || (med != null && alle.length <= Math.ceil(med));
                  return (
                    <div className={`vb-eignung ${eng ? "warn" : ""}`}>
                      <div className="vb-eig-h">{t("Eignungswirkung — wie viele Anbieter erfüllen?")}</div>
                      <table className="vb-eig-tab"><tbody>
                        {krit.map((k) => (
                          <tr key={k.label}><td>{k.label}</td><td className="vb-dots">{dots(k.pct)}</td>
                            <td>~{k.pct} %{k.pct < 15 ? <b className="vb-eng"> {t("⚠ stark einschränkend")}</b> : null}</td></tr>
                        ))}
                        {ckISO && <tr><td>{t("ISO 27001 zwingend")}</td><td className="vb-dots">—</td><td><i>{t("Datenlage dünn — nicht belastbar quantifiziert")}</i></td></tr>}
                      </tbody></table>
                      {krit.length > 0 && (
                        <div className="vb-eig-komb">{t("Kombiniert erfüllen alle")} {krit.length > 1 ? t("{n} Kriterien", { n: krit.length }) : t("das Kriterium")}:
                          <b> ~{t("{n} Anbieter", { n: alle.length })}</b> ({kombPct} %){med != null ? ` · ${t("Median-Bieterfeld: {n}", { n: med })}` : ""}</div>
                      )}
                      <p>{eng
                        ? t("Jede Hürde einzeln wirkt harmlos — zusammen bleiben wenige Anbieter. Das erhöht die Ein-Bieter-Gefahr.")
                        : t("Der Markt bleibt auch kumulativ breit genug.")}</p>
                      <p className="vb-note">{t("Umsatz-/Referenz-Anteile aus 3-Jahres-Auftragsvolumen bzw. Zuschlagszahl der {n} aktiven Anbieter (Größen-/Erfahrungs-Proxy, kein bilanzieller Umsatz). Benannte Zertifikate: Datenlage dünn (0,1–0,4 %), hier nicht quantifiziert. Faktische Marktwirkung, keine Weglass-Empfehlung.", { n: N })}</p>
                    </div>
                  );
                })() : null}
                {ckWert && f.wertband && (f.wertN ?? 0) >= 3 ? (() => {
                  const v = parseInt(ckWert, 10);
                  const myBand = bandOf(v), fieldBand = BANDS.indexOf(f.wertband!);
                  const thin = (f.wertN ?? 0) < 8;
                  const status = fieldBand < 0 ? "im" : myBand < fieldBand ? "unter" : myBand > fieldBand ? "über" : "im";
                  return (
                    <div className={`vb-wert ${status !== "im" ? "warn" : ""}`}>
                      <div className="vb-eig-h">{t("Wert-Plausibilität")}</div>
                      <div className="vb-wert-rows">
                        <div><span>{t("Ihr Schätzwert")}</span><b>{eur(v)}</b></div>
                        <div><span>{t("Vergleichbare Verfahren")}</span><b>{t("Band {band} €", { band: f.wertband! })}</b> <i>(n={f.wertN}{thin ? `, ${t("dünn")}` : ""})</i></div>
                      </div>
                      {status === "unter" && <p className="vb-wert-warn">⚠ {t("Ihr Schätzwert liegt")} <b>{t("unter")}</b> {t("dem üblichen Band — prüfen, ob er das Verfahren trägt, sonst Aufhebungsrisiko.")}</p>}
                      {status === "über" && <p className="vb-wert-warn">{t("Ihr Schätzwert liegt")} <b>{t("über")}</b> {t("dem üblichen Band — plausibel, ggf. Schwellenwerte/Verfahrensart prüfen.")}</p>}
                      {status === "im" && <p>{t("Ihr Schätzwert liegt im üblichen Band — plausibel.")}</p>}
                      <p className="vb-note">{t("Nur Bandorientierung, kein Punktpreis (Wertdaten sind dünn). Keine Preisorientierung.")}</p>
                    </div>
                  );
                })() : ckWert ? <div className="vb-wert"><p className="vb-note">{t("Zu wenige vergleichbare Verfahren mit echtem Wert in diesem Feld für eine belastbare Bandeinordnung.")}</p></div> : null}
                <p className="vb-note">{t("Grundlage: entschiedene Vergaben des Feldes (36 Mon.). Faktische Marktbeobachtung, kein Eingriff ins laufende Verfahren.")}</p>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
