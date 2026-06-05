import React from "react";
import ReactDOM from "react-dom/client";

// Self-hosted fonts (no CDN call - honors the local-first trust boundary).
// IBM Plex — the engineering/diagram typeface: Sans for UI + reading, Mono for technical labels.
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-mono/600.css";

import App from "./App";
import "./index.css";
import "./theme.css";

// Pick up an API token from ?token=… once (for off-localhost / Tailscale binds), persist it, and
// strip it from the URL so it isn't left in history. The client then sends it on every /api call.
const url = new URL(window.location.href);
const token = url.searchParams.get("token");
if (token) {
  localStorage.setItem("jarvis_token", token);
  url.searchParams.delete("token");
  window.history.replaceState({}, "", url.pathname + url.search + url.hash);
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
