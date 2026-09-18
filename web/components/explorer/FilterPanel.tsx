"use client";

import { useState } from "react";

import { useSprache } from "@/lib/i18n";

import { BRANCHEN } from "@/lib/explorerCore";
import { STAATEN } from "@/lib/staaten";
/* ⚠ Beschriftungen und Markenlogik liegen in Plain JS, damit der Waechter
 * `pruefe-filtermarken.mjs` die echte Funktion fahren kann (s. dortiger Kopf). */
import { PHASEN, HORIZONTE as _HORIZONTE, LEISTUNG, RAHMEN, BAND, ART, LAENDER,
         filterMarken as _filterMarken } from "@/lib/filterMarken.js";
export { LAENDER };
const HORIZONTE = _HORIZONTE as [number, string][];

export type FilterMarke = { schluessel: string; text: string; weg: Partial<Adv> };

/* ⚠ DIE TYPGRENZE STEHT HIER, DIE LOGIK IM JS-MODUL. Plain JS kennt die Literaltypen
 * von `Adv` nicht — `neu` kaeme als `string` zurueck statt als `"all" | "neu" | "folge"`,
 * und `setAdv` liesse sich damit nicht fuettern. Diese Huelle ist ausdruecklich KEINE
 * zweite Fassung der Logik: sie reicht durch. Wer hier etwas rechnet, hat den Grund fuer
 * die Aufteilung aufgehoben (s. Kopf von `lib/filterMarken.js`). */
export function filterMarken(
  a: Adv, segmente: Segment[],
  t: (k: string, v?: Record<string, string | number>) => string,
): FilterMarke[] {
  return _filterMarken(a, segmente, t) as FilterMarke[];
}

export type Adv = {
  phases: string[];                 // auslauf | f02 | f01 | award
  horizon: number | null;          // Monate: wann wird's relevant (Frist bzw. Vertragsende)
  cpvFields: string[];             // CPV4-Fachgebiete (Feinfilter im Grundraum)
  regionAxis: "perf" | "buyer";    // Leistungsort vs. Käufersitz
  regions: string[];               // NUTS1-Codes
  nationwide: boolean;             // bundesweit erbringbare mit einschließen
  buyer: string;                   // Vergabestelle (Teilstring)
  leistung: string[];              // dienst | liefer | bau
  art: string[];                   // Vertragsart: rahmen | einzel | wiederkehrend
  rahmen: string[];                // vgv | vob | uvgo | sektvo
  valMin: number | null;
  valMax: number | null;
  neu: "all" | "neu" | "folge";    // Wettbewerb: Neuvergabe / Folgevergabe
  wenigWettbewerb: boolean;        // zuletzt wenig Bieter (single-bidder-nah)
  aufwand: string[];               // niedrig | mittel | hoch
  buergschaft: "all" | "ja" | "nein";
  chance: string[];                // niedrig | mittel | hoch (Wechsel-Chance)
  relevanz: string[];              // niedrig | mittel | hoch (Profil-Relevanz, client-berechnet — braucht Profil)
  multiLot: boolean;
  hasDetail: boolean;              // nur mit ausführlicher Beschreibung
  unterlagen: boolean;             // nur mit Vergabeunterlagen-Link
  /** Nur Vorgaenge, deren Unterlagen WIR ausgewertet haben (Checkliste, K.-o.-Kriterien).
   *  ⚠ Nicht mit `unterlagen` verwechseln: einen LINK haben 97,3 % der Leads, eine
   *  AUSWERTUNG 9,4 %. Das eine siebt nichts, das andere ist das schaerfste Merkmal
   *  der Tabelle. */
  ausgewertet: boolean;
  staaten: string[];               // DACH-Vergabeland: DE | AT | CH (alle mit Daten)
};

export const emptyAdv: Adv = {
  phases: [], horizon: null, cpvFields: [], regionAxis: "perf", regions: [], nationwide: false,
  buyer: "", leistung: [], art: [], rahmen: [], valMin: null, valMax: null,
  neu: "all", wenigWettbewerb: false, aufwand: [], buergschaft: "all", chance: [], relevanz: [], multiLot: false,
  hasDetail: false, unterlagen: false, ausgewertet: false, staaten: [],
};

export function advCount(a: Adv): number {
  return (
    a.phases.length + (a.horizon != null ? 1 : 0) + a.cpvFields.length + a.regions.length + (a.nationwide ? 1 : 0) +
    (a.buyer.trim() ? 1 : 0) + a.leistung.length + a.art.length + a.rahmen.length +
    (a.valMin != null ? 1 : 0) + (a.valMax != null ? 1 : 0) +
    (a.neu !== "all" ? 1 : 0) + (a.wenigWettbewerb ? 1 : 0) + a.aufwand.length +
    (a.buergschaft !== "all" ? 1 : 0) + a.chance.length + a.relevanz.length + (a.multiLot ? 1 : 0) +
    (a.hasDetail ? 1 : 0) + (a.unterlagen ? 1 : 0) + (a.ausgewertet ? 1 : 0) + a.staaten.length
  );
}

export type Segment = { cpv4: string; label: string; n: number };


// DACH-Vergabeland — der Filter greift auf `l.land` (ExplorerShell).
// AT = offeneVergaben.at, CH = simap.ch. Die Liste stand hier ein zweites Mal; sie kommt
// jetzt aus `lib/staaten`, damit ein viertes Land nicht an einer von zwei Stellen fehlt.
// Sie steht bei den übrigen Importen oben.

const toggle = (arr: string[], v: string) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);
const parseEur = (s: string): number | null => {
  const n = parseFloat(s.replace(/[^\d]/g, ""));
  return isNaN(n) ? null : n;
};

/* ── Die Zahl am Chip ────────────────────────────────────────────────────────────────
 *
 * ⚠ NULL WIRD ANGEZEIGT, NICHT VERSTECKT. Ein Chip ohne Zahl sieht aus wie einer, dessen
 * Zahl noch laedt. „0" sagt dagegen genau das, wofuer die Zahlen da sind: hier gibt es
 * nichts, spar dir den Klick. Fehlt die Facette ganz (noch nicht gezaehlt), bleibt es leer.
 * Der Wert ist eine Auskunft, kein Teil der Beschriftung — deshalb `aria-hidden`. */
function Zahl({ n }: { n?: number }) {
  if (n == null) return null;
  return <span className="fp-chip-n" aria-hidden>{n.toLocaleString("de-DE")}</span>;
}

export function FilterPanel({
  open, adv, resultCount, segments, onChange, onClose, onReset,
  branche, profilBranche, brancheCounts, onSetBranche, onResetBranche,
  facetZahlen, ausgeblendetImTreffer, zeigeAusgeblendete, onToggleAusgeblendete,
  gespeicherteFilter, onFilterSpeichern, onFilterLaden, onFilterLoeschen,
}: {
  open: boolean; adv: Adv; resultCount: number; segments: Segment[];
  /** Je Facette und Wert: wie viele Treffer ergaebe dieser Chip STATT der aktuellen Wahl.
   *  Leer, solange nichts gezaehlt wurde — dann rendert `Zahl` nichts. */
  facetZahlen?: Record<string, Record<string, number>>;
  gespeicherteFilter?: { id: string; name: string; zustand: Record<string, unknown> }[];
  onFilterSpeichern?: (name: string) => void;
  onFilterLaden?: (f: { id: string; name: string; zustand: Record<string, unknown> }) => void;
  onFilterLoeschen?: (id: string) => void;
  ausgeblendetImTreffer?: number;
  zeigeAusgeblendete?: boolean;
  onToggleAusgeblendete?: () => void;
  onChange: (a: Adv) => void; onClose: () => void; onReset: () => void;
  // Grundraum: strukturell ein Filter (welcher Datenraum), deshalb hier statt im Header —
  // er wird aus dem Profil abgeleitet und ist kein Routine-Handgriff mehr.
  branche: string; profilBranche: string; brancheCounts: Record<string, number>;
  onSetBranche: (k: string) => void; onResetBranche: () => void;
}) {
  const { t, lang } = useSprache();
  const set = (patch: Partial<Adv>) => onChange({ ...adv, ...patch });
  /* ⚠ KEIN `prompt()`. Der Systemdialog ist auf dem iPad ein Fremdkoerper, laesst sich nicht
   * gestalten und bricht die Tastaturbedienung. Stattdessen ein Feld, das erst auf Klick
   * erscheint — und mit Enter speichert, weil sonst niemand den zweiten Knopf findet. */
  const [nameOffen, setNameOffen] = useState(false);
  const [name, setName] = useState("");
  function speichern() {
    const n = name.trim();
    if (!n) return;
    onFilterSpeichern?.(n);
    setName(""); setNameOffen(false);
  }
  const isPreset = adv.horizon != null && HORIZONTE.some(([m]) => m === adv.horizon);

  return (
    <>
      <div className={`fp-scrim ${open ? "on" : ""}`} onClick={onClose} aria-hidden />
      <aside className={`fp ${open ? "on" : ""}`} aria-label={t("Filter")} aria-hidden={!open}>
        <div className="fp-head">
          <span className="fp-title">{t("Filter")}</span>
          <button className="fp-x" onClick={onClose} aria-label={t("Schließen")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round"><path d="M6 6l12 12M18 6 6 18" /></svg>
          </button>
        </div>

        <div className="fp-body">
          <section className="fp-sec">
            <h5>
              {t("Grundraum")}
              <span className="fp-hint">
                {t(branche === profilBranche ? "aus eurem Profil abgeleitet" : "temporär gewechselt")}
              </span>
            </h5>
            {Object.entries(BRANCHEN as Record<string, string>).map(([k, v]) => (
              <label key={k} className="fp-check">
                <input type="radio" name="fp-branche" checked={branche === k} onChange={() => onSetBranche(k)} />
                <span>{t(v)}</span>
                <i className="fp-n">{brancheCounts[k] || 0}</i>
              </label>
            ))}
            {branche !== profilBranche ? (
              <button className="fp-mini" onClick={onResetBranche}>
                {t("Zurück zu {b}", { b: t((BRANCHEN as Record<string, string>)[profilBranche]) })}
              </button>
            ) : null}
          </section>

          {/* ── Gespeicherte Ansichten ──────────────────────────────────────────────
              Ganz oben, weil sie ein Sprungbrett sind: wer eine gespeicherte Sicht sucht,
              will nicht erst an allen Facetten vorbei. */}
          <section className="fp-sec">
            <h5>{t("Gespeicherte Ansichten")}</h5>
            {(gespeicherteFilter?.length ?? 0) > 0 && (
              <div className="fp-chips" style={{ marginBottom: 8 }}>
                {gespeicherteFilter!.map((f) => (
                  <span key={f.id} className="fp-gesp">
                    <button className="fp-chip" onClick={() => onFilterLaden?.(f)}>{f.name}</button>
                    <button className="fp-gesp-x" onClick={() => onFilterLoeschen?.(f.id)}
                            aria-label={t("Gespeicherte Ansicht löschen")} title={t("Gespeicherte Ansicht löschen")}>×</button>
                  </span>
                ))}
              </div>
            )}
            {nameOffen ? (
              <div className="fp-chips">
                <input className="fp-name" value={name} autoFocus maxLength={80}
                       placeholder={t("Name der Ansicht")}
                       onChange={(e) => setName(e.target.value)}
                       onKeyDown={(e) => { if (e.key === "Enter") speichern();
                                           if (e.key === "Escape") { setName(""); setNameOffen(false); } }} />
                <button className="fp-chip on" onClick={speichern}>{t("Sichern")}</button>
              </div>
            ) : (
              <button className="fp-chip" onClick={() => setNameOffen(true)}>
                {t("Diese Ansicht speichern")}
              </button>
            )}
          </section>

          {/* ⚠ GANZ OBEN, WEIL ER EINE LUECKE ERKLAERT. Wer etwas ausgeblendet hat, sieht
              danach weniger Treffer, als die Zahlen versprechen. Steht der Schalter unten,
              sucht er den Grund woanders. Erscheint nur, wenn es etwas auszublenden gibt. */}
          {(ausgeblendetImTreffer ?? 0) > 0 && (
            <section className="fp-sec">
              <label className="fp-check">
                <input type="checkbox" checked={!!zeigeAusgeblendete}
                       onChange={() => onToggleAusgeblendete?.()} />
                <span>{t("Ausgeblendete mitzeigen")}<Zahl n={ausgeblendetImTreffer} /></span>
              </label>
            </section>
          )}

          <section className="fp-sec">
            <h5>{t("Land")} <span className="fp-hint">{t("Vergabeland (DACH)")}</span></h5>
            {STAATEN.map(([v, l]) => (
              <label key={v} className="fp-check">
                <input type="checkbox" checked={adv.staaten.includes(v)} onChange={() => set({ staaten: toggle(adv.staaten, v) })} />
                <span>{t(l)}<Zahl n={facetZahlen?.staaten?.[v]} /></span>
              </label>
            ))}
          </section>

          <section className="fp-sec">
            <h5>{t("Phase")}</h5>
            {PHASEN.map(([v, l]) => (
              <label key={v} className="fp-check">
                <input type="checkbox" checked={adv.phases.includes(v)} onChange={() => set({ phases: toggle(adv.phases, v) })} />
                <span>{t(l)}<Zahl n={facetZahlen?.phases?.[v]} /></span>
              </label>
            ))}
          </section>

          <section className="fp-sec">
            <h5>{t("Frist / Vertragsende, in den nächsten …")}</h5>
            <div className="fp-chips">
              <button className={`fp-chip ${adv.horizon == null ? "on" : ""}`} onClick={() => set({ horizon: null })}>{t("egal")}</button>
              {HORIZONTE.map(([m, l]) => (
                <button key={m} className={`fp-chip ${adv.horizon === m ? "on" : ""}`} onClick={() => set({ horizon: m })}>{t(l)}</button>
              ))}
              <span className="fp-manual">
                {t("oder")}
                <input className="fp-in fp-mini" inputMode="numeric" placeholder="__"
                  defaultValue={isPreset ? "" : (adv.horizon ?? "")}
                  onChange={(e) => { const n = parseInt(e.target.value, 10); set({ horizon: isNaN(n) ? null : n }); }} />
                {t("Monate")}
              </span>
            </div>
          </section>

          {segments.length ? (
            <section className="fp-sec">
              <h5>{t("Fachgebiet")} <span className="fp-hint">{adv.cpvFields.length ? t("{n} gewählt", { n: adv.cpvFields.length }) : t("alle im Grundraum")}</span></h5>
              <div className="fp-seglist">
                {segments.map((s) => (
                  <label key={s.cpv4} className="fp-check">
                    <input type="checkbox" checked={adv.cpvFields.includes(s.cpv4)} onChange={() => set({ cpvFields: toggle(adv.cpvFields, s.cpv4) })} />
                    <span className="fp-seg-l">{s.label}</span>
                    <span className="fp-seg-n">{s.n}</span>
                  </label>
                ))}
              </div>
            </section>
          ) : null}

          <section className="fp-sec">
            <h5>{t("Region")}
              <span className="fp-axis">
                <button className={adv.regionAxis === "perf" ? "on" : ""} onClick={() => set({ regionAxis: "perf" })}>{t("Leistungsort")}</button>
                <button className={adv.regionAxis === "buyer" ? "on" : ""} onClick={() => set({ regionAxis: "buyer" })}>{t("Käufersitz")}</button>
              </span>
            </h5>
            <label className="fp-check">
              <input type="checkbox" checked={adv.nationwide} onChange={() => set({ nationwide: !adv.nationwide })} />
              <span>{t("Bundesweit erbringbare mit einschließen")}</span>
            </label>
            <div className="fp-grid2">
              {LAENDER.map(([code, name]) => (
                <label key={code} className="fp-check">
                  <input type="checkbox" checked={adv.regions.includes(code)} onChange={() => set({ regions: toggle(adv.regions, code) })} />
                  <span>{t(name)}</span>
                </label>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>{t("Vergabestelle")}</h5>
            <input className="fp-in" placeholder={t("Name enthält …")} value={adv.buyer} onChange={(e) => set({ buyer: e.target.value })} />
          </section>

          <section className="fp-sec">
            <h5>{t("Wettbewerb")}</h5>
            <div className="fp-chips">
              {(["all", "neu", "folge"] as const).map((k) => (
                <button key={k} className={`fp-chip ${adv.neu === k ? "on" : ""}`} onClick={() => set({ neu: k })}>
                  {t(k === "all" ? "alle" : k === "neu" ? "Neuvergabe (kein Amtsinhaber)" : "Folgevergabe")}
                </button>
              ))}
            </div>
            <label className="fp-check" style={{ marginTop: 8 }}>
              <input type="checkbox" checked={adv.wenigWettbewerb} onChange={() => set({ wenigWettbewerb: !adv.wenigWettbewerb })} />
              <span>{t("Nur mit wenig Wettbewerb (zuletzt ≤ 3 Bieter)")}</span>
            </label>
          </section>

          <section className="fp-sec">
            <h5>{t("Relevanz")} <span className="fp-hint">{t("Profil-Passung · braucht Profil")}</span></h5>
            <div className="fp-chips">
              {BAND.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.relevanz.includes(v) ? "on" : ""}`} onClick={() => set({ relevanz: toggle(adv.relevanz, v) })}>{t(l)}<Zahl n={facetZahlen?.relevanz?.[v]} /></button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>{t("Chance")} <span className="fp-hint">{t("Wechsel-Chance")}</span></h5>
            <div className="fp-chips">
              {BAND.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.chance.includes(v) ? "on" : ""}`} onClick={() => set({ chance: toggle(adv.chance, v) })}>{t(l)}<Zahl n={facetZahlen?.chance?.[v]} /></button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>{t("Aufwand")}</h5>
            <div className="fp-chips">
              {BAND.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.aufwand.includes(v) ? "on" : ""}`} onClick={() => set({ aufwand: toggle(adv.aufwand, v) })}>{t(l)}<Zahl n={facetZahlen?.aufwand?.[v]} /></button>
              ))}
            </div>
            <div className="fp-chips" style={{ marginTop: 8 }}>
              <span className="fp-hint" style={{ alignSelf: "center", marginRight: 4 }}>{t("Bürgschaft:")}</span>
              {(["all", "nein", "ja"] as const).map((k) => (
                <button key={k} className={`fp-chip ${adv.buergschaft === k ? "on" : ""}`} onClick={() => set({ buergschaft: k })}>
                  {t(k === "all" ? "egal" : k === "nein" ? "keine" : "gefordert")}
                </button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>{t("Leistungsart")}</h5>
            <div className="fp-chips">
              {LEISTUNG.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.leistung.includes(v) ? "on" : ""}`} onClick={() => set({ leistung: toggle(adv.leistung, v) })}>{t(l)}<Zahl n={facetZahlen?.leistung?.[v]} /></button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>{t("Vertragsart")}</h5>
            <div className="fp-chips">
              {ART.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.art.includes(v) ? "on" : ""}`} onClick={() => set({ art: toggle(adv.art, v) })}>{t(l)}<Zahl n={facetZahlen?.art?.[v]} /></button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>{t("Rechtsrahmen")}</h5>
            <div className="fp-chips">
              {RAHMEN.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.rahmen.includes(v) ? "on" : ""}`} onClick={() => set({ rahmen: toggle(adv.rahmen, v) })}>{t(l)}<Zahl n={facetZahlen?.rahmen?.[v]} /></button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>{t("Auftragswert (€)")}</h5>
            <div className="fp-range">
              <input className="fp-in" inputMode="numeric" placeholder={t("von")} defaultValue={adv.valMin ?? ""} onBlur={(e) => set({ valMin: parseEur(e.target.value) })} />
              <span>–</span>
              <input className="fp-in" inputMode="numeric" placeholder={t("bis")} defaultValue={adv.valMax ?? ""} onBlur={(e) => set({ valMax: parseEur(e.target.value) })} />
            </div>
          </section>

          <section className="fp-sec">
            <h5>{t("Weitere")}</h5>
            <label className="fp-check"><input type="checkbox" checked={adv.multiLot} onChange={() => set({ multiLot: !adv.multiLot })} /><span>{t("Nur mit mehreren Losen")}</span></label>
            <label className="fp-check"><input type="checkbox" checked={adv.hasDetail} onChange={() => set({ hasDetail: !adv.hasDetail })} /><span>{t("Nur mit ausführlicher Beschreibung")}</span></label>
            <label className="fp-check"><input type="checkbox" checked={adv.unterlagen} onChange={() => set({ unterlagen: !adv.unterlagen })} /><span>{t("Nur mit Link zu den Vergabeunterlagen")}</span></label>
            <label className="fp-check"><input type="checkbox" checked={adv.ausgewertet} onChange={() => set({ ausgewertet: !adv.ausgewertet })} /><span>{t("Nur mit ausgewerteten Unterlagen")}</span></label>
          </section>
        </div>

        <div className="fp-foot">
          <button className="fp-reset" onClick={onReset}>{t("Zurücksetzen")}</button>
          <button className="fp-apply btn btn-primary" onClick={onClose}>
            {t("{n} Treffer zeigen", { n: resultCount.toLocaleString(lang === "de" ? "de-DE" : lang) })}
          </button>
        </div>
      </aside>
    </>
  );
}
