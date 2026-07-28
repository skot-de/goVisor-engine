import "server-only";

/* E-Mail-Versand (Ticket #9) — INTEGRATIONS-STUB. Ohne Provider-Key wird nur geloggt.
 * Zum Scharfschalten: einen Transaktions-Provider anbinden (Resend/Postmark/SES) und in
 * `send()` dessen SDK aufrufen. Bewusst kein harter Dependency, damit der Build ohne
 * Provider-Account läuft. Neue-Leads-Digest ist Marketing (Opt-in + Abmelde-Link),
 * Frist-/Zuschlag-Alerts sind transaktional. */
export type Mail = { to: string; subject: string; text: string; marketing?: boolean };

const KEY = process.env.EMAIL_API_KEY;   // z. B. Resend-Key; fehlt → Stub

export async function send(mail: Mail): Promise<{ ok: boolean; stub: boolean }> {
  if (!KEY) {
    console.info(`[email:stub] → ${mail.to} | ${mail.subject}`);
    return { ok: true, stub: true };
  }
  // TODO(Integration): hier den Provider aufrufen, z. B.:
  //   await resend.emails.send({ from: 'alerts@govisor.de', to: mail.to, subject: mail.subject, text: mail.text });
  console.info(`[email] → ${mail.to} | ${mail.subject}`);
  return { ok: true, stub: false };
}
