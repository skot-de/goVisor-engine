"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { currentUser } from "@/lib/supabase/auth";
import { loadContracts, addContract, updateContract, removeContract, type UserContract } from "@/lib/supabase/contracts";

/* Editierbarer eigener Vertragsbestand (Ticket #11 §8.2 → Strategie/Bindung #10 §5.7).
 * Speist die Verteidigungs-/Kapazitätssicht: gewonnene (Rahmen-)Verträge binden beim Auslaufen
 * wieder Kapazität. Tabelle ist voll editierbar; „als gewonnen markieren" aus einem Lead
 * legt hier eine Zeile an. */

function fmtEur(v: number | null): string {
  if (v == null) return "—";
  if (v >= 1e6) return (v / 1e6).toFixed(1).replace(".", ",") + " Mio €";
  return Math.round(v).toLocaleString("de-DE") + " €";
}
function tageBis(end: string | null): number | null {
  if (!end) return null;
  return Math.round((new Date(end).getTime() - Date.now()) / 86400000);
}

export function ContractsEditor() {
  const [angemeldet, setAngemeldet] = useState<boolean | null>(null);
  const [rows, setRows] = useState<UserContract[]>([]);

  useEffect(() => {
    (async () => {
      const u = await currentUser().catch(() => null);
      setAngemeldet(!!u);
      if (u) setRows(await loadContracts());
    })();
  }, []);

  function patchLocal(id: string, f: Partial<UserContract>) {
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...f } : r)));
  }
  async function speichern(id: string, f: Partial<UserContract>) {
    patchLocal(id, f);
    await updateContract(id, f);
  }
  async function neu() {
    const r = await addContract({ buyer_name: "", titel: "", is_framework: false });
    if (r.ok) setRows(await loadContracts());
  }
  async function loeschen(id: string) {
    setRows((rs) => rs.filter((r) => r.id !== id));
    await removeContract(id);
  }

  // Abgeleitete Kennzahlen (Verteidigung/Kapazität/Konzentration)
  const analyse = useMemo(() => {
    const framework = rows.filter((r) => r.is_framework);
    const gebunden = framework.reduce((a, r) => a + (r.value_euro || 0), 0);
    const bald = rows.filter((r) => { const t = tageBis(r.end_date); return t != null && t >= 0 && t <= 540; })
      .sort((a, b) => (tageBis(a.end_date) ?? 1e9) - (tageBis(b.end_date) ?? 1e9));
    const proBuyer: Record<string, number> = {};
    for (const r of rows) if (r.value_euro) proBuyer[r.buyer_name || "—"] = (proBuyer[r.buyer_name || "—"] || 0) + r.value_euro;
    const gesamt = Object.values(proBuyer).reduce((a, b) => a + b, 0);
    const top = Object.entries(proBuyer).sort((a, b) => b[1] - a[1])[0];
    return { gebunden, frameworkN: framework.length, bald, konzentration: top && gesamt ? Math.round((top[1] / gesamt) * 100) : null, topBuyer: top?.[0] };
  }, [rows]);

  if (angemeldet === null) return <div className="spin">Lade …</div>;
  if (!angemeldet) return (
    <div className="mnote">Meldet euch an und hinterlegt eure laufenden Verträge — dann rechnen wir hier,
      wann sie wieder Kapazität binden und welche ihr verteidigen müsst. <Link href="/login" style={{ textDecoration: "underline" }}>Anmelden</Link></div>
  );

  return (
    <>
      {rows.length ? (
        <div className="bstats" style={{ marginBottom: "var(--s4)" }}>
          <div className="bstat"><span className="bstat-k">Gebundene Kapazität</span>
            <span className="bstat-v"><span className="v-num">{fmtEur(analyse.gebunden)}</span></span>
            <span className="bstat-m">in {analyse.frameworkN} Rahmenvertrag/-verträgen</span></div>
          <div className="bstat"><span className="bstat-k">Bald auslaufend (≤18 Mon.)</span>
            <span className="bstat-v"><span className="v-num">{analyse.bald.length}</span></span>
            <span className="bstat-m">Verteidigungsbedarf</span></div>
          <div className="bstat"><span className="bstat-k">Konzentrationsrisiko</span>
            <span className="bstat-v">{analyse.konzentration != null ? <span className="v-num">{analyse.konzentration} %</span> : <span className="v-sparse">—</span>}</span>
            <span className="bstat-m">{analyse.topBuyer ? `an ${analyse.topBuyer.slice(0, 28)}` : ""}</span></div>
        </div>
      ) : null}

      {analyse.bald.length ? (
        <div className="ce-defense">
          <span className="ce-def-h">Eure auslaufenden Verträge — nächste zuerst</span>
          {analyse.bald.slice(0, 5).map((r) => { const t = tageBis(r.end_date)!; const mon = Math.round(t / 30);
            return <div key={r.id} className="ce-def-row"><span className="ce-def-n">{r.titel || r.buyer_name || "—"}{r.is_framework ? <span className="st-tag">Rahmen</span> : null}</span>
              <span className="ce-def-w">{fmtEur(r.value_euro)}</span><span className="ce-def-t">in {mon} Mon.</span></div>; })}
        </div>
      ) : null}

      <div className="ce-table">
        <div className="ce-row ce-head">
          <span>Auftraggeber</span><span>Bezeichnung</span><span>Rahmen</span><span>Wert (€)</span><span>Ende</span><span />
        </div>
        {rows.map((r) => (
          <div key={r.id} className="ce-row">
            <input className="ce-in" value={r.buyer_name || ""} placeholder="Vergabestelle"
              onChange={(e) => patchLocal(r.id, { buyer_name: e.target.value })} onBlur={(e) => speichern(r.id, { buyer_name: e.target.value })} />
            <input className="ce-in" value={r.titel || ""} placeholder="Vertragsgegenstand"
              onChange={(e) => patchLocal(r.id, { titel: e.target.value })} onBlur={(e) => speichern(r.id, { titel: e.target.value })} />
            <label className="ce-cb"><input type="checkbox" checked={r.is_framework} onChange={(e) => speichern(r.id, { is_framework: e.target.checked })} /></label>
            <input className="ce-in ce-num" inputMode="numeric" value={r.value_euro ?? ""} placeholder="0"
              onChange={(e) => patchLocal(r.id, { value_euro: e.target.value ? Number(e.target.value) : null })}
              onBlur={(e) => speichern(r.id, { value_euro: e.target.value ? Number(e.target.value) : null })} />
            <input className="ce-in" type="date" value={r.end_date || ""} onChange={(e) => speichern(r.id, { end_date: e.target.value || null })} />
            <button className="ce-del" onClick={() => loeschen(r.id)} title="Löschen">✕</button>
          </div>
        ))}
        {!rows.length ? <div className="ce-empty">Noch keine Verträge hinterlegt.</div> : null}
      </div>
      <button className="sec-link" onClick={neu} style={{ marginTop: "var(--s3)" }}>+ Vertrag hinzufügen</button>
    </>
  );
}
