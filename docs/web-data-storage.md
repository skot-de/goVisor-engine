# web/data aus Git holen — Migrations-Notiz

**Problem:** `web/data/*.json` (~88 MB: leads/detail/branchen/markt/plz-geo) liegt in Git und
wächst mit jedem Export (~monatlich) → Repo-History bläht auf.

**Vorbereitet (Code steht):** Alle Daten-Routes (`/api/{leads,branchen,plz-geo,markt,lead-detail}`)
laden über `web/lib/dataSource.ts::loadDataFile()`:
- **`DATA_BASE_URL` gesetzt** → JSONs von dort (Object-Storage: Vercel Blob, Supabase Storage,
  S3/R2, beliebige CDN-Basis-URL).
- **nicht gesetzt** → lokales `web/data/` (heutiges Verhalten, Fallback).

## Umzug in 3 Schritten (wenn du so weit bist)
1. **Storage wählen + hochladen** — die 6 `leads-*.json`, 6 `detail-*.json`, `branchen.json`,
   `markt.json`, `plz-geo.json` in einen öffentlich lesbaren Bucket/Store legen (gleiche Dateinamen).
   - **Vercel Blob** (am einfachsten für dieses Setup): `npx vercel blob put web/data/*.json`, Basis-URL notieren.
   - **Supabase Storage / S3 / R2**: Bucket anlegen, hochladen, Basis-URL notieren.
2. **Env setzen:** in Vercel `DATA_BASE_URL=https://<dein-store>/…/` (die Basis, unter der die Dateien liegen).
3. **web/data gitignoren:** `echo "web/data/*.json" >> web/.gitignore`, aus dem Index nehmen
   (`git rm --cached web/data/*.json`), committen. Ab dann wächst Git nicht mehr.

Der Export-Lauf (`scripts/export_web_leads.py`) schreibt weiter nach `web/data/` (lokal); danach
lädst du die JSONs zum Store hoch (ein kleines Upload-Skript kann das automatisieren).

**Alternative (perspektivisch):** Statt statischer JSONs die kuratierten Leads in **Supabase** (Tabelle)
und die Routes per Query — dann live-aktualisierbar, aber braucht größeren Supabase-Plan (s. CLAUDE.md).
