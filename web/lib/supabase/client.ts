import { createBrowserClient } from "@supabase/ssr";

/* Browser-Client — nutzt den öffentlichen Publishable/Anon-Key. Für Auth im Client
 * (Login/Registrierung) und RLS-gebundene Reads. */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
