"use client";

import { useState } from "react";
import { UnternehmenView, type UnTab } from "@/components/unternehmen/UnternehmenView";
import { UnternehmenTabs } from "@/components/unternehmen/UnternehmenTabs";
import { AppRail, AppTop } from "@/components/explorer/Rail";
import "../explorer.css";
import "./unternehmen.css";

// #27 Eignungsprofil — im gleichen Gerüst wie die Lead-Ansichten (Hauptnavigation links),
// nicht als Seite ohne Rückweg.
export default function UnternehmenPage() {
  const [tab, setTab] = useState<UnTab>("profil");
  return (
    <div className="app">
      <AppTop werkzeuge={<UnternehmenTabs tab={tab} onTab={setTab} />} />
      <div className="body">
        <AppRail current="unternehmen" />
        <div className="main seitenmain">
          <UnternehmenView tab={tab} onTab={setTab} />
        </div>
      </div>
    </div>
  );
}
