import "server-only";
import { createClient } from "@supabase/supabase-js";

/* Admin-Client — Secret-Key, umgeht RLS. AUSSCHLIESSLICH serverseitig (server-only-Import
 * bricht den Build, falls das je in eine Client-Komponente rutscht). Für privilegierte
 * Operationen (später: Success-Fee-Rechnungen, Aggregate). */
export function createAdminClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
    { auth: { persistSession: false, autoRefreshToken: false } },
  );
}
