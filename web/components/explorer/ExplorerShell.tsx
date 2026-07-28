"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  LEADS, BRANCHEN, COLS, applyState, visible, sorted, syncLocationColumn,
  suggestList, classifyQuery, netzInteresse, netzFreigabe, offeneGruppen, angaben, setLeads, setMarket,
  applyProfile, setProfile, setUserContracts, PROFILES, parseWert, aufwandStufe,
} from "@/lib/explorerCore";
import { loadContracts } from "@/lib/supabase/contracts";
import { buildProfile } from "@/lib/profileEngine";
import { FilterPanel, emptyAdv, advCount, type Adv, type Segment } from "./FilterPanel";
import { LeadTable } from "./LeadTable";
import { DetailPanel } from "./DetailPanel";
import { StrategieView } from "./StrategieView";
import { ExportMenu } from "./ExportMenu";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { currentUser, logout, loadProfile } from "@/lib/supabase/auth";
import { recordLeadClick, recordAnalysis } from "@/lib/analytics";
import { syncWatchlist } from "@/lib/supabase/watchlist";
import { Kalender } from "./Kalender";
import { Cockpit } from "./Cockpit";
import { getOrCreateCalendarFeed } from "@/lib/supabase/calendar";

type Profile = ReturnType<typeof buildProfile>;
const PROFILE_KEY = "govisor.profile.v1";
import { Workspace, ColumnMenu, FilterBar, Suggestions, HeaderFilterPopover } from "./parts";

type Lead = { id: string; branche?: string; merk?: unknown; [k: string]: unknown };
type Token = { type: string; value: string; label: string; radius?: number | null };
type Filters = { ungesichtet: boolean; gemerkt: boolean; kandidaten: boolean; netz: boolean; relevant: boolean };
type View = "angriff" | "merkliste" | "netzwerk" | "potenzial";

// Mutabler Prototyp-Zustand, den React nicht als State hält (in-place mutiert):
// COLS-Reihenfolge/on, LEADS[].merk/status, netzInteresse. Ein Tick erzwingt Neuberechnung.
const CORE = LEADS as Lead[];
const ART_MATCH: Record<string, string> = {
  rahmen: "Rahmenvertrag", wiederkehrend: "Wiederkehrende Leistung", einzel: "Einzelauftrag",
};

// Erweiterte Filter (Filter-Panel) über die Kern-Auswahl legen. Unbekanntes schließt nichts
// aus (Wert). Zeithorizont zählt Vertragsende (endTage) bzw. Frist (tage). Region über
// Leistungsort (marktRegion) ODER Käufersitz (nuts) + bundesweit erbringbare.
function postFilter(rows: Lead[], a: Adv): Lead[] {
  if (advCount(a) === 0) return rows;
  const buyer = a.buyer.trim().toLowerCase();
  return rows.filter((l) => {
    if (a.phases.length && !a.phases.includes(String(l.src))) return false;
    if (a.horizon != null) {
      const days = (l.endTage as number | null) ?? (l.tage as number | null);
      if (days == null || days < 0 || days / 30 > a.horizon) return false;
    }
    if (a.regions.length || a.nationwide) {
      const geo = String((a.regionAxis === "perf" ? l.marktRegion : l.nuts) || "");
      const landOk = a.regions.length > 0 && a.regions.some((r) => geo.startsWith(r));
      const natOk = a.nationwide && l.is_nationwide === true;
      if (!(landOk || natOk)) return false;
    }
    if (a.cpvFields.length && !a.cpvFields.includes(String(l.cpv || "").slice(0, 4))) return false;
    if (buyer && !String(l.buyer || "").toLowerCase().includes(buyer)) return false;
    if (a.leistung.length && !a.leistung.includes(String(l.naturKat))) return false;
    if (a.art.length && !a.art.some((k) => l.art === ART_MATCH[k])) return false;
    if (a.rahmen.length && !a.rahmen.includes(String(l.rahmen))) return false;
    if (a.hasDetail && !l.hasDetail) return false;
    if (a.unterlagen && !l.unterlagen) return false;
    if (a.valMin != null || a.valMax != null) {
      const v = parseWert((l.volumen as { wert?: string } | undefined)?.wert);
      if (v != null) {
        if (a.valMin != null && v < a.valMin) return false;
        if (a.valMax != null && v > a.valMax) return false;
      }
    }
    if (a.neu === "neu" && !l.neu) return false;
    if (a.neu === "folge" && l.neu) return false;
    if (a.wenigWettbewerb && (l.konk as { stufe?: string } | undefined)?.stufe !== "gering") return false;
    if (a.chance.length && !a.chance.includes(String(l.wechsel))) return false;
    if (a.aufwand.length && !a.aufwand.includes(aufwandStufe(l).stufe)) return false;
    if (a.buergschaft !== "all") {
      const b = (l.aufwand as { buergschaft?: string } | undefined)?.buergschaft;
      if (a.buergschaft === "ja" && !(b && b !== "nein")) return false;
      if (a.buergschaft === "nein" && b !== "nein") return false;
    }
    if (a.multiLot && (((l.lose as unknown[] | undefined)?.length ?? 0) <= 1)) return false;
    return true;
  });
}

// URL-Slug ↔ interner Zustand. Slugs sind ENGLISCH/universell (wie der DB-Vertrag) — über alle
// Länder gleich; die sichtbaren Rail-Labels bleiben lokalisiert. watchlist/network sind Filter
// auf „angriff", strategy ist „potenzial".
const SLUG_VIEW: Record<string, View> = {
  leads: "angriff", watchlist: "angriff", network: "angriff", strategy: "potenzial",
};
function slugOf(v: View, f: { gemerkt: boolean; netz: boolean }): string {
  if (v === "potenzial") return "strategy";
  if (f.gemerkt) return "watchlist";
  if (f.netz) return "network";
  return "leads";
}

export function ExplorerShell({ initialSlug = "leads" }: { initialSlug?: string }) {
  const [query, setQuery] = useState("");
  const [tokens, setTokens] = useState<Token[]>([]);
  const [filters, setFilters] = useState<Filters>({
    ungesichtet: false, gemerkt: initialSlug === "watchlist", kandidaten: false,
    netz: initialSlug === "network", relevant: false,
  });
  const [sortKey, setSortKey] = useState("frist");
  const [sortDir, setSortDir] = useState(1);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("uebersicht");
  const [mode, setMode] = useState<"browse" | "read" | "full">("browse");
  const [buyerDemo, setBuyerDemo] = useState("dbnetz");
  const [aktiveRegion, setAktiveRegion] = useState("ffm");
  const [potTab, setPotTab] = useState("chancen");
  // Ohne Onboarding: aspiring bidder (keine Firmen-Historie). Firmen-Blöcke im Chancen-Tab
  // bleiben leer, die Marktblöcke (Branche × Region) sind echt gefüllt.
  const [profilStufe, setProfilStufe] = useState("neu");
  const [offenerPicker, setOffenerPicker] = useState<string | null>(null);
  const [profileKey, setProfileKey] = useState<string>("");   // "" | klein | mittel | gross (Testsicht)
  const [realProfile, setRealProfile] = useState<Profile | null>(null);   // echtes Profil aus Onboarding
  const router = useRouter();
  const [adv, setAdv] = useState<Adv>(emptyAdv);
  const [panelOpen, setPanelOpen] = useState(false);
  const accountLimit = false; // Pro; §9: kommt später aus dem echten Account-Status
  const [aktiveBranche, setAktiveBranche] = useState("it");
  const profilBranche = "it";
  const [view, setView] = useState<View>(SLUG_VIEW[initialSlug] ?? "angriff");
  // #16 Verfahrenskalender — „Termine"-Modus in der Merkliste + iCal-Feed-URL
  const [kalMode, setKalMode] = useState(false);
  const [feedUrl, setFeedUrl] = useState<string | null>(null);

  // Popover-/Menü-Zustand
  const [wsOpen, setWsOpen] = useState(false);
  const [colMenuOpen, setColMenuOpen] = useState(false);
  const [headFilter, setHeadFilter] = useState<{ facet: string; rect: DOMRect } | null>(null);
  const [openRadius, setOpenRadius] = useState<number | null>(null);
  const [suggIdx, setSuggIdx] = useState(-1);
  const [tick, setTick] = useState(0);
  const bump = useCallback(() => setTick((t) => t + 1), []);
  const [branchenCounts, setBranchenCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  const [userEmail, setUserEmail] = useState<string | null>(null);

  // Beim Start: eingeloggt? → Profil aus Supabase (autoritativ); sonst lokaler Fallback.
  useEffect(() => {
    (async () => {
      const u = await currentUser().catch(() => null);
      setUserEmail(u?.email ?? null);
      if (u) { loadContracts().then((cs) => { setUserContracts(cs); bump(); }).catch(() => {}); }
      const remote = u ? await loadProfile().catch(() => null) : null;
      if (remote) {
        setRealProfile(remote);
        try { localStorage.setItem(PROFILE_KEY, JSON.stringify(remote)); } catch { /* Quota */ }
        return;
      }
      try {
        const raw = localStorage.getItem(PROFILE_KEY);
        if (raw) setRealProfile(JSON.parse(raw));
      } catch { /* ungültig → ignorieren */ }
    })();
  }, []);

  async function abmelden() {
    await logout().catch(() => {});
    try { localStorage.removeItem(PROFILE_KEY); } catch { /* egal */ }
    setRealProfile(null); setUserEmail(null); setProfileKey("");
    bump();
  }

  // Onboarding ist eine eigene Route (/onboarding, portiert aus dem v1.4-Design). Das
  // Profil kommt beim Zurücknavigieren über localStorage rein (Load-Effect beim Mount).

  // Echte Leads aus der Gold-Schicht laden — bei Mount und bei jedem Grundraum-Wechsel.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    detailLoaded.current.clear();
    fetch(`/api/leads?branche=${aktiveBranche}`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        if (Array.isArray(data)) { setLeads(data); setActiveId(null); }
        setLoading(false);
        bump();
      })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [aktiveBranche, bump]);

  // Branchen-Zähler: bei aktiver Textsuche die Treffer je Branche ziehen (nicht die
  // Maximal-Totale) — "Hamm" zeigt im Menü dann z. B. Bau 0 / IT 6 statt 31.141 / 3.883.
  // Suchbegriffe = Live-Eingabe + committete Stichwort-Tokens. Debounced; ohne Suche → Totale.
  const textTokenKey = tokens.filter((t) => t.type === "text").map((t) => t.value).join(" ");
  useEffect(() => {
    const raw = [query.trim(), textTokenKey].filter(Boolean).join(" ").trim();
    const q = raw.length >= 2 ? raw : "";
    const url = q ? `/api/branchen?q=${encodeURIComponent(q)}` : "/api/branchen";
    const id = setTimeout(() => {
      fetch(url).then((r) => r.json()).then(setBranchenCounts).catch(() => {});
    }, q ? 220 : 0);
    return () => clearTimeout(id);
  }, [query, textTokenKey]);

  // Echte Marktblöcke (Chancen-Tab) laden und bei Branchenwechsel in den Kern schieben.
  const marktRef = useRef<Record<string, unknown>>({});
  useEffect(() => {
    fetch("/api/markt").then((r) => r.json()).then((m) => {
      marktRef.current = m || {};
      setMarket(marktRef.current[aktiveBranche]);
      bump();
    }).catch(() => {});
  }, []); // einmal laden
  useEffect(() => {
    if (marktRef.current[aktiveBranche]) { setMarket(marktRef.current[aktiveBranche]); bump(); }
  }, [aktiveBranche, bump]);

  // Vom Nutzer gezogene Spaltenbreiten (px), je Spaltenschlüssel. Gehört später ins
  // gespeicherte Arbeitsplatz-Profil (Übergabenotiz §10, um „Breite" erweitert).
  const [colWidths, setColWidths] = useState<Record<string, number>>({});
  const setColWidth = useCallback(
    (key: string, w: number) => setColWidths((m) => ({ ...m, [key]: Math.max(48, Math.round(w)) })),
    []
  );

  const searchRef = useRef<HTMLInputElement>(null);
  const mainRef = useRef<HTMLDivElement>(null);
  const detailLoaded = useRef<Set<string>>(new Set());

  // Inkrementelles Rendern: erst N Zeilen zeigen, beim Scrollen nachwachsen. Hält den DOM
  // klein (ein paar Hundert Zeilen) auch bei tausenden Leads — ohne feste Zeilenhöhe.
  const [renderCount, setRenderCount] = useState(200);
  function onTableScroll(e: React.UIEvent<HTMLDivElement>) {
    const el = e.currentTarget;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 500) {
      setRenderCount((c) => c + 200);
    }
  }
  // Bei geänderter Filterung/Sortierung/Branche wieder oben anfangen.
  useEffect(() => { setRenderCount(200); }, [aktiveBranche, sortKey, sortDir, tokens, filters]);

  // Modus steuert die Split-Höhe (CSS: body[data-mode]). Beim Wechsel die per Drag
  // gesetzte Inline-Höhe entfernen, damit die Modus-Regel wieder greift.
  useEffect(() => {
    document.body.dataset.mode = activeId ? mode : "browse";
    // Potenzial-Bereich blendet Tabelle/Detail aus und zeigt die profilview (CSS §area).
    if (view === "potenzial") document.body.dataset.area = "profil";
    else document.body.removeAttribute("data-area");
    if (mainRef.current) mainRef.current.style.gridTemplateRows = "";
  }, [activeId, mode, view]);

  function startDivider() {
    const main = mainRef.current;
    if (!main) return;
    main.classList.add("dragging");
    document.body.style.userSelect = "none";
    const move = (ev: MouseEvent) => {
      const r = main.getBoundingClientRect();
      const h = Math.min(Math.max(ev.clientY - r.top, 90), r.height - 120);
      main.style.gridTemplateRows = `${h}px 6px 1fr`;
    };
    const up = () => {
      main.classList.remove("dragging");
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }

  // React ist die Wahrheit → vor jeder Ableitung in den Kern schieben, dann dessen
  // unveränderte Filter-/Sortier-Logik nutzen.
  const rows: Lead[] = useMemo(() => {
    applyState({ aktiveBranche, profilBranche, sortKey, sortDir, searchTokens: tokens, filters });
    // Testsicht (Klein/Mittel/Groß) überschreibt zum Ausprobieren; sonst das echte Profil.
    if (profileKey) applyProfile(profileKey);
    else setProfile(realProfile);
    syncLocationColumn();
    return postFilter(sorted(visible()), adv);
  }, [aktiveBranche, sortKey, sortDir, tokens, filters, tick, profileKey, realProfile, adv]);

  const suggestions = useMemo(() => (query.trim() ? suggestList(query) : []), [query]);

  // CPV-Fachgebiete des Grundraums (Top-Segmente) für den Feinfilter im Panel.
  const cpvSegments = useMemo((): Segment[] => {
    const map: Record<string, { label: string; n: number }> = {};
    for (const l of CORE) {
      const c = String((l as { cpv?: string }).cpv || "").slice(0, 4);
      if (!c) continue;
      if (!map[c]) map[c] = { label: String((l as { cpvLabel?: string }).cpvLabel || c), n: 0 };
      map[c].n++;
    }
    return Object.entries(map)
      .map(([cpv4, v]) => ({ cpv4, label: v.label, n: v.n }))
      .sort((a, b) => b.n - a.n)
      .slice(0, 14);
  }, [aktiveBranche, tick]);

  // Aktive Token je Facette → „on"-Zustand des Kopf-Trichters
  const activeFacets = useMemo(() => {
    const m: Record<string, number> = {};
    tokens.forEach((t) => { m[t.type] = (m[t.type] || 0) + 1; });
    return m;
  }, [tokens]);

  // ── Aktionen ──────────────────────────────────────────────────────────────
  const closeAllPops = useCallback(() => {
    setWsOpen(false); setColMenuOpen(false); setHeadFilter(null); setOpenRadius(null);
  }, []);

  const autoSort = useRef(true);   // solange true: Sortierung wird automatisch verwaltet
  function handleSort(key: string) {
    autoSort.current = false;      // manuelle Sortierung → Auto-Umschaltung aus
    if (key === sortKey) setSortDir((d) => -d);
    else { setSortKey(key); setSortDir(1); }
  }

  // Kombiniertes Ranking (Ticket #1) als Default-Sort, sobald ein Profil aktiv ist (beste zuerst);
  // ohne Profil zurück auf Frist. Manuelle Sortierung schaltet das ab.
  useEffect(() => {
    if (!autoSort.current) return;
    const hatProfil = !!profileKey || !!realProfile;
    setSortKey(hatProfil ? "ranking" : "frist");
    setSortDir(1);
  }, [profileKey, realProfile]);

  function markRead() {
    visible().forEach((l: Lead) => { if (l.status === "ungesichtet") l.status = "gesichtet"; });
    bump();
  }
  function toggleStar(id: string) {
    const l = CORE.find((x) => x.id === id);
    if (l) { l.merk = l.merk ? null : "manuell"; syncWatchlist(id, !!l.merk); }
    bump();
  }

  // ── Cockpit (#17) — Pipeline-/Ergebnis-Übergänge (client-seitig; #11-Meldung serverseitig) ──
  function ckApply(id: string) { const l = CORE.find((x) => x.id === id) as (Lead & { pipe?: string }) | undefined; if (l) l.pipe = "beworben"; bump(); }
  function ckStatus(id: string, s: string) { const l = CORE.find((x) => x.id === id) as (Lead & { pipe?: string }) | undefined; if (l) l.pipe = s; bump(); }
  function ckOutcome(id: string, o: "gewonnen" | "verloren") {
    const l = CORE.find((x) => x.id === id) as (Lead & { outcome?: string; cockpitProv?: string }) | undefined;
    if (l) { l.outcome = o; l.cockpitProv = "korrigiert"; } // Ergebnismeldung (#11) ist Nebenprodukt der Pflege
    bump();
  }
  function ckConfirm(id: string) { const l = CORE.find((x) => x.id === id) as (Lead & { cockpitProv?: string }) | undefined; if (l) l.cockpitProv = "bestaetigt"; bump(); }

  // ── Lead-Detail öffnen/schließen/Tabs ──────────────────────────────────────
  function openLead(id: string) {
    const l = CORE.find((x) => x.id === id) as (Lead & { status?: string; beschreibung?: string }) | undefined;
    if (l && l.status === "ungesichtet") l.status = "gesichtet";
    setActiveId(id);
    setActiveTab("uebersicht");
    setMode("read");
    bump();
    recordLeadClick(id);   // Attribution: erster Detail-Klick (Success-Fee-Gate #6)
    // Schwere Felder (Beschreibung + Vergabestellen-Profil) einmalig nachladen.
    if (l && !detailLoaded.current.has(id)) {
      detailLoaded.current.add(id);
      fetch(`/api/lead-detail?branche=${aktiveBranche}&id=${encodeURIComponent(id)}`)
        .then((r) => r.json())
        .then((d) => { if (d && typeof d === "object" && !d.error) { Object.assign(l, d); bump(); } })
        .catch(() => detailLoaded.current.delete(id));
    }
  }
  function closeLead() {
    setActiveId(null);
    setMode("browse");
  }
  function setTab(k: string) {
    setActiveTab(k);
    setMode((m) => (m === "browse" ? "read" : m));
    // Bewertung ist das Erfolgsprämien-Gate (§4): Klick auf „Bewertung" markiert analysiert.
    if (k === "analyse" && !accountLimit) {
      const l = CORE.find((x) => x.id === activeId) as (Lead & { status?: string; seen?: string }) | undefined;
      if (l) { l.status = "analysiert"; l.seen = "ANALYSIERT"; }
      if (activeId) recordAnalysis(activeId);   // Attribution: erster Bewertungs-Klick
    }
    bump();
  }
  function setWf(k: string) {
    const l = CORE.find((x) => x.id === activeId) as (Lead & { userStatus?: string | null }) | undefined;
    if (!l) return;
    l.userStatus = l.userStatus === k ? null : k;
    bump();
  }
  function toggleExpand() { setMode((m) => (m === "full" ? "read" : "full")); }

  // Interaktionen im Tab-Körper (delegiert aus DetailPanel)
  function onBodyAction(action: string, value: string, el: HTMLElement) {
    switch (action) {
      case "anav": {
        document.getElementById("an-" + value)?.scrollIntoView({ behavior: "smooth", block: "start" });
        break;
      }
      case "openlead": openLead(value); break;
      case "editprofil": router.push("/onboarding"); break;   // Profil-Tab → selbe Route wie der Topbar-Button
      case "region": setAktiveRegion(value); bump(); break;
      case "buyerdemo": setBuyerDemo(value); bump(); break;
      case "tonetz": case "netz": switchView("netzwerk"); break;
      case "buyerleads": {
        const l = CORE.find((x) => x.id === activeId) as (Lead & { buyer?: string; buyerShort?: string }) | undefined;
        const label = l?.buyer || value;
        setTokens((ts) => [...ts.filter((t) => t.type !== "buyer"), { type: "buyer", value, label }]);
        setMode("browse"); setActiveId(null);
        break;
      }
      case "grp": {
        const g = offeneGruppen as Set<string>;
        g.has(value) ? g.delete(value) : g.add(value);
        bump();
        break;
      }
      case "cmtsend": {
        const ta = el.closest(".detail")?.querySelector<HTMLTextAreaElement>("[data-cmt]");
        const body = ta?.value.trim();
        if (body) {
          const l = CORE.find((x) => x.id === activeId) as (Lead & { comments?: unknown[] }) | undefined;
          l?.comments?.push({ author: "Du", initials: "DK", ts: "gerade eben", body });
          bump();
        }
        break;
      }
      case "ptab": setPotTab(value); break;
      case "pstufe": setProfilStufe(value); break;
      case "partner": {
        const a = angaben as { partner?: boolean };
        a.partner = !a.partner;
        if (!a.partner) { (netzInteresse as Set<string>).clear(); (netzFreigabe as Set<string>).clear(); }
        bump();
        break;
      }
      case "angset": {
        const [k, v] = value.split(":");
        const arr = (angaben as unknown as Record<string, string[]>)[k];
        if (arr && !arr.includes(v)) arr.push(v);
        setOffenerPicker(null);
        bump();
        break;
      }
      case "angrm": {
        const [k, v] = value.split(":");
        const rec = angaben as unknown as Record<string, string[]>;
        if (rec[k]) rec[k] = rec[k].filter((x) => x !== v);
        bump();
        break;
      }
      case "angadd": setOffenerPicker((p) => (p === value ? null : value)); bump(); break;
      case "editbestand": {
        // „Verträge pflegen" → zurück in die Liste im Bestand-Modus (vereinfacht: Liste zeigen)
        setView("angriff");
        setFilters((f) => ({ ...f, kandidaten: false }));
        break;
      }
      default: break; // mark/netzfrei — Feinschliff
    }
  }
  function toggleNetz(id: string) {
    const ni = netzInteresse as Set<string>;
    ni.has(id) ? ni.delete(id) : ni.add(id);
    bump();
  }
  function toggleOwn(id: string, ans: string) {
    const l = CORE.find((x) => x.id === id) as (Lead & { eigen?: boolean; eigenBestaetigt?: boolean }) | undefined;
    if (l) {
      l.eigenBestaetigt = ans === "ja";
      l.eigen = ans === "ja";
      if (ans !== "ja" && activeId === id) setActiveId(null);
    }
    bump();
  }
  function toggleCol(key: string) {
    const c = (COLS as { key: string; on: boolean; lock?: boolean; _userOff?: boolean }[]).find((x) => x.key === key);
    if (c && !c.lock) { c.on = !c.on; if (key === "region") c._userOff = !c.on; bump(); }
  }
  // Spalten umordnen (Prototyp-Verhalten: vor/nach dem Ziel je nach Cursorseite)
  function reorderCol(fromKey: string, toKey: string, after: boolean) {
    if (fromKey === toKey || toKey === "star") return;
    const cols = COLS as { key: string }[];
    const from = cols.findIndex((c) => c.key === fromKey);
    const moved = cols.splice(from, 1)[0];
    let to = cols.findIndex((c) => c.key === toKey);
    if (after) to++;
    cols.splice(to, 0, moved);
    bump();
  }

  // Such-Tokens
  function commitSearch(pick?: number | "raw") {
    let tok: Token | null = null;
    if (typeof pick === "number") tok = suggestions[pick] as Token;
    else if (pick === "raw") tok = classifyQuery(query) as Token;
    else if (suggIdx >= 0 && suggIdx < suggestions.length) tok = suggestions[suggIdx] as Token;
    else tok = classifyQuery(query) as Token;
    if (tok && !tokens.some((t) => t.type === tok!.type && t.value === tok!.value)) {
      setTokens((ts) => [...ts, { type: tok!.type, value: tok!.value, label: tok!.label }]);
    }
    setQuery(""); setSuggIdx(-1);
  }
  function removeToken(i: number) { setTokens((ts) => ts.filter((_, k) => k !== i)); }
  function clearAll() {
    setTokens([]); setQuery("");
    setFilters((f) => ({ ...f, ungesichtet: false, gemerkt: false }));
  }
  function toggleFacetToken(name: string, v: string, label: string) {
    setTokens((ts) => {
      const i = ts.findIndex((t) => t.type === name && t.value === v);
      return i >= 0 ? ts.filter((_, k) => k !== i) : [...ts, { type: name, value: v, label }];
    });
  }
  function togglePlace(region: string, label: string) {
    setTokens((ts) => {
      const i = ts.findIndex((t) => t.type === "ort" && t.value === region);
      return i >= 0 ? ts.filter((_, k) => k !== i) : [...ts, { type: "ort", value: region, label }];
    });
  }
  function setRadius(i: number, km: number) {
    setTokens((ts) => ts.map((t, k) => (k === i ? { ...t, radius: km || null } : t)));
    setOpenRadius(null);
  }

  // Rail-Sichten
  function switchView(next: View) {
    closeAllPops();
    setActiveId(null);
    const netzCol = (COLS as { key: string; on: boolean }[]).find((c) => c.key === "netz");
    if (next === "angriff") {
      setFilters((f) => ({ ...f, netz: false, gemerkt: false }));
      if (netzCol) netzCol.on = false;
    } else if (next === "merkliste") {
      setFilters((f) => ({ ...f, gemerkt: !f.gemerkt, netz: false }));
      if (netzCol) netzCol.on = false;
    } else if (next === "netzwerk") {
      setFilters((f) => ({ ...f, netz: !f.netz, gemerkt: false }));
      if (netzCol) netzCol.on = !filters.netz;
    }
    const nextView: View = next === "merkliste" && filters.gemerkt ? "angriff" : next;
    setView(nextView);
    // URL spiegelt die Ansicht (bookmarkbar), ohne Next-Navigation → kein Remount.
    const nextFilters = {
      gemerkt: next === "merkliste" ? !filters.gemerkt : false,
      netz: next === "netzwerk" ? !filters.netz : false,
    };
    if (typeof window !== "undefined") {
      window.history.pushState(null, "", "/" + slugOf(nextView, nextFilters));
    }
    bump();
  }

  // Zurück/Vor im Browser → Ansicht aus der URL wiederherstellen.
  useEffect(() => {
    function onPop() {
      const slug = window.location.pathname.replace(/^\//, "").split("/")[0] || "leads";
      setView(SLUG_VIEW[slug] ?? "angriff");
      setFilters((f) => ({ ...f, gemerkt: slug === "watchlist", netz: slug === "network" }));
      const netzCol = (COLS as { key: string; on: boolean }[]).find((c) => c.key === "netz");
      if (netzCol) netzCol.on = slug === "network";
      bump();
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [bump]);

  function setBranche(k: string) { setAktiveBranche(k); setWsOpen(false); setActiveId(null); }
  function resetBranche() { setAktiveBranche(profilBranche); setWsOpen(false); setActiveId(null); }

  // Tastatur
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement;
      if (e.key === "/" && !el.matches("input,textarea")) {
        e.preventDefault(); searchRef.current?.focus(); return;
      }
      if (el.matches("input,textarea")) return;
      if (e.key === "Escape" && activeId) { setActiveId(null); return; }
      if (!["ArrowDown", "ArrowUp"].includes(e.key)) return;
      if (!rows.length) return;
      e.preventDefault();
      const i = rows.findIndex((l) => l.id === activeId);
      const n = e.key === "ArrowDown" ? rows[Math.min(i + 1, rows.length - 1)] : rows[Math.max(i - 1, 0)];
      setActiveId(n.id);
      document.querySelector(`tr[data-id="${n.id}"]`)?.scrollIntoView({ block: "nearest" });
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [rows, activeId]);

  // Klick außerhalb schließt Popovers
  useEffect(() => {
    function onDown(e: MouseEvent) {
      const t = e.target as HTMLElement;
      if (!t.closest(".workspace")) setWsOpen(false);
      if (!t.closest(".colcfg")) setColMenuOpen(false);
      if (!t.closest(".has-filter") && !t.closest(".headpop")) setHeadFilter(null);
      if (!t.closest(".ftoken")) setOpenRadius(null);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  function onSearchKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") { e.preventDefault(); setSuggIdx((i) => Math.min(i + 1, suggestions.length)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSuggIdx((i) => Math.max(i - 1, -1)); }
    else if (e.key === "Enter") { e.preventDefault(); commitSearch(); }
    else if (e.key === "Escape") { setQuery(""); (e.target as HTMLInputElement).blur(); }
    else if (e.key === "Backspace" && query === "" && tokens.length) {
      setTokens((ts) => ts.slice(0, -1));
    }
  }

  const branchen = BRANCHEN as Record<string, string>;
  const unread = rows.filter((l) => l.status === "ungesichtet").length;
  const merkN = CORE.filter((l) => l.merk).length;

  return (
    <div className="app" data-view={view === "netzwerk" ? "angriff" : "angriff"}>
      <header className="topbar">
        <div className="brandcell">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/govisor-wordmark.png" alt="goVisor" className="brandlogo" />
        </div>
        <Workspace
          aktiveBranche={aktiveBranche}
          profilBranche={profilBranche}
          open={wsOpen}
          counts={branchenCounts}
          onToggle={() => setWsOpen((o) => !o)}
          onSet={setBranche}
          onReset={resetBranche}
        />
        <div className="maincol">
          <div className="toolbar">
            <div className="searchwrap">
              <label className="tsearch">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
                  <circle cx="11" cy="11" r="7" />
                  <path d="m20 20-3.4-3.4" />
                </svg>
                <input
                  ref={searchRef}
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setSuggIdx(-1); }}
                  onKeyDown={onSearchKey}
                  placeholder="Suchen — Ort, PLZ, Auftraggeber, Stichwort"
                  aria-label="Suchen"
                  autoComplete="off"
                />
                <kbd className="tkbd">/</kbd>
              </label>
              <Suggestions query={query} list={suggestions as never} suggIdx={suggIdx} onPick={commitSearch} />
            </div>
            <div className="colcfg">
              <button className="colbtn" type="button" onClick={() => setPanelOpen(true)} title="Detailfilter">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 5h18l-7 8v5l-4 2v-7L3 5Z" />
                </svg>
                Filter{advCount(adv) ? <span className="filt-n">{advCount(adv)}</span> : null}
              </button>
            </div>
            <div className="colcfg">
              <button className="colbtn" type="button" onClick={() => setColMenuOpen((o) => !o)}>
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M3 5h18M3 12h18M3 19h18" />
                </svg>
                Spalten
              </button>
              <ColumnMenu open={colMenuOpen} onToggleCol={toggleCol} />
            </div>
            <ExportMenu rows={rows} view={filters.relevant ? "passend" : "alle"} />
            <div className="colcfg">
              <button className={`colbtn ${realProfile ? "colbtn-on" : ""}`} type="button"
                onClick={() => router.push("/onboarding")}
                title={realProfile ? "Profil ansehen/bearbeiten" : "Profil einrichten — schaltet echte Relevanz frei"}>
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 12a4 4 0 100-8 4 4 0 000 8ZM4 21a8 8 0 0116 0" />
                </svg>
                {realProfile ? (realProfile.firma || "Profil").slice(0, 22) : "Profil einrichten"}
              </button>
            </div>
            <div className="testsicht" title="Test: Relevanz gegen ein simuliertes Firmenprofil berechnen">
              <span className="ts-k">Testsicht</span>
              {["", "klein", "mittel", "gross"].map((k) => (
                <button
                  key={k || "aus"}
                  className={`ts-o ${profileKey === k ? "on" : ""}`}
                  onClick={() => {
                    setProfileKey(k);
                    if (!k) setFilters((f) => ({ ...f, relevant: false }));
                  }}
                  title={k ? (PROFILES as Record<string, { sub: string }>)[k].sub : "keine Profil-Simulation"}
                >
                  {k ? (PROFILES as Record<string, { label: string }>)[k].label.replace("unternehmen", "").replace("betrieb", "") : "Aus"}
                </button>
              ))}
              {profileKey ? (
                <button
                  className={`ts-only ${filters.relevant ? "on" : ""}`}
                  onClick={() => setFilters((f) => ({ ...f, relevant: !f.relevant }))}
                >
                  nur passende
                </button>
              ) : null}
            </div>
            <div className="tstatus">
              <span className="tcount">
                <b>{rows.length}</b> von <span>{CORE.length}</span>
              </span>
              <button
                className="markread"
                onClick={markRead}
                disabled={unread === 0}
                title="Alle sichtbaren Leads als gesehen markieren"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 6 9.5 15 6 11.5" />
                  <path d="M22 6l-8.5 9L13 14.5" />
                </svg>
                <span>{unread ? `${unread} als gesehen` : "alle gesehen"}</span>
              </button>
            </div>
          </div>
          <FilterBar
            tokens={tokens}
            openRadius={openRadius}
            onRemove={removeToken}
            onClear={clearAll}
            onToggleRadius={(i) => setOpenRadius((r) => (r === i ? null : i))}
            onSetRadius={setRadius}
          />
        </div>
        <div className="acctcell">
          <a className="rolelink" href="/authority" title="Zur Vergabestellen-Sicht (Vergabeblick) — in Produktion rollen-gegatet">↔ Vergabestelle</a>
          {userEmail ? (
            <div className="acct">
              <Link className="acct-mail" href="/settings" title="Einstellungen">{userEmail}</Link>
              <button className="acct-out" onClick={abmelden} title="Abmelden">Abmelden</button>
            </div>
          ) : (
            <Link className="acct-in" href="/login">Anmelden</Link>
          )}
        </div>
      </header>

      <div className="body">
        <nav className="rail" aria-label="Ansicht">
          <button className="viewbtn" aria-current={view === "angriff" && !filters.gemerkt && !filters.netz ? "true" : undefined} onClick={() => switchView("angriff")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4" />
              <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
            </svg>
            <b>Akquise</b>
          </button>
          <button className="viewbtn" aria-current={filters.gemerkt ? "true" : undefined} onClick={() => switchView("merkliste")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
              <path d="m12 4 2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4-3.9-3.8 5.4-.8L12 4Z" />
            </svg>
            <b>Merkliste</b>
            <span className="railcount">{merkN}</span>
          </button>
          <button className="viewbtn" aria-current={filters.netz ? "true" : undefined} onClick={() => switchView("netzwerk")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="6" cy="7" r="2.6" /><circle cx="18" cy="7" r="2.6" /><circle cx="12" cy="18" r="2.6" />
              <path d="M7.6 9.1 10.6 15.7M16.4 9.1 13.4 15.7M8.6 7h6.8" />
            </svg>
            <b>Netzwerk</b>
          </button>
          <span className="railsep" />
          <button className="viewbtn" aria-current={view === "potenzial" ? "true" : undefined} onClick={() => switchView("potenzial")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 20V13M9.3 20V8M14.7 20v-4M20 20V4" /><path d="M4 20h16" />
            </svg>
            <b>Strategie</b>
          </button>
          <div className="railfoot">
            <span className="verlabel" title="Prototyp-Version">v4.4</span>
            <button className="planbadge" title="Kontostatus">
              <span className="plan-ring" /><span className="plan-lbl">Pro</span>
            </button>
          </div>
        </nav>

        <div className="main" ref={mainRef}>
          {view === "potenzial" ? (
            <section className="profilview">
              <StrategieView
                potTab={potTab}
                profilStufe={profilStufe}
                offenerPicker={offenerPicker}
                aktiveBranche={aktiveBranche}
                accountLimit={accountLimit}
                tick={tick}
                onBodyAction={onBodyAction}
              />
            </section>
          ) : (
          <>
          <section className="tablewrap">
            {filters.gemerkt && (
              <div className="wl-toggle" role="tablist" aria-label="Merkliste-Ansicht">
                <button role="tab" aria-selected={!kalMode} className={!kalMode ? "on" : ""} onClick={() => setKalMode(false)}>Cockpit</button>
                <button role="tab" aria-selected={kalMode} className={kalMode ? "on" : ""} onClick={() => setKalMode(true)}>Termine</button>
              </div>
            )}
            {filters.gemerkt && kalMode ? (
              <Kalender
                rows={rows}
                onSelect={openLead}
                feedUrl={feedUrl}
                onSubscribe={async () => {
                  const token = await getOrCreateCalendarFeed();
                  if (token) setFeedUrl(`${window.location.origin}/api/calendar/${token}.ics`);
                }}
              />
            ) : filters.gemerkt ? (
              <div className="ckscroll">
                <Cockpit
                  rows={CORE.filter((l) => l.merk || (l as { pipe?: string }).pipe || (l as { outcome?: string }).outcome || (l.eigen && l.eigenBestaetigt !== false))}
                  onSelect={openLead}
                  onApply={ckApply}
                  onStatus={ckStatus}
                  onOutcome={ckOutcome}
                  onConfirm={ckConfirm}
                />
              </div>
            ) : (
            <div className="tablescroll" onScroll={onTableScroll}>
              <LeadTable
                rows={rows}
                limit={renderCount}
                sortKey={sortKey}
                sortDir={sortDir}
                activeId={activeId}
                activeFacets={activeFacets}
                onSort={handleSort}
                onSelect={openLead}
                onStar={toggleStar}
                onNetz={toggleNetz}
                onOwn={toggleOwn}
                onHeadFilter={(facet, rect) =>
                  setHeadFilter((h) => (h && h.facet === facet ? null : { facet, rect }))
                }
                onReorder={reorderCol}
                colWidths={colWidths}
                onResize={setColWidth}
              />
            </div>
            )}
          </section>

          <div className="divider" role="separator" aria-orientation="horizontal" onMouseDown={startDivider} />

          <section className="detail">
            <DetailPanel
              activeId={activeId}
              activeTab={activeTab}
              mode={mode}
              tick={tick}
              buyerDemo={buyerDemo}
              aktiveRegion={aktiveRegion}
              accountLimit={accountLimit}
              onTab={setTab}
              onClose={closeLead}
              onExpand={toggleExpand}
              onWf={setWf}
              onStar={toggleStar}
              onBodyAction={onBodyAction}
            />
          </section>
          </>
          )}
        </div>
      </div>

      <FilterPanel
        open={panelOpen}
        adv={adv}
        resultCount={rows.length}
        segments={cpvSegments}
        onChange={setAdv}
        onClose={() => setPanelOpen(false)}
        onReset={() => setAdv(emptyAdv)}
      />

      {headFilter ? (
        <HeaderFilterPopover
          facet={headFilter.facet}
          rect={headFilter.rect}
          tokens={tokens}
          onToggleFacet={toggleFacetToken}
          onTogglePlace={togglePlace}
        />
      ) : null}
    </div>
  );
}
