"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { LayersIcon, EditIcon, TrashIcon } from "./Icons";
import { t } from "@/lib/i18n";
import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";

import { Activity } from "@/lib/types";
import { api } from "@/lib/api";

interface RouteMapProps {
  geojson: GeoJSON.FeatureCollection;
  center?: [number, number];
  showLayers?: boolean;
  editable?: boolean;
  onGeoJsonChange?: (geojson: GeoJSON.FeatureCollection) => void;
  cityId?: string;
  activity?: Activity;
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

const WARNING_STYLES: Record<string, { color: string; label: string }> = {
  crosses_water: { color: "#0ea5e9", label: "map.warn.crossesWater" },
  crosses_building: { color: "#f59e0b", label: "map.warn.crossesBuilding" },
  route_disconnected: { color: "#ef4444", label: "map.warn.routeDisconnected" },
  high_detour_ratio: { color: "#f97316", label: "map.warn.highDetourRatio" },
};

type SnapStatus = "idle" | "snapping" | "snapped" | "failed";

const SNAP_DEBOUNCE_MS = 500;

export default function RouteMap({ geojson, center, showLayers = true, editable = false, onGeoJsonChange, cityId, activity }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.GeoJSON | null>(null);
  const pastRef = useRef<string[]>([]);
  const futureRef = useRef<string[]>([]);
  const currentRef = useRef<string>("");
  const originalRef = useRef<string>("");
  const autoSnapRef = useRef(true);
  const isSnappingRef = useRef(false);
  const snapTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const undoRef = useRef<() => void>(() => {});
  const redoRef = useRef<() => void>(() => {});
  const resetRef = useRef<() => void>(() => {});
  const snapNowRef = useRef<() => void>(() => {});

  const [visible, setVisible] = useState<Set<string>>(
    new Set(["route", "target_artwork", "keypoints", "boundary"]),
  );
  const [showPanel, setShowPanel] = useState(false);
  const [snapStatus, setSnapStatus] = useState<SnapStatus>("idle");
  const [snapWarnings, setSnapWarnings] = useState<string[]>([]);
  const [autoSnap, setAutoSnap] = useState(true);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [isRemovalMode, setIsRemovalMode] = useState(false);
  const [isDragMode, setIsDragMode] = useState(false);
  const [isCutMode, setIsCutMode] = useState(false);

  useEffect(() => {
    autoSnapRef.current = autoSnap;
  }, [autoSnap]);

  const updateHistoryState = useCallback(() => {
    setCanUndo(pastRef.current.length > 0);
    setCanRedo(futureRef.current.length > 0);
  }, []);

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

    const initialStr = JSON.stringify(geojson);
    originalRef.current = initialStr;
    currentRef.current = initialStr;
    pastRef.current = [];
    futureRef.current = [];

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
      onEachFeature: (feature, l: any) => {
        if (feature.properties?.kind !== "route") {
          l.options.pmIgnore = true;
          L.setOptions(l, { pmIgnore: true });
        }
      }
    });
    layer.addTo(map);
    layerRef.current = layer;

    const attachPmListeners = (layerGroup: any) => {
      layerGroup.eachLayer((l: any) => {
        if (!l.options.pmIgnore) {
          l.off('pm:edit', triggerChange);
          l.off('pm:dragend', triggerChange);
          l.off('pm:vertexadded', triggerChange);
          l.off('pm:vertexremoved', triggerChange);
          l.off('pm:markerdragend', triggerChange);

          l.on('pm:edit', triggerChange);
          l.on('pm:dragend', triggerChange);
          l.on('pm:vertexadded', triggerChange);
          l.on('pm:vertexremoved', triggerChange);
          l.on('pm:markerdragend', triggerChange);
        }
      });
    };

    const restoreState = (stateStr: string) => {
      if (!layerRef.current) return;
      const state = JSON.parse(stateStr) as GeoJSON.FeatureCollection;
      isSnappingRef.current = true;
      layerRef.current.clearLayers();
      layerRef.current.addData(state);
      attachPmListeners(layerRef.current);
      
      if (mapRef.current?.pm.globalEditModeEnabled()) {
        layerRef.current.eachLayer((l: any) => {
          if (!l.options.pmIgnore && l.pm) l.pm.enable();
        });
      }

      currentRef.current = stateStr;
      isSnappingRef.current = false;
      if (onGeoJsonChange) onGeoJsonChange(state);
      updateHistoryState();
    };

    const doSnap = async () => {
      if (isSnappingRef.current) return;
      if (!layerRef.current || !cityId || !activity) return;

      const geojsonStr = currentRef.current;
      const gj = JSON.parse(geojsonStr) as GeoJSON.FeatureCollection;
      const route = gj.features.find(f => f.properties?.kind === "route") as GeoJSON.Feature<GeoJSON.LineString> | undefined;
      if (!route || route.geometry?.type !== "LineString" || route.geometry.coordinates.length < 2) {
        return;
      }

      isSnappingRef.current = true;
      setSnapStatus("snapping");

      try {
        const res = await api.snapEdit({
          city_id: cityId,
          activity,
          lonlat: route.geometry.coordinates,
        });

        route.geometry.coordinates = res.lonlat;
        setSnapWarnings(res.warnings);
        setSnapStatus(res.snapped ? "snapped" : "failed");

        if (res.snapped) {
          const snappedStr = JSON.stringify(gj);
          isSnappingRef.current = true;
          layerRef.current.clearLayers();
          layerRef.current.addData(gj);
          attachPmListeners(layerRef.current);

          if (mapRef.current?.pm.globalEditModeEnabled()) {
            layerRef.current.eachLayer((l: any) => {
              if (!l.options.pmIgnore && l.pm) l.pm.enable();
            });
          }

          currentRef.current = snappedStr;
          isSnappingRef.current = false;
        }

        if (onGeoJsonChange) onGeoJsonChange(gj);
      } catch (e) {
        console.error("Snap failed", e);
        setSnapStatus("failed");
      } finally {
        isSnappingRef.current = false;
      }
    };

    const triggerChange = () => {
      if (isSnappingRef.current) return;
      if (!layerRef.current) return;

      let currentGeoJson = layerRef.current.toGeoJSON() as GeoJSON.FeatureCollection;
      const newStr = JSON.stringify(currentGeoJson);

      if (newStr === currentRef.current) return;

      pastRef.current.push(currentRef.current);
      futureRef.current = [];
      currentRef.current = newStr;
      updateHistoryState();

      if (autoSnapRef.current && cityId && activity) {
        if (snapTimerRef.current) clearTimeout(snapTimerRef.current);
        snapTimerRef.current = setTimeout(() => doSnap(), SNAP_DEBOUNCE_MS);
      }

      if (onGeoJsonChange) onGeoJsonChange(currentGeoJson);
    };

    const undo = () => {
      if (isSnappingRef.current) return;
      if (snapTimerRef.current) clearTimeout(snapTimerRef.current);
      if (pastRef.current.length === 0) return;
      futureRef.current.push(currentRef.current);
      const prev = pastRef.current.pop()!;
      restoreState(prev);
    };

    const redo = () => {
      if (isSnappingRef.current) return;
      if (snapTimerRef.current) clearTimeout(snapTimerRef.current);
      if (futureRef.current.length === 0) return;
      pastRef.current.push(currentRef.current);
      const next = futureRef.current.pop()!;
      restoreState(next);
    };

    const reset = () => {
      if (isSnappingRef.current) return;
      if (snapTimerRef.current) clearTimeout(snapTimerRef.current);
      if (currentRef.current === originalRef.current) return;
      pastRef.current.push(currentRef.current);
      futureRef.current = [];
      restoreState(originalRef.current);
      setSnapWarnings([]);
      setSnapStatus("idle");
    };

    const snapNow = () => {
      if (isSnappingRef.current) return;
      if (snapTimerRef.current) clearTimeout(snapTimerRef.current);
      doSnap();
    };

    undoRef.current = undo;
    redoRef.current = redo;
    resetRef.current = reset;
    snapNowRef.current = snapNow;

    if (editable) {
      map.pm.addControls({
        position: 'topleft',
        drawMarker: false,
        drawCircleMarker: false,
        drawPolyline: false,
        drawRectangle: false,
        drawPolygon: false,
        drawCircle: false,
        drawText: false,
        editMode: false,
        dragMode: false,
        cutPolygon: false,
        removalMode: false,
        rotateMode: false,
      });

      map.on('pm:globaleditmodetoggled', (e: any) => setIsEditMode(e.enabled));
      map.on('pm:globalremovalmodetoggled', (e: any) => setIsRemovalMode(e.enabled));
      map.on('pm:globaldragmodetoggled', (e: any) => setIsDragMode(e.enabled));
      map.on('pm:globalcutmodetoggled', (e: any) => setIsCutMode(e.enabled));
      map.on('pm:remove', triggerChange);
      attachPmListeners(layer);
    }

    const bounds = layer.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40] });
    }

    setTimeout(() => map.invalidateSize(), 200);

    return () => {
      if (snapTimerRef.current) clearTimeout(snapTimerRef.current);
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, [center]);

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

      {/* Editing toolbar */}
      {editable && (
        <div className="absolute left-4 top-20 z-[1000] flex flex-col gap-3">
          <div className="glass flex flex-col rounded-2xl p-1 gap-1 shadow-[0_8px_30px_rgb(0,0,0,0.12)]">
            <button
              className={`flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200 hover:scale-105 active:scale-95 ${isEditMode ? "bg-brand-500 text-white shadow-md shadow-brand-500/30" : "text-slate-700 hover:bg-slate-100 hover:text-brand-600"}`}
              onClick={() => {
                if (mapRef.current) {
                  if (isRemovalMode) mapRef.current.pm.disableGlobalRemovalMode();
                  if (isDragMode) mapRef.current.pm.disableGlobalDragMode();
                  if (isCutMode) mapRef.current.pm.disableGlobalCutMode();
                  mapRef.current.pm.toggleGlobalEditMode();
                }
              }}
              title={t("map.edit.mode")}
            >
              <EditIcon size={20} />
            </button>
            <button
              className={`flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200 hover:scale-105 active:scale-95 ${isRemovalMode ? "bg-rose-500 text-white shadow-md shadow-rose-500/30" : "text-slate-700 hover:bg-rose-50 hover:text-rose-600"}`}
              onClick={() => {
                if (mapRef.current) {
                  if (isEditMode) mapRef.current.pm.disableGlobalEditMode();
                  if (isDragMode) mapRef.current.pm.disableGlobalDragMode();
                  if (isCutMode) mapRef.current.pm.disableGlobalCutMode();
                  mapRef.current.pm.toggleGlobalRemovalMode();
                }
              }}
              title={t("map.edit.remove")}
            >
              <TrashIcon size={20} />
            </button>
            <button
              className={`flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200 hover:scale-105 active:scale-95 ${isDragMode ? "bg-amber-500 text-white shadow-md shadow-amber-500/30" : "text-slate-700 hover:bg-amber-50 hover:text-amber-600"}`}
              onClick={() => {
                if (mapRef.current) {
                  if (isEditMode) mapRef.current.pm.disableGlobalEditMode();
                  if (isRemovalMode) mapRef.current.pm.disableGlobalRemovalMode();
                  if (isCutMode) mapRef.current.pm.disableGlobalCutMode();
                  mapRef.current.pm.toggleGlobalDragMode();
                }
              }}
              title={t("map.edit.drag")}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="5 9 2 12 5 15"/><polyline points="9 5 12 2 15 5"/><polyline points="19 9 22 12 19 15"/><polyline points="9 19 12 22 15 19"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="12" y1="2" x2="12" y2="22"/></svg>
            </button>
            <button
              className={`flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200 hover:scale-105 active:scale-95 ${isCutMode ? "bg-purple-500 text-white shadow-md shadow-purple-500/30" : "text-slate-700 hover:bg-purple-50 hover:text-purple-600"}`}
              onClick={() => {
                if (mapRef.current) {
                  if (isEditMode) mapRef.current.pm.disableGlobalEditMode();
                  if (isRemovalMode) mapRef.current.pm.disableGlobalRemovalMode();
                  if (isDragMode) mapRef.current.pm.disableGlobalDragMode();
                  mapRef.current.pm.toggleGlobalCutMode();
                }
              }}
              title={t("map.edit.cut")}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.12" y2="15.88"/><line x1="14.47" y1="14.48" x2="20" y2="20"/><line x1="8.12" y1="8.12" x2="12" y2="12"/></svg>
            </button>
          </div>

          <div className="glass flex flex-col rounded-2xl p-1 gap-1 shadow-[0_8px_30px_rgb(0,0,0,0.12)]">
            <button
              className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-700 hover:bg-slate-100 hover:text-brand-600 transition-all duration-200 hover:scale-105 active:scale-95 disabled:opacity-30 disabled:hover:scale-100 disabled:cursor-not-allowed"
              onClick={() => undoRef.current()}
              disabled={!canUndo}
              title={t("map.edit.undo")}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-15-6.7L3 13"/></svg>
            </button>
            <button
              className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-700 hover:bg-slate-100 hover:text-brand-600 transition-all duration-200 hover:scale-105 active:scale-95 disabled:opacity-30 disabled:hover:scale-100 disabled:cursor-not-allowed"
              onClick={() => redoRef.current()}
              disabled={!canRedo}
              title={t("map.edit.redo")}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 15-6.7L21 13"/></svg>
            </button>
            <button
              className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-700 hover:bg-slate-100 hover:text-brand-600 transition-all duration-200 hover:scale-105 active:scale-95 disabled:opacity-30 disabled:hover:scale-100 disabled:cursor-not-allowed"
              onClick={() => resetRef.current()}
              disabled={currentRef.current === originalRef.current}
              title={t("map.edit.reset")}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
            </button>
            <button
              className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-700 hover:bg-slate-100 hover:text-brand-600 transition-all duration-200 hover:scale-105 active:scale-95"
              onClick={() => snapNowRef.current()}
              title={t("map.edit.snapNow")}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            </button>
          </div>
          <button
            className={`glass flex h-10 items-center justify-center gap-2 rounded-2xl px-3 text-xs font-bold transition-all duration-300 hover:scale-105 active:scale-95 shadow-[0_8px_30px_rgb(0,0,0,0.12)] ${autoSnap ? "text-brand-600 bg-brand-50/80 border-brand-200" : "text-slate-500 hover:text-slate-700"}`}
            onClick={() => setAutoSnap(s => !s)}
            title={t("map.edit.autoSnap")}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            {t("map.edit.autoSnap")}
          </button>
        </div>
      )}

      {/* Snap status + warnings */}
      {editable && (
        <div className="absolute left-3 bottom-3 z-[1000] max-w-xs">
          {snapStatus === "snapping" && (
            <div className="glass flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-brand-600 animate-pulse">
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
              {t("map.edit.snapping")}
            </div>
          )}
          {snapStatus === "snapped" && snapWarnings.length === 0 && (
            <div className="glass flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium text-emerald-600">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
              {t("map.edit.snapped")}
            </div>
          )}
          {snapWarnings.length > 0 && (
            <div className="glass rounded-lg p-3 shadow-md">
              <div className="mb-1.5 flex items-center gap-1.5 text-xs font-bold text-amber-700">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                {t("map.warnings")}
              </div>
              {snapWarnings.map((w) => {
                const info = WARNING_STYLES[w];
                const label = info ? t(info.label) : w;
                const color = info?.color || "#f59e0b";
                return (
                  <div key={w} className="flex items-center gap-1.5 py-0.5 text-xs text-slate-700">
                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                    {label}
                  </div>
                );
              })}
              <p className="mt-1.5 text-[10px] text-slate-400">{t("map.edit.help")}</p>
            </div>
          )}
        </div>
      )}

      {/* Layers panel */}
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
