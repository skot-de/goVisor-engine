"use client";

export type Adv = {
  phases: string[];                 // auslauf | f02 | f01
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
}: {
  open: boolean; adv: Adv; resultCount: number; segments: Segment[];
  onChange: (a: Adv) => void; onClose: () => void; onReset: () => void;
}) {
  const set = (patch: Partial<Adv>) => onChange({ ...adv, ...patch });
  const isPreset = adv.horizon != null && HORIZONTE.some(([m]) => m === adv.horizon);

  return (
    <>
      <div className={`fp-scrim ${open ? "on" : ""}`} onClick={onClose} aria-hidden />
      <aside className={`fp ${open ? "on" : ""}`} aria-label="Filter" aria-hidden={!open}>
        <div className="fp-head">
          <span className="fp-title">Filter</span>
          <button className="fp-x" onClick={onClose} aria-label="Schließen">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round"><path d="M6 6l12 12M18 6 6 18" /></svg>
          </button>
        </div>

        <div className="fp-body">
          <section className="fp-sec">
            <h5>Land <span className="fp-hint">Vergabeland (DACH)</span></h5>
            {STAATEN.map(([v, l]) => (
              <label key={v} className="fp-check">
                <input type="checkbox" checked={adv.staaten.includes(v)} onChange={() => set({ staaten: toggle(adv.staaten, v) })} />
                <span>{l}</span>
              </label>
            ))}
          </section>

          <section className="fp-sec">
            <h5>Phase</h5>
            {PHASEN.map(([v, l]) => (
              <label key={v} className="fp-check">
                <input type="checkbox" checked={adv.phases.includes(v)} onChange={() => set({ phases: toggle(adv.phases, v) })} />
                <span>{l}</span>
              </label>
            ))}
          </section>

          <section className="fp-sec">
            <h5>Frist / Vertragsende — in den nächsten …</h5>
            <div className="fp-chips">
              <button className={`fp-chip ${adv.horizon == null ? "on" : ""}`} onClick={() => set({ horizon: null })}>egal</button>
              {HORIZONTE.map(([m, l]) => (
                <button key={m} className={`fp-chip ${adv.horizon === m ? "on" : ""}`} onClick={() => set({ horizon: m })}>{l}</button>
              ))}
              <span className="fp-manual">
                oder
                <input className="fp-in fp-mini" inputMode="numeric" placeholder="__"
                  defaultValue={isPreset ? "" : (adv.horizon ?? "")}
                  onChange={(e) => { const n = parseInt(e.target.value, 10); set({ horizon: isNaN(n) ? null : n }); }} />
                Monate
              </span>
            </div>
          </section>

          {segments.length ? (
            <section className="fp-sec">
              <h5>Fachgebiet <span className="fp-hint">{adv.cpvFields.length ? `${adv.cpvFields.length} gewählt` : "alle im Grundraum"}</span></h5>
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
            <h5>Region
              <span className="fp-axis">
                <button className={adv.regionAxis === "perf" ? "on" : ""} onClick={() => set({ regionAxis: "perf" })}>Leistungsort</button>
                <button className={adv.regionAxis === "buyer" ? "on" : ""} onClick={() => set({ regionAxis: "buyer" })}>Käufersitz</button>
              </span>
            </h5>
            <label className="fp-check">
              <input type="checkbox" checked={adv.nationwide} onChange={() => set({ nationwide: !adv.nationwide })} />
              <span>Bundesweit erbringbare mit einschließen</span>
            </label>
            <div className="fp-grid2">
              {LAENDER.map(([code, name]) => (
                <label key={code} className="fp-check">
                  <input type="checkbox" checked={adv.regions.includes(code)} onChange={() => set({ regions: toggle(adv.regions, code) })} />
                  <span>{name}</span>
                </label>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>Vergabestelle</h5>
            <input className="fp-in" placeholder="Name enthält …" value={adv.buyer} onChange={(e) => set({ buyer: e.target.value })} />
          </section>

          <section className="fp-sec">
            <h5>Wettbewerb</h5>
            <div className="fp-chips">
              {(["all", "neu", "folge"] as const).map((k) => (
                <button key={k} className={`fp-chip ${adv.neu === k ? "on" : ""}`} onClick={() => set({ neu: k })}>
                  {k === "all" ? "alle" : k === "neu" ? "Neuvergabe (kein Amtsinhaber)" : "Folgevergabe"}
                </button>
              ))}
            </div>
            <label className="fp-check" style={{ marginTop: 8 }}>
              <input type="checkbox" checked={adv.wenigWettbewerb} onChange={() => set({ wenigWettbewerb: !adv.wenigWettbewerb })} />
              <span>Nur mit wenig Wettbewerb (zuletzt ≤ 3 Bieter)</span>
            </label>
          </section>

          <section className="fp-sec">
            <h5>Relevanz <span className="fp-hint">Profil-Passung · braucht Profil</span></h5>
            <div className="fp-chips">
              {BAND.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.relevanz.includes(v) ? "on" : ""}`} onClick={() => set({ relevanz: toggle(adv.relevanz, v) })}>{l}</button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>Chance <span className="fp-hint">Wechsel-Chance</span></h5>
            <div className="fp-chips">
              {BAND.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.chance.includes(v) ? "on" : ""}`} onClick={() => set({ chance: toggle(adv.chance, v) })}>{l}</button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>Aufwand</h5>
            <div className="fp-chips">
              {BAND.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.aufwand.includes(v) ? "on" : ""}`} onClick={() => set({ aufwand: toggle(adv.aufwand, v) })}>{l}</button>
              ))}
            </div>
            <div className="fp-chips" style={{ marginTop: 8 }}>
              <span className="fp-hint" style={{ alignSelf: "center", marginRight: 4 }}>Bürgschaft:</span>
              {(["all", "nein", "ja"] as const).map((k) => (
                <button key={k} className={`fp-chip ${adv.buergschaft === k ? "on" : ""}`} onClick={() => set({ buergschaft: k })}>
                  {k === "all" ? "egal" : k === "nein" ? "keine" : "gefordert"}
                </button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>Leistungsart</h5>
            <div className="fp-chips">
              {LEISTUNG.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.leistung.includes(v) ? "on" : ""}`} onClick={() => set({ leistung: toggle(adv.leistung, v) })}>{l}</button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>Vertragsart</h5>
            <div className="fp-chips">
              {ART.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.art.includes(v) ? "on" : ""}`} onClick={() => set({ art: toggle(adv.art, v) })}>{l}</button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>Rechtsrahmen</h5>
            <div className="fp-chips">
              {RAHMEN.map(([v, l]) => (
                <button key={v} className={`fp-chip ${adv.rahmen.includes(v) ? "on" : ""}`} onClick={() => set({ rahmen: toggle(adv.rahmen, v) })}>{l}</button>
              ))}
            </div>
          </section>

          <section className="fp-sec">
            <h5>Auftragswert (€)</h5>
            <div className="fp-range">
              <input className="fp-in" inputMode="numeric" placeholder="von" defaultValue={adv.valMin ?? ""} onBlur={(e) => set({ valMin: parseEur(e.target.value) })} />
              <span>–</span>
              <input className="fp-in" inputMode="numeric" placeholder="bis" defaultValue={adv.valMax ?? ""} onBlur={(e) => set({ valMax: parseEur(e.target.value) })} />
            </div>
          </section>

          <section className="fp-sec">
            <h5>Weitere</h5>
            <label className="fp-check"><input type="checkbox" checked={adv.multiLot} onChange={() => set({ multiLot: !adv.multiLot })} /><span>Nur mit mehreren Losen</span></label>
            <label className="fp-check"><input type="checkbox" checked={adv.hasDetail} onChange={() => set({ hasDetail: !adv.hasDetail })} /><span>Nur mit ausführlicher Beschreibung</span></label>
            <label className="fp-check"><input type="checkbox" checked={adv.unterlagen} onChange={() => set({ unterlagen: !adv.unterlagen })} /><span>Nur mit Link zu den Vergabeunterlagen</span></label>
          </section>
        </div>

        <div className="fp-foot">
          <button className="fp-reset" onClick={onReset}>Zurücksetzen</button>
          <button className="fp-apply btn btn-primary" onClick={onClose}>
            {resultCount.toLocaleString("de-DE")} Treffer zeigen
          </button>
        </div>
      </aside>
    </>
  );
}
