"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { LayersIcon } from "./Icons";
import { t } from "@/lib/i18n";

interface RouteMapProps {
  geojson: GeoJSON.FeatureCollection;
  center?: [number, number];
  showLayers?: boolean;
}

const TILE_URL =
  process.env.NEXT_PUBLIC_MAP_TILE_URL ||
  "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";
const TILE_ATTR =
  process.env.NEXT_PUBLIC_MAP_TILE_ATTR ||
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';
const TILE_SUBDOMAINS =
  process.env.NEXT_PUBLIC_MAP_TILE_SUBDOMAINS || "abcd";

const LAYER_STYLES: Record<string, L.PathOptions> = {
  route: { color: "#4f46e5", weight: 5, opacity: 0.95 },
  target_artwork: { color: "#ef4444", weight: 2, opacity: 0.5, dashArray: "6 6" },
  keypoints: { color: "#10b981", weight: 0, fillColor: "#10b981", fillOpacity: 1 },
  boundary: { color: "#6366f1", weight: 2, opacity: 0.4, dashArray: "4 4", fillOpacity: 0.05 },
};

export default function RouteMap({ geojson, center, showLayers = true }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.GeoJSON | null>(null);
  const [visible, setVisible] = useState<Set<string>>(
    new Set(["route", "target_artwork", "keypoints", "boundary"]),
  );
  const [showPanel, setShowPanel] = useState(false);

  const kinds = new Set<string>();
  geojson.features.forEach((f) => {
    const k = f.properties?.kind as string;
    if (k) kinds.add(k);
  });

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }
    container.removeAttribute("class");
    container.classList.add("h-full", "w-full", "min-h-[300px]");
    delete (container as unknown as Record<string, unknown>)._leaflet_id;

    const initialCenter: [number, number] = center ?? [47.4979, 19.0402];
    const map = L.map(container, {
      center: initialCenter,
      zoom: 13,
      scrollWheelZoom: true,
    });
    mapRef.current = map;

    L.tileLayer(TILE_URL, {
      attribution: TILE_ATTR,
      subdomains: TILE_SUBDOMAINS,
    }).addTo(map);

    function styleFor(feature: GeoJSON.Feature): L.PathOptions {
      const kind = feature.properties?.kind as string | undefined;
      if (kind && !visible.has(kind)) return { opacity: 0, fillOpacity: 0 };
      return LAYER_STYLES[kind || ""] || { color: "#334155", weight: 3 };
    }

    const layer = L.geoJSON(geojson, {
      style: (feat) => (feat ? styleFor(feat) : LAYER_STYLES.route),
      pointToLayer: (_feat, latlng) =>
        L.circleMarker(latlng, {
          radius: 4,
          color: "#10b981",
          fillColor: "#10b981",
          fillOpacity: visible.has("keypoints") ? 1 : 0,
          opacity: visible.has("keypoints") ? 1 : 0,
        }),
    });
    layer.addTo(map);
    layerRef.current = layer;

    const bounds = layer.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40] });
    }

    setTimeout(() => map.invalidateSize(), 200);

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, [center, geojson]);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.setStyle((feat) => {
      const kind = feat?.properties?.kind as string | undefined;
      if (kind && !visible.has(kind)) return { opacity: 0, fillOpacity: 0 } as L.PathOptions;
      return LAYER_STYLES[kind || ""] || { color: "#334155", weight: 3 };
    });
  }, [visible]);

  const toggle = (kind: string) => {
    setVisible((prev) => {
      const next = new Set(prev);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });
  };

  const LAYER_LABELS: Record<string, { label: string; color: string }> = {
    route: { label: t("map.route"), color: "#4f46e5" },
    target_artwork: { label: t("map.target"), color: "#ef4444" },
    keypoints: { label: t("map.keypoints"), color: "#10b981" },
    boundary: { label: t("map.boundary"), color: "#6366f1" },
  };

  return (
    <div className="relative h-full w-full min-h-[300px]">
      <div ref={containerRef} className="h-full w-full min-h-[300px]" />

      {showLayers && kinds.size > 0 && (
        <div className="absolute right-3 top-3 z-[1000]">
          <button
            className="glass flex h-9 w-9 items-center justify-center rounded-lg text-slate-700 hover:text-brand-600 transition-colors"
            onClick={() => setShowPanel((s) => !s)}
            title={t("map.layers")}
          >
            <LayersIcon size={18} />
          </button>
          {showPanel && (
            <div className="glass mt-2 w-48 rounded-xl p-3 animate-slide-up">
              <div className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">
                {t("map.layers")}
              </div>
              {Array.from(kinds).map((kind) => {
                const info = LAYER_LABELS[kind] || { label: kind, color: "#334155" };
                const isVisible = visible.has(kind);
                return (
                  <button
                    key={kind}
                    className="flex w-full items-center gap-2.5 py-1.5 text-sm text-left hover:bg-white/50 rounded-lg px-1.5 transition-colors"
                    onClick={() => toggle(kind)}
                  >
                    <span
                      className="h-4 w-4 rounded border-2 transition-all"
                      style={{
                        borderColor: info.color,
                        backgroundColor: isVisible ? info.color : "transparent",
                      }}
                    />
                    <span className={isVisible ? "text-slate-900 font-medium" : "text-slate-400"}>
                      {info.label}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
