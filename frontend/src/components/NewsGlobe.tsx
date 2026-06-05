// The 3D world-news globe (react-globe.gl / three.js). News is aggregated to one glowing pin per
// source country (arc cyan; gold where many stories cluster). Auto-rotates on the board, STOPPED
// under prefers-reduced-motion. The earth texture is a LOCAL asset (public/earth-dark.jpg) - no CDN,
// honoring the project's trust boundary. A country we don't know simply doesn't pin (never mis-pins).
import { useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import Globe, { type GlobeMethods } from "react-globe.gl";
import type { NewsItem } from "../types";
import { lookup } from "./countryCentroids";

const ARC = "#4fd8e8";
const GOLD = "#e6b347";

export interface GlobePoint {
  country: string;
  lat: number;
  lng: number;
  count: number;
  headline: string;
  url: string | null;
}

export default function NewsGlobe({
  items,
  onSelect,
}: {
  items: NewsItem[];
  onSelect?: (point: GlobePoint) => void;
}) {
  const reduce = useReducedMotion();
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 600, h: 520 });

  // globe.gl needs explicit pixel w/h — track the wrapper.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const r = entries[0].contentRect;
      setSize({ w: Math.max(1, Math.floor(r.width)), h: Math.max(1, Math.floor(r.height)) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Auto-rotate (off under reduced motion); never zoom (it's an ambient instrument, not a map tool).
  useEffect(() => {
    const g = globeRef.current;
    if (!g) return;
    const controls = g.controls();
    controls.autoRotate = !reduce;
    controls.autoRotateSpeed = 0.6;
    controls.enableZoom = false;
  }, [reduce, size]);

  const points = useMemo<GlobePoint[]>(() => {
    const byCountry = new Map<string, GlobePoint>();
    for (const it of items) {
      const centroid = lookup(it.country);
      if (!centroid || !it.country) continue; // unknown / no country -> no pin (still lists)
      const existing = byCountry.get(it.country);
      if (existing) existing.count += 1;
      else
        byCountry.set(it.country, {
          country: it.country,
          lat: centroid[0],
          lng: centroid[1],
          count: 1,
          headline: it.title,
          url: it.url,
        });
    }
    return [...byCountry.values()];
  }, [items]);

  return (
    <div ref={wrapRef} style={{ position: "relative", width: "100%", height: "100%", minHeight: 420 }}>
      <Globe
        ref={globeRef}
        width={size.w}
        height={size.h}
        backgroundColor="rgba(0,0,0,0)"
        globeImageUrl="/earth-dark.jpg"
        showAtmosphere
        atmosphereColor={ARC}
        atmosphereAltitude={0.18}
        pointsData={points}
        pointLat={(d: object) => (d as GlobePoint).lat}
        pointLng={(d: object) => (d as GlobePoint).lng}
        pointColor={(d: object) => ((d as GlobePoint).count >= 4 ? GOLD : ARC)}
        pointAltitude={(d: object) => 0.04 + Math.min((d as GlobePoint).count, 8) * 0.015}
        pointRadius={(d: object) => 0.25 + Math.min((d as GlobePoint).count, 8) * 0.05}
        pointLabel={(d: object) => `${(d as GlobePoint).country} — ${(d as GlobePoint).headline}`}
        onPointClick={(d: object) => onSelect?.(d as GlobePoint)}
      />
    </div>
  );
}
