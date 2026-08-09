"use client";

import { UnternehmenView } from "@/components/unternehmen/UnternehmenView";
import { AppRail, AppTop } from "@/components/explorer/Rail";
import "../explorer.css";
import "./unternehmen.css";

// #27 Eignungsprofil — im gleichen Gerüst wie die Lead-Ansichten (Hauptnavigation links),
// nicht als Seite ohne Rückweg.
export default function UnternehmenPage() {
  return (
    <div className="app">
      <AppTop titel="Unser Unternehmen" />
      <div className="body">
        <AppRail current="unternehmen" />
        <div className="main seitenmain">
          <UnternehmenView />
        </div>
      </div>
    </div>
  );
}
