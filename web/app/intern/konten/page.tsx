"use client";
/**
 * Konten & Profile (Admin-Portal, Bereich 3). Orgs mit Mitgliedern/Seats/Profilen/Plan,
 * Identitaets-Ansprueche, Passwort-Reset. Quellen: /api/intern/konten + /api/intern/claims.
 * Middleware sperrt /intern auf istAdmin; ohne Session 404 → Hinweis statt leerer Seite.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import "../../intern.css";

type Org = {
  id: string; name: string; plan: string; seats_paid: number; profiles_paid: number;
  profile: number; mitglieder: { email: string; role: string }[];
};
type Claim = {
  id: string; company_name: string; email_domain: string | null; status: string;
  grund: string | null; domainPasst: boolean;
  firma: { name: string; wins: number; bekannteDomain: string | null } | null;
};

export default function KontenPage() {
  const [orgs, setOrgs] = useState<Org[] | null>(null);
  const [claims, setClaims] = useState<Claim[] | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [reset, setReset] = useState("");
  const [ts, setTs] = useState(0);

  function melde(m: string) { setToast(m); setTimeout(() => setToast(null), 2500); }

  useEffect(() => {
    let ab = false;
    (async () => {
      try {
        const [rk, rc] = await Promise.all([
          fetch("/api/intern/konten", { cache: "no-store" }),
          fetch("/api/intern/claims", { cache: "no-store" }),
        ]);
        if (ab) return;
        if (rk.status === 404) { setFehler("Kein Zugriff — als Admin anmelden (istAdmin)."); return; }
        setOrgs((await rk.json()).orgs ?? []);
        setClaims(rc.ok ? ((await rc.json()).claims ?? []) : []);
        setFehler(null);
      } catch { if (!ab) setFehler("Laden fehlgeschlagen."); }
    })();
    return () => { ab = true; };
  }, [ts]);

  async function setzen(org_id: string, feld: string, wert: string | number) {
    const r = await fetch("/api/intern/konten", {
      method: "PATCH", headers: { "content-type": "application/json" },
      body: JSON.stringify({ org_id, [feld]: wert }),
    });
    const j = await r.json().catch(() => ({}));
    if (r.ok) { melde("Gespeichert"); setTs(Date.now()); } else melde(j.error || "Fehler");
  }

  async function claim(id: string, status: "geprueft" | "abgelehnt") {
    const r = await fetch("/api/intern/claims", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ id, status, von: "admin-portal" }),
    });
    const j = await r.json().catch(() => ({}));
    if (r.ok) { melde(status === "geprueft" ? "Freigegeben" : "Abgelehnt"); setTs(Date.now()); }
    else melde(j.error || "Fehler");
  }

  async function passwortReset() {
    if (!reset.trim()) return;
    const r = await fetch("/api/intern/konten", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ action: "passwort-reset", email: reset.trim() }),
    });
    const j = await r.json().catch(() => ({}));
    if (r.ok) { melde("Reset-Mail ausgelöst"); setReset(""); } else melde(j.error || "Fehler");
  }

  const offeneClaims = (claims ?? []).filter((c) => c.status === "unbestaetigt");

  return (
    <main className="cp-wrap">
      <header className="cp-top">
        <h1>Konten & Profile</h1>
        <nav className="cp-nav">
          <Link href="/intern/betrieb">Betrieb</Link>
          <Link href="/intern/qualitaet">Datenqualität</Link>
          <Link href="/intern/kosten">LLM & Kosten</Link>
          <Link href="/intern/kuratierung">Kuratierung</Link>
          <Link href="/intern">Firmen-Radar</Link>
          <button onClick={() => setTs(Date.now())}>Aktualisieren</button>
        </nav>
      </header>
      {toast && <p className="cp-toast">{toast}</p>}
      {fehler && <p className="cp-hinweis">{fehler}</p>}

      {/* Passwort-Reset */}
      <section className="cp-karte" style={{ marginBottom: 14 }}>
        <h3>Passwort-Reset (Mail auslösen)</h3>
        <div className="pv-neu">
          <input type="email" value={reset} onChange={(e) => setReset(e.target.value)} placeholder="E-Mail des Nutzers" />
          <button className="pv-btn" onClick={passwortReset} disabled={!reset.trim()}>Reset-Mail senden</button>
        </div>
        <p className="cp-klein">Es wird nur die Reset-Mail ausgelöst — nie ein Passwort gesetzt.</p>
      </section>

      {/* Identitäts-Ansprüche */}
      <section className="cp-karte" style={{ marginBottom: 14 }}>
        <h3>Offene Identitäts-Ansprüche {offeneClaims.length ? `(${offeneClaims.length})` : ""}</h3>
        {offeneClaims.length === 0 ? <p className="cp-klein">keine offenen Ansprüche</p> :
          <table className="cp-tab"><thead><tr>
            <th>Firma (Anspruch)</th><th>Domain</th><th>bekannt</th><th>passt?</th><th></th>
          </tr></thead><tbody>
            {offeneClaims.map((c) => (
              <tr key={c.id}>
                <td>{c.company_name}{c.firma ? ` · ${c.firma.wins} Zuschläge` : ""}</td>
                <td>{c.email_domain ?? "—"}</td>
                <td>{c.firma?.bekannteDomain ?? "—"}</td>
                <td>{c.domainPasst ? "✓" : "—"}</td>
                <td className="cp-acts">
                  <button className="pv-btn" onClick={() => claim(c.id, "geprueft")}>Freigeben</button>
                  <button className="pv-btn pv-del" onClick={() => claim(c.id, "abgelehnt")}>Ablehnen</button>
                </td>
              </tr>
            ))}
          </tbody></table>}
      </section>

      {/* Organisationen */}
      <section className="cp-karte">
        <h3>Organisationen {orgs ? `(${orgs.length})` : ""}</h3>
        {!orgs ? <p className="cp-klein">—</p> :
          <table className="cp-tab"><thead><tr>
            <th>Organisation</th><th>Inhaber</th><th>Plan</th><th>Seats</th><th>Profile</th>
          </tr></thead><tbody>
            {orgs.map((o) => {
              const owner = o.mitglieder.find((m) => m.role === "owner")?.email
                ?? o.mitglieder[0]?.email ?? "—";
              return (
                <tr key={o.id}>
                  <td>{o.name}{o.mitglieder.length > 1 ? ` · ${o.mitglieder.length} Mitglieder` : ""}</td>
                  <td className="cp-klein">{owner}</td>
                  <td>
                    <select defaultValue={o.plan} onChange={(e) => setzen(o.id, "plan", e.target.value)}>
                      <option value="free">free</option><option value="paid">paid</option>
                      <option value="cancelled">cancelled</option>
                    </select>
                  </td>
                  <td>{o.mitglieder.length}/<input className="cp-num" type="number" min={1} defaultValue={o.seats_paid}
                        onBlur={(e) => Number(e.target.value) !== o.seats_paid && setzen(o.id, "seats_paid", Number(e.target.value))} /></td>
                  <td>{o.profile}/<input className="cp-num" type="number" min={1} defaultValue={o.profiles_paid}
                        onBlur={(e) => Number(e.target.value) !== o.profiles_paid && setzen(o.id, "profiles_paid", Number(e.target.value))} /></td>
                </tr>
              );
            })}
          </tbody></table>}
        <p className="cp-klein">Seats/Profile hier setzen ist der manuelle Hebel, solange der Kauf-Flow (Stripe/Preise) nicht scharf ist.</p>
      </section>
    </main>
  );
}
