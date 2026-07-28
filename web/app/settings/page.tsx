"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { LAENDER } from "@/components/explorer/FilterPanel";
import { logout } from "@/lib/supabase/auth";
import {
  loadAccount, saveProfileFields, loadAlertSettings, saveAlertSettings,
  changePassword, changeEmail, gdprExport, loadInvoices, confirmBand,
  type AccountRow, type AlertSettings, type Invoice,
} from "@/lib/supabase/account";
import { BANDS } from "@/lib/billing";
import "../onboarding/onboarding.css";
import "./settings.css";

const BRANCHEN: [string, string][] = [
  ["it", "IT & Software"], ["bau", "Bau & Infrastruktur"], ["medizin", "Medizin & Gesundheit"],
  ["beratung", "Beratung & Dienstleistung"], ["sicherheit", "Sicherheit & Verteidigung"], ["energie", "Energie & Versorgung"],
];
const SEKTIONEN: [string, string][] = [
  ["profil", "Profil"], ["gruppe", "Gruppe"], ["zahlung", "Zahlung"],
  ["alerts", "Benachrichtigungen"], ["account", "Account"],
];

export default function SettingsPage() {
  const router = useRouter();
  const [sek, setSek] = useState("profil");
  const [acc, setAcc] = useState<AccountRow | null>(null);
  const [alerts, setAlerts] = useState<AlertSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const a = await loadAccount();
      if (!a) { router.push("/login"); return; }
      setAcc(a);
      setAlerts(await loadAlertSettings());
      setLoading(false);
    })();
  }, [router]);

  function melde(m: string) { setToast(m); setTimeout(() => setToast(null), 2000); }

  if (loading || !acc) return <div className="ob-page"><div className="stage"><p className="spin">Lade …</p></div></div>;

  return (
    <div className="ob-page set-page">
      <header className="top">
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span className="brand">go<span>V</span>isor</span><span className="ver">Einstellungen</span>
        </div>
        <Link className="btn btn-t" href="/">Zurück zu den Leads</Link>
      </header>

      <div className="set-wrap">
        <nav className="set-nav">
          {SEKTIONEN.map(([k, l]) => (
            <button key={k} className={`set-navi ${sek === k ? "on" : ""}`} onClick={() => setSek(k)}>{l}</button>
          ))}
        </nav>

        <main className="set-main">
          {sek === "profil" && <ProfilSektion acc={acc} setAcc={setAcc} melde={melde} />}
          {sek === "gruppe" && <GruppeSektion acc={acc} />}
          {sek === "zahlung" && <ZahlungSektion acc={acc} melde={melde} />}
          {sek === "alerts" && alerts && <AlertSektion alerts={alerts} setAlerts={setAlerts} melde={melde} />}
          {sek === "account" && <AccountSektion acc={acc} melde={melde} router={router} />}
        </main>
      </div>
      {toast && <div className="set-toast">{toast}</div>}
    </div>
  );
}

function ProfilSektion({ acc, setAcc, melde }: { acc: AccountRow; setAcc: (a: AccountRow) => void; melde: (m: string) => void }) {
  const [name, setName] = useState(acc.company_name || "");
  const [branche, setBranche] = useState(acc.branche || "");
  const [regions, setRegions] = useState<Set<string>>(new Set(acc.regions));
  const [bundesweit, setBundesweit] = useState(!acc.regions?.length);
  const [vMin, setVMin] = useState(acc.vol_min != null ? String(acc.vol_min) : "");
  const [vMax, setVMax] = useState(acc.vol_max != null ? String(acc.vol_max) : "");

  function toggleR(code: string) {
    setRegions((s) => { const n = new Set(s); n.has(code) ? n.delete(code) : n.add(code); return n; });
    setBundesweit(false);
  }
  async function speichern() {
    const regs = bundesweit ? [] : [...regions];
    const fields = {
      company_name: name.trim() || null, branche: branche || null,
      regions: regs, region_labels: regs.map((r) => r === "BUND" ? "Bund" : (LAENDER.find((l) => l[0] === r)?.[1] || r)),
      vol_min: vMin ? Number(vMin) : null, vol_max: vMax ? Number(vMax) : null,
    };
    const { ok } = await saveProfileFields(fields);
    if (ok) { setAcc({ ...acc, ...fields }); melde("Profil gespeichert — wirkt beim nächsten Laden auf die Relevanz."); }
    else melde("Speichern fehlgeschlagen.");
  }

  return (
    <>
      <h2 className="set-h">Profil</h2>
      <p className="set-x">Steuert Relevanz und Anforderungs-Check. Schwerpunkte (Felder) bearbeitet ihr im Onboarding.</p>
      <div className="field"><label className="lbl">Firmenname</label>
        <input className="inp" value={name} onChange={(e) => setName(e.target.value)} /></div>
      <div className="field"><label className="lbl">Bereich</label>
        <select className="inp" value={branche} onChange={(e) => setBranche(e.target.value)}>
          <option value="">— wählen —</option>
          {BRANCHEN.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select></div>
      <div className="field"><label className="lbl">Schwerpunkte <em style={{ color: "var(--ink-400)", fontWeight: 400 }}>im Onboarding bearbeitbar</em></label>
        <div className="set-chips">{acc.cpv_labels?.length ? acc.cpv_labels.map((l) => <span key={l} className="set-chip ro">{l}</span>) : <span className="set-x">noch keine</span>}
          <Link className="set-editlink" href="/onboarding">bearbeiten →</Link></div></div>
      <div className="field"><label className="lbl">Regionen (Leistungsort)</label>
        <label className="set-check"><input type="checkbox" checked={bundesweit} onChange={() => { setBundesweit((b) => !b); setRegions(new Set()); }} /> Bundesweit</label>
        {!bundesweit && <div className="set-laender">{LAENDER.map(([code, n]) => (
          <label key={code} className={`set-chip ${regions.has(code) ? "on" : ""}`}><input type="checkbox" checked={regions.has(code)} onChange={() => toggleR(code)} style={{ display: "none" }} />{n}</label>
        ))}</div>}</div>
      <div className="field"><label className="lbl">Auftragsvolumen</label>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="set-x">von</span><input className="inp" style={{ width: 130 }} inputMode="numeric" value={vMin} onChange={(e) => setVMin(e.target.value)} placeholder="0" />
          <span className="set-x">bis</span><input className="inp" style={{ width: 130 }} inputMode="numeric" value={vMax} onChange={(e) => setVMax(e.target.value)} placeholder="beliebig" /><span className="set-x">€</span>
        </div></div>
      <div className="btnrow"><button className="btn btn-p" onClick={speichern}>Speichern</button></div>
    </>
  );
}

function GruppeSektion({ acc }: { acc: AccountRow }) {
  const belegt = acc.entity_confidence === "confirmed";
  return (
    <>
      <h2 className="set-h">Firmengruppe</h2>
      <p className="set-x">Öffentliche Auftraggeber schreiben denselben Konzern unterschiedlich. goVisor zählt Siege aller aktiven Einheiten zusammen.</p>
      <div className="set-row"><span className="set-k">Identität</span>
        <span className="set-v"><span className={`conf conf-${belegt ? "belegt" : "unsicher"}`}>{belegt ? "bestätigt" : acc.entity_confidence}</span> {acc.company_name || "—"}</span></div>
      <div className="set-row"><span className="set-k">Aktive Einheiten</span>
        <span className="set-v">{acc.confirmed_entities?.length || 0}</span></div>
      {acc.confirmed_entities?.length ? (
        <div className="set-entlist">{acc.confirmed_entities.map((e, i) => <div key={i} className="set-ent">{e}</div>)}</div>
      ) : <p className="set-x">Keine bestätigte Firma. Im Onboarding könnt ihr eure Firma zuordnen.</p>}
      <div className="btnrow"><Link className="btn btn-s" href="/onboarding">Gruppe im Onboarding ändern</Link></div>
    </>
  );
}

const STATUS_LABEL: Record<string, string> = {
  draft: "in Vorbereitung", needs_confirmation: "Bestätigung nötig", disputed: "in Prüfung",
  sent: "Rechnung gestellt", paid: "bezahlt", waived: "erlassen", failed: "fehlgeschlagen",
};
function ZahlungSektion({ acc, melde }: { acc: AccountRow; melde: (m: string) => void }) {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [bandSel, setBandSel] = useState<Record<string, string>>({});
  useEffect(() => { loadInvoices().then(setInvoices); }, []);

  async function bestaetigen(inv: Invoice) {
    const band = bandSel[inv.id] || inv.anchor_band || BANDS[2];
    const r = await confirmBand(inv.id, band);
    if (!r.ok) return melde("Bestätigung fehlgeschlagen.");
    melde(r.flagged ? "Angabe weicht stark vom Schätzwert ab — geht in Prüfung (Beleg nötig)." : `Band bestätigt · Gebühr ${r.fee} €.`);
    setInvoices(await loadInvoices());
  }

  return (
    <>
      <h2 className="set-h">Zahlung</h2>
      <div className="set-row"><span className="set-k">Zugang</span>
        <span className="set-v"><span className={`conf conf-${acc.plan === "paid" ? "belegt" : "unsicher"}`}>{acc.plan === "paid" ? "Pro" : acc.plan === "cancelled" ? "gekündigt" : "Free"}</span></span></div>
      <div className="set-row"><span className="set-k">Erfolgsprämien-Schonfrist</span>
        <span className="set-v">{acc.grace_until ? `bis ${new Date(acc.grace_until).toLocaleDateString("de-DE")}` : "—"}</span></div>

      <h3 className="set-h3">Rechnungen</h3>
      <p className="set-x">Erfolgsprämien werden nie automatisch abgebucht — ihr bekommt eine Rechnung mit Widerspruchsfrist. Wo kein Auftragswert veröffentlicht ist, bestätigt ihr das Band selbst.</p>
      {invoices.length ? (
        <div className="set-invlist">
          {invoices.map((inv) => (
            <div key={inv.id} className="set-inv">
              <div className="set-inv-top">
                <span className="set-inv-t">{inv.lead_id || "Erfolgsprämie"}{inv.award_date ? ` · ${new Date(inv.award_date).toLocaleDateString("de-DE")}` : ""}</span>
                <span className={`conf conf-${inv.status === "paid" ? "belegt" : "unsicher"}`}>{STATUS_LABEL[inv.status] || inv.status}</span>
              </div>
              <div className="set-inv-b">
                {inv.fee_amount != null ? <span className="set-inv-fee">{inv.fee_amount} €</span> : <span className="set-x">Betrag offen</span>}
                {inv.value_source ? <span className="set-x"> · {inv.value_source === "echt" ? "belegter Wert" : inv.value_source === "kunde_bestaetigt" ? "von euch bestätigt" : "offen"}</span> : null}
              </div>
              {inv.status === "needs_confirmation" ? (
                <div className="set-inv-confirm">
                  <span className="set-x">Bitte bestätigt das Auftragsband{inv.anchor_band ? ` (unser Schätzwert: ${inv.anchor_band})` : ""}:</span>
                  <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                    <select className="inp" style={{ maxWidth: 160 }} value={bandSel[inv.id] || inv.anchor_band || BANDS[2]} onChange={(e) => setBandSel((s) => ({ ...s, [inv.id]: e.target.value }))}>
                      {BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
                    </select>
                    <button className="btn btn-p" onClick={() => bestaetigen(inv)}>Bestätigen</button>
                  </div>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : <div className="set-empty">Noch keine Rechnungen.</div>}
      <div className="mnote" style={{ marginTop: "var(--s4)" }}>Karten-Hinterlegung & Abo-Zahlung laufen über Stripe (Integrations-Stub bis Provider-Key gesetzt ist).</div>
    </>
  );
}

function AlertSektion({ alerts, setAlerts, melde }: { alerts: AlertSettings; setAlerts: (a: AlertSettings) => void; melde: (m: string) => void }) {
  const set = (patch: Partial<AlertSettings>) => setAlerts({ ...alerts, ...patch });
  async function speichern() { const { ok } = await saveAlertSettings(alerts); melde(ok ? "Benachrichtigungen gespeichert." : "Speichern fehlgeschlagen."); }
  const TOG: [keyof AlertSettings, string, string][] = [
    ["deadline_warning_enabled", "Angebotsfrist naht", "14 und 3 Tage vor der Frist — der wichtigste Alert."],
    ["expiry_warning_enabled", "Vertrag läuft aus", "Nur wo ein echtes Vertragsende bekannt ist."],
    ["award_notify_enabled", "Zuschlag erteilt", "Wenn eine beobachtete Ausschreibung vergeben wird."],
    ["new_leads_digest_enabled", "Neue passende Leads", "Digest neuer Treffer (Marketing — abbestellbar)."],
  ];
  return (
    <>
      <h2 className="set-h">Benachrichtigungen</h2>
      <p className="set-x">E-Mail-Benachrichtigungen zu euren beobachteten Leads (Pro).</p>
      {TOG.map(([k, l, x]) => (
        <label key={k} className="set-toggle">
          <input type="checkbox" checked={alerts[k] as boolean} onChange={(e) => set({ [k]: e.target.checked })} />
          <span><b>{l}</b><span className="set-x">{x}</span></span>
        </label>
      ))}
      <div className="field" style={{ marginTop: "var(--s4)" }}><label className="lbl">Frequenz</label>
        <select className="inp" value={alerts.frequency} onChange={(e) => set({ frequency: e.target.value as AlertSettings["frequency"] })}>
          <option value="instant">Sofort</option><option value="daily">Täglich</option><option value="weekly">Wöchentlich</option>
        </select></div>
      <div className="btnrow"><button className="btn btn-p" onClick={speichern}>Speichern</button></div>
    </>
  );
}

function AccountSektion({ acc, melde, router }: { acc: AccountRow; melde: (m: string) => void; router: ReturnType<typeof useRouter> }) {
  const [pw, setPw] = useState("");
  const [email, setEmail] = useState(acc.email);
  const [confirmDel, setConfirmDel] = useState(false);

  async function pwSpeichern() {
    if (pw.length < 8) return melde("Passwort zu kurz (min. 8).");
    const { error } = await changePassword(pw); setPw("");
    melde(error ? error.message : "Passwort geändert.");
  }
  async function emailSpeichern() {
    const { error } = await changeEmail(email);
    melde(error ? error.message : "Bestätigt die neue Adresse über die E-Mail, die wir geschickt haben.");
  }
  async function exportieren() {
    const data = await gdprExport();
    if (!data) return melde("Export fehlgeschlagen.");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "govisor-datenexport.json"; a.click();
    melde("Datenexport heruntergeladen.");
  }
  async function loeschen() {
    const r = await fetch("/api/account/delete", { method: "POST" }).then((x) => x.json()).catch(() => ({ ok: false }));
    if (!r.ok) return melde("Löschung fehlgeschlagen.");
    await logout(); router.push("/");
  }

  return (
    <>
      <h2 className="set-h">Account</h2>
      <div className="field"><label className="lbl">E-Mail</label>
        <div style={{ display: "flex", gap: 8 }}>
          <input className="inp" value={email} onChange={(e) => setEmail(e.target.value)} />
          <button className="btn btn-s" onClick={emailSpeichern} disabled={email === acc.email}>Ändern</button>
        </div><span className="set-x">Änderung erfordert Bestätigung der neuen Adresse.</span></div>
      <div className="field"><label className="lbl">Neues Passwort</label>
        <div style={{ display: "flex", gap: 8 }}>
          <input className="inp" type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="min. 8 Zeichen" />
          <button className="btn btn-s" onClick={pwSpeichern} disabled={!pw}>Ändern</button>
        </div></div>

      <h3 className="set-h3">Eure Daten</h3>
      <div className="btnrow"><button className="btn btn-s" onClick={exportieren}>Datenexport (DSGVO) herunterladen</button></div>

      <h3 className="set-h3" style={{ color: "var(--risk)" }}>Account löschen</h3>
      <p className="set-x">Löscht euer Konto und alle Daten unwiderruflich. Bezahlte Rechnungen bleiben pseudonymisiert erhalten.</p>
      {!confirmDel
        ? <div className="btnrow"><button className="btn set-danger" onClick={() => setConfirmDel(true)}>Account löschen</button></div>
        : <div className="btnrow"><button className="btn set-danger" onClick={loeschen}>Endgültig löschen</button><button className="btn btn-t" onClick={() => setConfirmDel(false)}>Abbrechen</button></div>}
    </>
  );
}
