"use client";

import { useSprache } from "@/lib/i18n";

import { BRANCHEN } from "@/lib/explorerCore";

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
  staaten: string[];               // DACH-Vergabeland: DE | AT | CH (alle mit Daten)
};

export const emptyAdv: Adv = {
  phases: [], horizon: null, cpvFields: [], regionAxis: "perf", regions: [], nationwide: false,
  buyer: "", leistung: [], art: [], rahmen: [], valMin: null, valMax: null,
  neu: "all", wenigWettbewerb: false, aufwand: [], buergschaft: "all", chance: [], relevanz: [], multiLot: false,
  hasDetail: false, unterlagen: false, staaten: [],
};

export function advCount(a: Adv): number {
  return (
    a.phases.length + (a.horizon != null ? 1 : 0) + a.cpvFields.length + a.regions.length + (a.nationwide ? 1 : 0) +
    (a.buyer.trim() ? 1 : 0) + a.leistung.length + a.art.length + a.rahmen.length +
    (a.valMin != null ? 1 : 0) + (a.valMax != null ? 1 : 0) +
    (a.neu !== "all" ? 1 : 0) + (a.wenigWettbewerb ? 1 : 0) + a.aufwand.length +
    (a.buergschaft !== "all" ? 1 : 0) + a.chance.length + a.relevanz.length + (a.multiLot ? 1 : 0) +
    (a.hasDetail ? 1 : 0) + (a.unterlagen ? 1 : 0) + a.staaten.length
  );
}

export type Segment = { cpv4: string; label: string; n: number };

const PHASEN: [string, string][] = [
  ["auslauf", "Auslaufende Verträge"],
  ["f02", "Aktive Ausschreibungen"],
  ["f01", "Ankündigungen"],
  ["award", "Zuschlag erteilt"],
];
const HORIZONTE: [number, string][] = [[1, "1 Mon."], [3, "3 Mon."], [6, "6 Mon."], [12, "12 Mon."], [18, "18 Mon."]];
const LEISTUNG: [string, string][] = [["dienst", "Dienstleistung"], ["liefer", "Lieferung"], ["bau", "Bauleistung"]];
const RAHMEN: [string, string][] = [["vgv", "VgV"], ["vob", "VOB/A"], ["uvgo", "UVgO"], ["sektvo", "SektVO"]];
const BAND: [string, string][] = [["niedrig", "niedrig"], ["mittel", "mittel"], ["hoch", "hoch"]];
const ART: [string, string][] = [["rahmen", "Rahmenvertrag"], ["wiederkehrend", "Wiederkehrend"], ["einzel", "Einzelauftrag"]];
// DACH-Vergabeland. Alle drei tragen Daten (DE ~21k, CH ~1,7k, AT ~1,1k) — der Filter greift
// auf `l.land` (ExplorerShell). AT = offeneVergaben.at, CH = simap.ch.
const STAATEN: [string, string][] = [["DE", "Deutschland"], ["AT", "Österreich"], ["CH", "Schweiz"]];
export const LAENDER: [string, string][] = [
  ["DE1", "Baden-Württemberg"], ["DE2", "Bayern"], ["DE3", "Berlin"], ["DE4", "Brandenburg"],
  ["DE5", "Bremen"], ["DE6", "Hamburg"], ["DE7", "Hessen"], ["DE8", "Mecklenburg-Vorp."],
  ["DE9", "Niedersachsen"], ["DEA", "Nordrhein-Westf."], ["DEB", "Rheinland-Pfalz"], ["DEC", "Saarland"],
  ["DED", "Sachsen"], ["DEE", "Sachsen-Anhalt"], ["DEF", "Schleswig-Holstein"], ["DEG", "Thüringen"],
];

const toggle = (arr: string[], v: string) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);
const parseEur = (s: string): number | null => {
  const n = parseFloat(s.replace(/[^\d]/g, ""));
  return isNaN(n) ? null : n;
};

export function FilterPanel({
  open, adv, resultCount, segments, onChange, onClose, onReset,
  branche, profilBranche, brancheCounts, onSetBranche, onResetBranche,
}: {
  open: boolean; adv: Adv; resultCount: number; segments: Segment[];
  onChange: (a: Adv) => void; onClose: () => void; onReset: () => void;
  // Grundraum: strukturell ein Filter (welcher Datenraum), deshalb hier statt im Header —
  // er wird aus dem Profil abgeleitet und ist kein Routine-Handgriff mehr.
  branche: string; profilBranche: string; brancheCounts: Record<string, number>;
  onSetBranche: (k: string) => void; onResetBranche: () => void;
}) {
  const { t, lang } = useSprache();
  const set = (patch: Partial<Adv>) => onChange({ ...adv, ...patch });
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

          <section className="fp-sec">
            <h5>{t("Land")} <span className="fp-hint">{t("Vergabeland (DACH)")}</span></h5>
            {STAATEN.map(([v, l]) => (
              <label key={v} className="fp-check">
                <input type="checkbox" checked={adv.staaten.includes(v)} onChange={() => set({ staaten: toggle(adv.staaten, v) })} />
                <span>{t(l)}</span>
              </label>
            ))}
          </section>

          <section className="fp-sec">
            <h5>{t("Phase")}</h5>
            {PHASEN.map(([v, l]) => (
              <label key={v} className="fp-check">
                <input type="checkbox" checked={adv.phases.includes(v)} onChange={() => set({ phases: toggle(adv.phases, v) })} />
                <span>{t(l)}</span>
              </label>
            ))}
          </section>

          <section className="fp-sec">
            <h5>{t("Frist / Vertragsende — in den nächsten …")}</h5>
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
                <button key={v} className={`fp-chip ${adv.relevanz.includes(v) ? "on" : ""}`} onClick={() => set({ relevanz: toggle(adv.relevanz, v) })}>{t(l)}</button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>{t("Chance")} <span className="fp-hint">{t("Wechsel-Chance")}</span></h5>
            <div className="fp-chips">
              {BAND.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.chance.includes(v) ? "on" : ""}`} onClick={() => set({ chance: toggle(adv.chance, v) })}>{t(l)}</button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>{t("Aufwand")}</h5>
            <div className="fp-chips">
              {BAND.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.aufwand.includes(v) ? "on" : ""}`} onClick={() => set({ aufwand: toggle(adv.aufwand, v) })}>{t(l)}</button>
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
                <button key={v} className={`fp-chip ${adv.leistung.includes(v) ? "on" : ""}`} onClick={() => set({ leistung: toggle(adv.leistung, v) })}>{t(l)}</button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>{t("Vertragsart")}</h5>
            <div className="fp-chips">
              {ART.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.art.includes(v) ? "on" : ""}`} onClick={() => set({ art: toggle(adv.art, v) })}>{t(l)}</button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>{t("Rechtsrahmen")}</h5>
            <div className="fp-chips">
              {RAHMEN.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.rahmen.includes(v) ? "on" : ""}`} onClick={() => set({ rahmen: toggle(adv.rahmen, v) })}>{t(l)}</button>
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
