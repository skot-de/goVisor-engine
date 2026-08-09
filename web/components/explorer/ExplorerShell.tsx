"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  LEADS, BRANCHEN, COLS, applyState, visible, sorted, syncLocationColumn,
  suggestList, classifyQuery, netzInteresse, netzFreigabe, offeneGruppen, angaben, setLeads, setMarket, setPlzGeo, setPlzLand,
  setProfile, setUserContracts, parseWert, aufwandStufe,
} from "@/lib/explorerCore";
import { loadContracts } from "@/lib/supabase/contracts";
import { buildProfile, brancheFromProfile } from "@/lib/profileEngine";
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
import { ColumnMenu, FilterBar, Suggestions, HeaderFilterPopover } from "./parts";
import { AppRail, type RailId } from "./Rail";

type Lead = { id: string; branche?: string; merk?: unknown; [k: string]: unknown };
type Token = { type: string; value: string; label: string; radius?: number | null; coord?: number[] };
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
    if (a.staaten.length && !a.staaten.includes(String(l.land || "DE"))) return false;
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
    if (a.relevanz.length && !a.relevanz.includes(String(l.relevanz))) return false;
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

// Ticket #23 Checkliste: Abhak-Zustand je Lead persistieren + TOC-Fortschritt aktualisieren (DOM-only).
function clPersist(root: HTMLElement | null) {
  if (!root) return;
  const lead = root.dataset.clroot;
  const items = root.querySelectorAll<HTMLElement>(".item[data-clitem]");
  const state: Record<string, boolean> = {};
  let dn = 0;
  items.forEach((it) => { if (it.classList.contains("done")) { state[it.dataset.clitem || ""] = true; dn++; } });
  if (lead) { try { localStorage.setItem("govisor.checkstate." + lead, JSON.stringify(state)); } catch { /* voll */ } }
  const n = root.querySelector<HTMLElement>(".cl-doneN"); if (n) n.textContent = String(dn);
  const bar = root.querySelector<HTMLElement>(".cl-tprog");
  if (bar) bar.style.width = (items.length ? Math.round((dn / items.length) * 100) : 0) + "%";
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
  const [awAlertOff, setAwAlertOff] = useState(false);   // #24 Zuschlag-Alert-Band ausgeblendet
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
  const [realProfile, setRealProfile] = useState<Profile | null>(null);   // echtes Profil aus Onboarding
  const router = useRouter();
  const [adv, setAdv] = useState<Adv>(emptyAdv);
  const [panelOpen, setPanelOpen] = useState(false);
  const accountLimit = false; // Pro; §9: kommt später aus dem echten Account-Status
  const [aktiveBranche, setAktiveBranche] = useState("it");
  // Grundraum aus dem Profil (CPV) — nicht mehr hart „it". Fällt auf „it" zurück, solange kein Profil da ist.
  const profilBranche = brancheFromProfile(realProfile as unknown as Parameters<typeof brancheFromProfile>[0]) || "it";
  const brancheManual = useRef(false);   // true, sobald der Nutzer den Grundraum selbst umschaltet
  const [view, setView] = useState<View>(SLUG_VIEW[initialSlug] ?? "angriff");
  // #16 Verfahrenskalender — „Termine"-Modus in der Merkliste + iCal-Feed-URL
  const [kalMode, setKalMode] = useState(false);
  const [feedUrl, setFeedUrl] = useState<string | null>(null);

  // Popover-/Menü-Zustand
  const [colMenuOpen, setColMenuOpen] = useState(false);
  const [headFilter, setHeadFilter] = useState<{ facet: string; rect: DOMRect } | null>(null);
  const [openRadius, setOpenRadius] = useState<number | null>(null);
  const [suggIdx, setSuggIdx] = useState(-1);
  const [tick, setTick] = useState(0);
  const bump = useCallback(() => setTick((t) => t + 1), []);
  const [branchenCounts, setBranchenCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  const [userEmail, setUserEmail] = useState<string | null>(null);
  // Echter Zugangsstatus statt hartkodiertem „Pro"-Aufkleber (Free bis der Account etwas anderes sagt).
  const [plan, setPlan] = useState<"free" | "paid" | "cancelled">("free");
  const [planOpen, setPlanOpen] = useState(false);
  // Vorauswahl = das Produktversprechen („wir sortieren vor, ihr arbeitet nur das Sinnvolle ab").
  // Standard AN; ohne Profil wirkungslos, weil dann keine Relevanz berechnet werden kann.
  const [vorauswahl, setVorauswahl] = useState(true);

  // Beim Start: eingeloggt? → Profil aus Supabase (autoritativ); sonst lokaler Fallback.
  useEffect(() => {
    (async () => {
      const u = await currentUser().catch(() => null);
      setUserEmail(u?.email ?? null);
      if (u) {
        // echten Zugangsstatus laden (Free bleibt der ehrliche Default, wenn nichts hinterlegt ist)
        import("@/lib/supabase/account").then(({ loadAccount }) => loadAccount())
          .then((a) => { const p = a?.plan; if (p === "paid" || p === "cancelled") setPlan(p); })
          .catch(() => {});
      }
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

  // Nach dem Profil-Laden den Grundraum auf die eigene Branche stellen — sonst sieht ein Bau-Kunde
  // den IT-Default. Nur solange der Nutzer nicht selbst umgeschaltet hat.
  useEffect(() => {
    if (brancheManual.current) return;
    const b = brancheFromProfile(realProfile as unknown as Parameters<typeof brancheFromProfile>[0]);
    if (b) setAktiveBranche((cur) => (cur === b ? cur : b));
  }, [realProfile]);   // eslint-disable-line react-hooks/exhaustive-deps

  async function abmelden() {
    await logout().catch(() => {});
    try { localStorage.removeItem(PROFILE_KEY); } catch { /* egal */ }
    setRealProfile(null); setUserEmail(null); brancheManual.current = false; setPlan("free");
    bump();
  }

  // Onboarding ist eine eigene Route (/onboarding, portiert aus dem v1.4-Design). Das
  // Profil kommt beim Zurücknavigieren über localStorage rein (Load-Effect beim Mount).

  // Echte Leads aus der Gold-Schicht laden — bei Mount und bei jedem Grundraum-Wechsel.
  // Deep-Link: ?lead=<id>&branche=<br>&tab=docs öffnet einen Lead direkt (z. B. eine analysierte
  // Unterlagen-Checkliste), ohne die Liste durchsuchen zu müssen. Einmalig beim Laden.
  const deepRef = useRef<{ lead: string; tab: string } | null>(null);
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const lead = p.get("lead");
    if (!lead) return;
    deepRef.current = { lead, tab: p.get("tab") || "docs" };
    const br = p.get("branche");
    if (br) { brancheManual.current = true; setAktiveBranche(br); }   // expliziter Deep-Link gewinnt vor Profil-Ableitung
  }, []);

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
        const dl = deepRef.current;
        if (dl && Array.isArray(data) && data.some((x: { id?: string }) => String(x.id) === dl.lead)) {
          deepRef.current = null;
          setTimeout(() => { openLead(dl.lead); setTimeout(() => setActiveTab(dl.tab), 0); }, 0);
        }
      })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [aktiveBranche, bump]);

  // Branchen-Zähler: bei aktiver Textsuche die Treffer je Branche ziehen (nicht die
  // Maximal-Totale) — "Hamm" zeigt im Menü dann z. B. Bau 0 / IT 6 statt 31.141 / 3.883.
  // Suchbegriffe = Live-Eingabe + committete Stichwort-Tokens. Debounced; ohne Suche → Totale.
  const textTokenKey = tokens.filter((t) => t.type === "text").map((t) => t.value).join(" ");
  // Aktiver Umkreis-Token (Stadt/PLZ mit Koordinate) → die Branchen-Zähler im Menü auf genau
  // diesen Ort+Radius beziehen (#27), statt globale Totale zu zeigen.
  const ortGeo = tokens.find(
    (t) => t.type === "ort" && Array.isArray((t as { coord?: number[] }).coord),
  ) as { coord?: number[]; radius?: number } | undefined;
  const geoKey = ortGeo?.coord ? `${ortGeo.coord[0]},${ortGeo.coord[1]},${ortGeo.radius || 25}` : "";
  useEffect(() => {
    const raw = [query.trim(), textTokenKey].filter(Boolean).join(" ").trim();
    // Reine PLZ/Zahl ist eine Geo-Suche (kein Textmatch) → nicht als Textzähler werten,
    // sonst zeigte das Menü fälschlich 0 überall. Der Umkreis kommt separat als lat/lon/r.
    const q = (raw.length >= 2 && !/^\d{2,5}$/.test(raw)) ? raw : "";
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (geoKey) { const [la, lo, rr] = geoKey.split(","); params.set("lat", la); params.set("lon", lo); params.set("r", rr); }
    const qs = params.toString();
    const url = qs ? `/api/branchen?${qs}` : "/api/branchen";
    const id = setTimeout(() => {
      fetch(url).then((r) => r.json()).then(setBranchenCounts).catch(() => {});
    }, (q || geoKey) ? 220 : 0);
    return () => clearTimeout(id);
  }, [query, textTokenKey, geoKey]);

  // PLZ→Koordinate-Tabelle einmal laden (für die echte Umkreissuche). ~450 KB, cache-fähig.
  useEffect(() => {
    fetch("/api/plz-geo").then((r) => r.json()).then(setPlzGeo).catch(() => {});
  }, []);
  // Aktiver DACH-Länderfilter → getippte 4-stellige PLZ (CH/AT kollidieren) dorthin auflösen.
  useEffect(() => {
    setPlzLand(adv.staaten.length === 1 ? adv.staaten[0] : "");
  }, [adv.staaten]);

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
  // Vollständige, gefilterte Liste INKLUSIVE Zuschläge — Basis für Zähler und das Zuschlags-Band.
  const alleRows: Lead[] = useMemo(() => {
    applyState({ aktiveBranche, profilBranche, sortKey, sortDir, searchTokens: tokens, filters });
    setProfile(realProfile);
    syncLocationColumn();
    return postFilter(sorted(visible()), adv);
  }, [aktiveBranche, sortKey, sortDir, tokens, filters, tick, realProfile, adv]);

  // Akquise zeigt, worauf man sich BEWERBEN kann. Erteilte Zuschläge (#24) sind Marktbeobachtung
  // (wer hat gewonnen → wer kauft jetzt zu) und würden hier oben stehen, weil sie nach
  // Zuschlagsdatum ganz vorn sortieren. Deshalb nur, wenn die Phase ausdrücklich gewählt ist.
  // `alleRows` behält sie — daraus speist sich das Zuschlags-Band.
  // Die Vorauswahl gilt nur für die Akquise — Merkliste/Netzwerk sind eigene Linsen.
  // Rail-Punkt ↔ interne Ansicht. Getrennt gehalten: die Rail spricht die Sprache des
  // Nutzers ("akquise"), die Shell ihre eigene ("angriff").
  const RAIL_VIEW: Record<string, View> = {
    akquise: "angriff", merkliste: "merkliste", netzwerk: "netzwerk", strategie: "potenzial",
  } as Record<string, View>;
  const aktiverRailPunkt: RailId =
    view === "potenzial" ? "strategie"
    : filters.gemerkt ? "merkliste" : filters.netz ? "netzwerk" : "akquise";

  const istAkquise = view === "angriff" && !filters.gemerkt && !filters.netz;
  // Die Vorauswahl sucht bewerbbare Ausschreibungen (src='f02'). Wer ausdrücklich die
  // Zuschlags-Phase wählt, will genau das Gegenteil sehen — dann muss sie schweigen.
  // Vorher filterte sie die Zuschläge restlos weg: „Zuschläge ansehen" landete auf 0 von 0.
  const zuschlagsSicht = adv.phases.includes("award");

  const rows: Lead[] = useMemo(() => {
    const ohneAwards = adv.phases.includes("award") ? alleRows : alleRows.filter((l) => l.src !== "award");
    // Vorauswahl (gemessen an ENGIE/Cancom/Rosenbauer: 5.911→72, 3.974→23, 5.979→77):
    // Es bleibt, worauf man sich HEUTE sinnvoll bewerben kann —
    //   · echte Ausschreibung (keine Ankündigung, kein bloßes Vertragsende)
    //   · noch mindestens 3 Tage Zeit
    //   · Relevanz hoch (CPV-6-genau + Region + Volumen)
    //   · kein harter Blocker (Bürgschaft übersteigt Rahmen / bewusst ausgeschlossen)
    //   · Aufwand nicht „hoch" — unbekannter Aufwand fliegt NICHT raus (Unbekanntes schließt nie aus)
    // Ohne Profil ist die Relevanz für alles „na" → wir sortieren nicht vor, statt alles zu leeren.
    if (!vorauswahl || !realProfile || !istAkquise || zuschlagsSicht) return ohneAwards;
    return ohneAwards.filter((l) => {
      if (l.src !== "f02") return false;
      const t = (l.frist as { tage?: number } | undefined)?.tage ?? (l.tage as number | null);
      if (typeof t !== "number" || t < 3) return false;
      if (l.relevanz !== "hoch") return false;
      const m = l.match as { blocker?: { art: string }[] } | undefined;
      if (m?.blocker?.some((b) => b.art === "buergschaft" || b.art === "ausschluss")) return false;
      return aufwandStufe(l).stufe !== "hoch";
    });
  }, [alleRows, adv.phases, vorauswahl, realProfile, istAkquise, zuschlagsSicht]);

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
    setColMenuOpen(false); setHeadFilter(null); setOpenRadius(null);
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
    // Erster Blick auf die Akquise = die Leads, die zuerst Arbeit verdienen: Relevanz × Chance ×
    // wenig Aufwand × genug Frist (topScore). Auch ohne Profil sinnvoll (dann ohne Relevanz-Anteil)
    // — die Alternative „nach Frist" stellt die fast abgelaufenen nach oben, also das Gegenteil.
    setSortKey("ranking");
    setSortDir(1);
  }, [realProfile]);

  // Verlauf-Protokoll (#30): Nutzeraktionen landen im Team-Tab „Verlauf" (l.log). Angehängt
  // (nicht vorangestellt), damit der Erst-Eintrag oben bleibt — wie in den Seed-Logs.
  function logEvent(l: (Lead & { log?: unknown[] }) | undefined, kind: string, text: string) {
    if (!l) return;
    (l.log = (l.log as unknown[]) || []).push({ kind, text, who: "Du", ts: "gerade eben" });
  }
  function toggleStar(id: string) {
    const l = CORE.find((x) => x.id === id);
    if (l) {
      l.merk = l.merk ? null : "manuell";
      syncWatchlist(id, !!l.merk);
      logEvent(l, "watch", l.merk ? "Zur Merkliste hinzugefügt" : "Von der Merkliste entfernt");
    }
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
    const l = CORE.find((x) => x.id === id) as (Lead & { status?: string; beschreibung?: string; log?: unknown[] }) | undefined;
    if (l && l.status === "ungesichtet") l.status = "gesichtet";
    // Verlauf nie ganz leer: beim ERSTEN Öffnen einen Auftakt-Eintrag setzen (length-Guard → einmalig).
    if (l && (!l.log || (l.log as unknown[]).length === 0)) logEvent(l, "create", "Lead in goVisor geöffnet");
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
    const WFLABEL: Record<string, string> = { interessant: "Interessant", pruefung: "In Prüfung", fragen: "Offene Fragen", verworfen: "Verworfen" };
    logEvent(l, "status", l.userStatus ? `Status → ${WFLABEL[k] || k}` : "Status zurückgesetzt");
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
      // #24/#25: Firmenprofil des Zuschlags-Gewinners (eigene Seite) + Merken aus dem Zuschlag-Detail
      case "firma": if (value) window.location.href = "/firma?id=" + encodeURIComponent(value); break;
      case "merk": toggleStar(value); break;
      case "saveblock": {
        // §7.1 Kombi-Button: editierten Baustein (oder das Zitat) in die Zwischenablage kopieren
        // UND in die Bausteinbibliothek speichern (§9.1). Lokal (Ebene B) — die verschlüsselte
        // Supabase-Persistenz (profile_text_blocks) ist die Deploy-Schicht.
        let blk: { quote?: string; label?: string; theme?: string } = {};
        try { blk = JSON.parse(value); } catch { /* ignore */ }
        const ta = el.closest(".cl-item")?.querySelector<HTMLTextAreaElement>("textarea.cl-edit");
        const text = (ta?.value.trim()) || blk.quote || blk.label || "";
        if (text) {
          navigator.clipboard?.writeText(text).catch(() => {});
          try {
            const key = "govisor.blocks";
            const lib = JSON.parse(localStorage.getItem(key) || "[]");
            lib.push({ theme: blk.theme || "sonstiges", content: text, label: blk.label || "",
              lead_id: activeId, saved_at: new Date().toISOString() });
            localStorage.setItem(key, JSON.stringify(lib));
          } catch { /* Speicher voll/blockiert → nur kopieren */ }
        }
        const btn = el as HTMLButtonElement;
        const orig = btn.textContent;
        btn.classList.add("ok"); btn.textContent = "Gespeichert ✓";
        setTimeout(() => { btn.classList.remove("ok"); btn.textContent = orig; }, 1500);
        break;
      }
      // ── Ticket #23 Checkliste (§7): Abhaken, Kombi-Button, Kopieren, TOC ──────────────────
      case "clchk": {
        const it = el.closest<HTMLElement>(".item");
        if (it) { it.classList.toggle("done"); clPersist(el.closest<HTMLElement>(".va-checklist")); }
        break;
      }
      case "clkombi": {
        let blk: { theme?: string; label?: string; quote?: string } = {};
        try { blk = JSON.parse(value); } catch { /* ignore */ }
        const it = el.closest<HTMLElement>(".item");
        const ta = it?.querySelector<HTMLTextAreaElement>("textarea.ta");
        const text = (ta?.value.trim()) || blk.quote || blk.label || "";
        if (text) {
          navigator.clipboard?.writeText(text).catch(() => {});
          try {
            const lib = JSON.parse(localStorage.getItem("govisor.blocks") || "[]");
            lib.push({ theme: blk.theme || "sonstiges", content: text, label: blk.label || "",
              lead_id: activeId, saved_at: new Date().toISOString() });
            localStorage.setItem("govisor.blocks", JSON.stringify(lib));
          } catch { /* voll/blockiert */ }
        }
        if (it) { it.classList.add("done"); clPersist(el.closest<HTMLElement>(".va-checklist")); }
        break;
      }
      case "clcopy": {
        const it = el.closest<HTMLElement>(".item");
        const ta = it?.querySelector<HTMLTextAreaElement>("textarea.ta");
        const q = it?.querySelector<HTMLElement>(".quote q");
        const text = (ta?.value.trim()) || q?.textContent || "";
        if (text) navigator.clipboard?.writeText(text).catch(() => {});
        const b = el as HTMLButtonElement; const o = b.textContent;
        b.textContent = "Kopiert"; setTimeout(() => { b.textContent = o; }, 1200);
        break;
      }
      case "cljump": {
        const g = document.getElementById(value);
        if (g) { g.setAttribute("open", ""); g.scrollIntoView({ behavior: "smooth", block: "start" }); }
        break;
      }
      case "clcollapse": {
        const root = el.closest<HTMLElement>(".va-checklist");
        if (root) {
          const anyOpen = root.querySelector("details.grp[open]");
          root.querySelectorAll<HTMLDetailsElement>("details.grp").forEach((g) => {
            if (anyOpen) g.removeAttribute("open"); else g.setAttribute("open", "");
          });
          (el as HTMLElement).textContent = anyOpen ? "Alle aufklappen" : "Alle zuklappen";
        }
        break;
      }
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
          logEvent(l, "analyze", "Notiz für das Team ergänzt");
          bump();
        }
        break;
      }
      case "uploaddocs": {
        // Vergabeunterlagen hochladen → Pipeline (index→signals→LLM) → Felder in den Lead mergen.
        const statusEl = el.closest(".detail")?.querySelector<HTMLElement>(`[data-upstatus="${value}"]`) || null;
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".zip,.pdf,.doc,.docx,.xls,.xlsx,.txt,.html";
        input.onchange = async () => {
          const file = input.files?.[0];
          if (!file) return;
          if (statusEl) statusEl.textContent = "Lade hoch und analysiere … (kann bis ~30 s dauern)";
          const fd = new FormData();
          fd.append("file", file);
          const lb = (CORE.find((x) => x.id === value) as (Lead & { buyer?: string }) | undefined)?.buyer || "";
          try {
            const r = await fetch(`/api/lead-docs?id=${encodeURIComponent(value)}&buyer=${encodeURIComponent(lb)}`,
              { method: "POST", body: fd });
            const d = await r.json();
            if (!r.ok || d.error) { if (statusEl) statusEl.textContent = "Fehler: " + (d.error || r.status); return; }
            const l = CORE.find((x) => x.id === value) as (Lead & { log?: unknown[] }) | undefined;
            if (l) { Object.assign(l, d); logEvent(l, "analyze", "Vergabeunterlagen hochgeladen & analysiert"); }
            // §5-4: Käufer nicht in den Unterlagen gefunden → Rückfrage (Analyse trotzdem gezeigt).
            const mm = (d as { leadMismatch?: { expected_buyer?: string } }).leadMismatch;
            if (statusEl) statusEl.innerHTML = mm
              ? `<span style="color:#b91c1c">⚠ Diese Unterlagen erwähnen den Auftraggeber „${(mm.expected_buyer || "").replace(/[<>&]/g, "")}" nicht — gehören sie wirklich zu diesem Lead? Die Analyse ist unten trotzdem angezeigt.</span>`
              : "";
            bump();
          } catch {
            if (statusEl) statusEl.textContent = "Upload fehlgeschlagen.";
          }
        };
        input.click();
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
      // coord/radius mitnehmen — trägt die echte PLZ-Umkreissuche (sonst Token ohne Geo).
      setTokens((ts) => [...ts, { type: tok!.type, value: tok!.value, label: tok!.label,
        ...(tok!.coord ? { coord: tok!.coord } : {}), ...(tok!.radius ? { radius: tok!.radius } : {}) }]);
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
    } else {
      // Strategie ist keine Linse auf die Liste — die Linsen dürfen nicht mitwandern.
      setFilters((f) => ({ ...f, netz: false, gemerkt: false }));
      if (netzCol) netzCol.on = false;
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

  function setBranche(k: string) { brancheManual.current = true; setAktiveBranche(k); setActiveId(null); }
  function resetBranche() { setAktiveBranche(profilBranche); setActiveId(null); }

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
  const merkN = CORE.filter((l) => l.merk).length;

  return (
    <div className="app" data-view={view === "netzwerk" ? "angriff" : "angriff"}>
      <header className="topbar">
        <div className="brandcell">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/govisor-wordmark.png" alt="goVisor" className="brandlogo" />
        </div>
        <div className="maincol">
          <div className="toolbar">
            <div className="colcfg">
              <button className={`colbtn ${realProfile ? "colbtn-on" : ""}`} type="button"
                onClick={() => router.push("/onboarding")}
                title={realProfile ? `${realProfile.firma || "Profil"} — ansehen/bearbeiten` : "Profil einrichten — schaltet echte Relevanz frei"}>
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 12a4 4 0 100-8 4 4 0 000 8ZM4 21a8 8 0 0116 0" />
                </svg>
                {/* Kein Zeichen-Limit: Namen sind median 24 Zeichen, aber der längste im
                    Bestand hat 400 (eine ARGE-Auflistung). Die Breite begrenzt der Platz
                    (CSS max-width + Ellipse), der volle Name steht im title. */}
                <span className="pb-name">{realProfile ? (realProfile.firma || "Profil") : "Profil einrichten"}</span>
              </button>
            </div>
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
            <div className="tstatus">
              <span className="tcount">
                {/* Nenner auf DERSELBEN Grundmenge wie die Anzeige — in der
                    Zuschlags-Sicht sind das die Zuschläge, sonst die offenen. */}
                <b>{rows.length}</b> von <span>{zuschlagsSicht ? alleRows.length : alleRows.filter((l) => l.src !== "award").length}</span>
              </span>
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
      </header>

      <div className="body">
        <AppRail
          current={aktiverRailPunkt}
          merkN={merkN}
          onSwitch={(id) => switchView(RAIL_VIEW[id])}
          plan={plan}
          userEmail={userEmail}
          onLogout={abmelden}
        />

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
              {(() => {
                // #24 Alert-Band (§4): frische Zuschläge (≤3 Tage) im aktuellen Feld — der eigentliche
                // Auslöser. Gebündelt, nicht je Einzelzuschlag; ausblendbar.
                if (awAlertOff) return null;
                type Aw = { ago?: number; winner?: string };
                const awOf = (l: Lead) => (l as { award?: Aw }).award;
                // WICHTIG: aus `alleRows` (inkl. Zuschläge), nicht aus `rows` — dort sind die
                // Zuschläge bewusst herausgefiltert, das Band würde sich sonst selbst abschalten.
                // „in eurem Feld" war gelogen: gezählt wurde der ganze Grundraum. Mit Profil
                // zählen wir nur, was auch zu euch passt — sonst meldet die App einem
                // Tiefbauer aus Sachsen-Anhalt Zuschläge aus ganz Deutschland.
                const fresh = alleRows.filter((l) =>
                  l.src === "award" && (awOf(l)?.ago ?? 99) <= 3
                  && (!realProfile || l.relevanz === "hoch" || l.relevanz === "mittel"));
                if (!fresh.length) return null;
                const winners = [...new Set(fresh.map((l) => awOf(l)?.winner).filter(Boolean))].slice(0, 2);
                return (
                  <div className="aw-alert">
                    <svg viewBox="0 0 24 24"><path d="M18 8a6 6 0 10-12 0c0 7-3 8-3 8h18s-3-1-3-8" /><path d="M13.7 21a2 2 0 01-3.4 0" /></svg>
                    <div><b>{fresh.length} {fresh.length === 1 ? "neuer Zuschlag" : "neue Zuschläge"} {realProfile ? "in eurem Feld" : "im Grundraum"}</b>
                      {winners.length ? ` — ${winners.join(" und ")}. ` : " — "}Wer gerade gewonnen hat, kauft jetzt ein.</div>
                    {/* Zuschläge sind nicht mehr bewerbbar und stehen deshalb nicht in der Akquise-Liste.
                        Hier — wo sie angekündigt werden — führt ein Klick direkt zu ihnen. */}
                    <button className="aw-alert-go" onClick={() => setAdv((a) => ({ ...a, phases: ["award"] }))}>
                      Zuschläge ansehen
                    </button>
                    <button className="aw-alert-x" onClick={() => setAwAlertOff(true)} aria-label="Ausblenden">✕</button>
                  </div>
                );
              })()}
              {/* Vorauswahl sichtbar machen: WAS wir weggelassen haben und wie man es zurückholt.
                  Ein stilles Filtern wäre der schlimmere Fehler — der Nutzer muss die Menge kennen. */}
              {realProfile && istAkquise && !adv.phases.includes("award") ? (
                <div className={`vor-band ${vorauswahl ? "" : "off"}`}>
                  {vorauswahl ? (
                    <>
                      <b>{rows.length}</b> von {alleRows.filter((l) => l.src !== "award").length.toLocaleString("de-DE")} für euch vorsortiert <span className="vor-gr">({(BRANCHEN as Record<string, string>)[aktiveBranche]})</span>
                      <span className="vor-x">
                        offene Ausschreibung · noch ≥ 3 Tage · hohe Passung · Aufwand vertretbar
                        {/* Der Regionsteil ist aus der eigenen Zuschlagshistorie abgeleitet — sagen,
                            woher er kommt, sonst wirkt die Einschränkung willkürlich. */}
                        {(() => {
                          const p = realProfile as unknown as { regionTyp?: string | null; regionLabels?: string[]; regions?: string[] } | null;
                          if (!p?.regions?.length) return null;
                          const wo = (p.regionLabels?.length ? p.regionLabels : p.regions).slice(0, 3).join(", ");
                          return ` · ${p.regionTyp === "regional" ? "eure Region" : "eure Regionen"} ${wo} (aus euren Zuschlägen abgeleitet)`;
                        })()}
                      </span>
                      <button className="vor-btn" onClick={() => setVorauswahl(false)}>Alle anzeigen</button>
                      {/* Sehr scharfe Profile (enges Gewerk × eine Region) landen zweistellig darunter.
                          Das ist die ehrliche Zahl — aber unkommentiert sieht sie nach einem Defekt aus. */}
                      {rows.length < 10 ? (
                        <span className="vor-eng">
                          Wenige Treffer — so eng ist der Markt für euer Gewerk in eurer Region gerade.
                        </span>
                      ) : null}
                    </>
                  ) : (
                    <>
                      Alle <b>{rows.length.toLocaleString("de-DE")}</b> Ausschreibungen in {(BRANCHEN as Record<string, string>)[aktiveBranche]}
                      <span className="vor-x">ungefiltert — auch Ankündigungen und weniger passende</span>
                      <button className="vor-btn" onClick={() => setVorauswahl(true)}>Wieder vorsortieren</button>
                    </>
                  )}
                </div>
              ) : null}
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
              rows={rows}
              alle={alleRows}
              onGoto={(ziel) => {
                // Ein Klick im Überblick soll die Ansicht wirklich wechseln, nicht nur
                // etwas einfärben — deshalb dieselben Wege wie über die Rail.
                if (ziel === "netzwerk") return switchView("netzwerk");
                if (ziel === "strategie") return switchView("potenzial");
                if (ziel === "award") return setAdv((a) => ({ ...a, phases: ["award"] }));
                if (ziel === "vorschau") return setAdv((a) => ({ ...a, phases: ["f01", "auslauf"] }));
              }}
              onPickLead={openLead}
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
        branche={aktiveBranche}
        profilBranche={profilBranche}
        brancheCounts={branchenCounts}
        onSetBranche={setBranche}
        onResetBranche={resetBranche}
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
