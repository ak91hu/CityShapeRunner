"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import {
  type Activity,
  type ArtworkSummary,
  type CandidateSummary,
  type CityCompatibility,
  type Difficulty,
  type GenerationJobStatus,
} from "@/lib/types";
import { useI18n, type Lang } from "@/lib/i18n";
import {
  SearchIcon,
  MapPinIcon,
  PlayIcon,
  StopIcon,
  DownloadIcon,
  ShareIcon,
  AlertIcon,
  CheckIcon,
  SparklesIcon,
  ActivityIcon,
  GaugeIcon,
  RulerIcon,
  CopyIcon,
  GridIcon,
} from "./Icons";
import { ScoreRing, ScoreBar, WarningList, CategoryBadge } from "./UI";

const RouteMap = dynamic(() => import("./RouteMap"), { ssr: false });

const CATEGORY_COLORS: Record<string, string> = {
  basic: "from-rose-500 to-pink-500",
  animals: "from-amber-500 to-orange-500",
  sports: "from-accent-500 to-teal-500",
  nature: "from-green-500 to-emerald-500",
  city: "from-brand-500 to-violet-500",
  funny: "from-fuchsia-500 to-pink-500",
  symbols: "from-cyan-500 to-blue-500",
};

const CATEGORIES = ["basic", "animals", "sports", "nature", "city", "funny", "symbols"];

export default function Studio() {
  const { t, tShape, lang } = useI18n() as { t: (k: string) => string; tShape: (id: string, n: string) => string; lang: Lang };
  const router = useRouter();
  const params = useSearchParams();

  const [artworks, setArtworks] = useState<ArtworkSummary[]>([]);
  const [shapeSearch, setShapeSearch] = useState("");
  const [shapeCategory, setShapeCategory] = useState<string | null>(null);
  const [selectedShape, setSelectedShape] = useState<ArtworkSummary | null>(null);
  const [compatCities, setCompatCities] = useState<CityCompatibility[]>([]);
  const [citySearch, setCitySearch] = useState("");
  const [loadingCompat, setLoadingCompat] = useState(false);
  const [city, setCity] = useState<CityCompatibility | null>(null);
  const [activity, setActivity] = useState<Activity>("running");
  const [distance, setDistance] = useState(10);

  const [job, setJob] = useState<GenerationJobStatus | null>(null);
  const [polling, setPolling] = useState(false);
  const [artworkMap, setArtworkMap] = useState<Record<string, ArtworkSummary>>({});
  const [selected, setSelected] = useState<CandidateSummary | null>(null);
  const [geojson, setGeojson] = useState<GeoJSON.FeatureCollection | null>(null);
  const [routeId, setRouteId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const STAGE_ORDER = [
    "loading_city", "loading_road_graph", "building_indexes", "parsing_shapes",
    "ranking_shapes", "selecting_artworks", "generating_placements", "generating_transforms",
    "corridor_scoring", "fitting_candidates", "beam_matching", "constructing_routes",
    "repairing_routes", "refining_candidates", "scoring", "ai_retry", "storing_results", "completed",
  ];

  useEffect(() => {
    api.listArtworks().then((items) => {
      setArtworks(items);
      const map: Record<string, ArtworkSummary> = {};
      for (const a of items) map[a.id] = a;
      setArtworkMap(map);
      
      const q = params.get("q");
      if (q) setShapeSearch(q);
      
      const artworkId = params.get("artwork");
      if (artworkId && map[artworkId]) {
        setSelectedShape(map[artworkId]);
      }
    });
  }, [params]);

  const onShapeSelect = useCallback((shape: ArtworkSummary) => {
    setSelectedShape(shape);
    setCity(null);
    setCompatCities([]);
    setLoadingCompat(true);
    api.getCompatibleCities(shape.id, activity).then((r) => {
      setCompatCities(r.items);
      setLoadingCompat(false);
    }).catch(() => {
      setCompatCities([]);
      setLoadingCompat(false);
    });
  }, [activity]);

  useEffect(() => {
    if (selectedShape) {
      console.log('Selected shape:', selectedShape.id);
      setLoadingCompat(true);
      api.getCompatibleCities(selectedShape.id, activity).then((r) => {
        console.log('Got compat cities:', r.items?.length);
        setCompatCities(r.items);
        setLoadingCompat(false);
      }).catch((err) => {
        console.error('Error fetching compat cities:', err);
        setCompatCities([]);
        setLoadingCompat(false);
      });
    }
  }, [activity, selectedShape]);

  const onCitySelect = (c: CityCompatibility) => {
    setCity(c);
    setDistance(c.recommendedKm);
  };

  useEffect(() => {
    const cityId = params.get("city");
    if (cityId) {
      api.searchCities(cityId).then((r) => {
        const found = r.find((c) => c.id === cityId) ?? r[0];
        if (found) {
          setCity({
            cityId: found.id, cityName: found.name, fitScore: 0.5,
            minKm: 3, maxKm: 100, recommendedKm: 10, isSignature: false,
          });
        }
      });
    }
  }, [params]);

  const generate = async () => {
    if (!city) return;
    setError(null); setSelected(null); setGeojson(null); setRouteId(null); setShareUrl(null);
    try {
      const created = await api.createJob({
        cityId: city.cityId, activity, targetDistanceKm: distance,
        maxSuggestions: 3,
        artworkIds: selectedShape ? [selectedShape.id] : undefined,
      });
      setPolling(true);
      setJob({ jobId: created.jobId, status: created.status, progressPercent: 0, suggestions: [] });
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const cancelJob = async () => {
    if (!job) return;
    try {
      await api.cancelJob(job.jobId);
      setPolling(false);
      setJob((j) => (j ? { ...j, status: "cancelled" } : j));
    } catch {}
  };

  useEffect(() => {
    if (!polling || !job) return;
    let active = true;
    const tick = async () => {
      const st = await api.getJob(job.jobId);
      if (!active) return;
      setJob(st);
      if (st.status === "completed" || st.status === "failed" || st.status === "cancelled") {
        setPolling(false);
        if (st.status === "failed") setError(st.errorMessage || t("studio.genFailed"));
        return;
      }
      setTimeout(tick, 500);
    };
    tick();
    return () => { active = false; };
  }, [polling, job?.jobId]);

  const preview = async (c: CandidateSummary) => {
    setSelected(c); setRouteId(null); setShareUrl(null);
    const gj = await api.candidateGeoJson(c.candidateId);
    setGeojson(gj);
  };

  const createRoute = async () => {
    if (!selected) return;
    const route = await api.createRoute(selected.candidateId);
    setRouteId(route.routeId);
  };

  const share = async () => {
    if (!routeId) return;
    const s = await api.createShare(routeId);
    setShareUrl(`${window.location.origin}/r/${s.shareId}`);
  };

  const copyShare = () => {
    if (!shareUrl) return;
    navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 500);
  };

  const ACTIVITIES = [
    { value: "running" as Activity, label: t("studio.running"), icon: "🏃" },
    { value: "cycling" as Activity, label: t("studio.cycling"), icon: "🚴" },
    { value: "walking" as Activity, label: t("studio.walking"), icon: "🚶" },
  ];


  const cyclingShort = activity === "cycling" && distance < 8;
  const progressPct = job ? job.progressPercent : 0;
  const currentStageIdx = job?.progressStage ? STAGE_ORDER.indexOf(job.progressStage) : -1;
  const sortedSuggestions = useMemo(
    () => [...(job?.suggestions ?? [])].sort((a, b) => a.rank - b.rank),
    [job?.suggestions],
  );

  const filteredArtworks: ArtworkSummary[] = artworks.filter((a) => {
    if (shapeSearch && !a.name.toLowerCase().includes(shapeSearch.toLowerCase())) return false;
    if (shapeCategory && a.category !== shapeCategory) return false;
    return true;
  });

  const distMin = city?.minKm ?? 3;
  const distMax = city?.maxKm ?? 100;

  // Current step: 1=shape, 2=city, 3=generate
  const currentStep = selectedShape ? (city ? 3 : 2) : 1;

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col lg:flex-row">
      {/* Sidebar */}
      <aside className="flex w-full shrink-0 flex-col overflow-y-auto border-r border-slate-200 bg-white scrollbar-thin lg:w-[420px]">
        <div className="p-5">
          <h1 className="flex items-center gap-2 text-lg font-bold">
            <SparklesIcon size={20} className="text-brand-600" />
            {t("studio.title")}
          </h1>
          <p className="mt-1 text-xs text-slate-500">{t("studio.subtitle")}</p>

          {/* Step indicator */}
          <div className="mt-4 flex items-center gap-1">
            {[1, 2, 3].map((step) => (
              <div key={step} className="flex flex-1 items-center gap-1">
                <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-all ${
                  currentStep >= step ? "bg-brand-600 text-white" : "bg-slate-200 text-slate-400"
                }`}>
                  {currentStep > step ? <CheckIcon size={14} /> : step}
                </div>
                <span className={`hidden text-xs font-medium sm:inline ${currentStep >= step ? "text-slate-700" : "text-slate-400"}`}>
                  {t(`studio.step${step}`)}
                </span>
                {step < 3 && <div className={`h-0.5 flex-1 rounded ${currentStep > step ? "bg-brand-500" : "bg-slate-200"}`} />}
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-5 px-5 pb-5">
          {/* Step 1: Shape selection */}
          <div>
            <label className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate-700">
              <GridIcon size={16} className="text-brand-500" />
              {t("studio.shape")}
            </label>
            {selectedShape ? (
              <div className="flex items-center gap-3 rounded-xl bg-brand-50 px-3 py-2.5">
                <div className={`flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-br ${CATEGORY_COLORS[selectedShape.category] || "from-slate-400 to-slate-500"} p-1.5`}>
                  <img src={selectedShape.previewSvgUrl} alt={selectedShape.name} className="h-full w-full invert" />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-bold text-brand-700">{tShape(selectedShape.id, selectedShape.name)}</div>
                  <div className="mt-0.5"><CategoryBadge category={selectedShape.category} /></div>
                </div>
                <button
                  className="rounded-lg border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-white"
                  onClick={() => { setSelectedShape(null); setCompatCities([]); setCity(null); }}
                >
                  {t("studio.changeShape")}
                </button>
              </div>
            ) : (
              <>
                <div className="relative mb-2">
                  <SearchIcon size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    className="input pl-11"
                    placeholder={t("studio.searchShape")}
                    value={shapeSearch}
                    onChange={(e) => setShapeSearch(e.target.value)}
                  />
                </div>
                <div className="mb-2 flex flex-wrap gap-1">
                  <button
                    className={`rounded-lg px-2 py-1 text-xs font-medium ${!shapeCategory ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600"}`}
                    onClick={() => setShapeCategory(null)}
                  >
                    {t("gallery.all")}
                  </button>
                  {CATEGORIES.map((cat) => (
                    <button
                      key={cat}
                      className={`rounded-lg px-2 py-1 text-xs font-medium ${shapeCategory === cat ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600"}`}
                      onClick={() => setShapeCategory(shapeCategory === cat ? null : cat)}
                    >
                      {t("cat." + cat) || cat}
                    </button>
                  ))}
                </div>
                <div className="max-h-52 overflow-y-auto rounded-xl border border-slate-200 scrollbar-thin">
                  <div className="grid grid-cols-4 gap-1.5 p-2 sm:grid-cols-5">
                    {filteredArtworks.map((a: ArtworkSummary) => (
                      <button
                        key={a.id}
                        data-testid="shape-button"
                        className="flex flex-col items-center rounded-lg border-2 border-transparent p-1.5 transition-all hover:border-brand-300 hover:bg-brand-50"
                        onClick={() => onShapeSelect(a)}
                        title={a.name}
                      >
                        <div className={`flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-br ${CATEGORY_COLORS[a.category] || "from-slate-400 to-slate-500"} p-1`}>
                          <img src={a.previewSvgUrl} alt={a.name} className="h-full w-full invert" />
                        </div>
                        <span className="mt-0.5 w-full truncate text-center text-[9px] font-medium text-slate-600">{tShape(a.id, a.name)}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Step 2: Compatible cities */}
          {selectedShape && (
            <div>
              <label className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate-700">
                <MapPinIcon size={16} className="text-brand-500" />
                {t("studio.city")}
              </label>
              {loadingCompat ? (
                <div className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-3">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
                  <span className="text-xs text-slate-500">{t("studio.loadingCompat")}</span>
                </div>
              ) : compatCities.length === 0 ? (
                <div className="rounded-lg bg-amber-50 px-3 py-3 text-xs text-amber-700">
                  {t("studio.noCities")}
                </div>
              ) : (
                <>
                  <div className="mb-2 relative">
                    <SearchIcon size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      className="input pl-9 py-1.5 text-sm w-full"
                      placeholder={t("cities.search") || "Search city..."}
                      value={citySearch}
                      onChange={(e) => setCitySearch(e.target.value)}
                    />
                  </div>
                  <p className="mb-1.5 text-xs text-slate-400">{compatCities.filter(c => !citySearch || c.cityName.toLowerCase().includes(citySearch.toLowerCase())).length} {t("studio.compatibleCities").toLowerCase()}</p>
                  <div className="max-h-56 space-y-1 overflow-y-auto rounded-xl border border-slate-200 scrollbar-thin">
                    {compatCities.filter(c => !citySearch || c.cityName.toLowerCase().includes(citySearch.toLowerCase())).map((c) => (
                      <button
                        key={c.cityId}
                        data-testid="city-button"
                        className={`flex w-full items-center gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-brand-50 ${city?.cityId === c.cityId ? "bg-brand-50 ring-1 ring-brand-300" : ""}`}
                        onClick={() => onCitySelect(c)}
                      >
                        <MapPinIcon size={14} className="shrink-0 text-brand-500" />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="truncate text-sm font-medium text-slate-900">{c.cityName}</span>
                            {c.isSignature && <span className="badge-amber text-[8px]">{t("studio.signature")}</span>}
                          </div>
                          <div className="flex items-center gap-2 text-xs text-slate-500">
                            <span>{c.minKm}-{c.maxKm} km</span>
                            <span className="text-accent-600">{Math.round(c.fitScore * 100)}%</span>
                          </div>
                        </div>
                        {city?.cityId === c.cityId && <CheckIcon size={16} className="shrink-0 text-brand-600" />}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}



          {/* Distance */}
          {city && (
            <div>
              <label className="mb-1.5 flex items-center justify-between text-sm font-semibold text-slate-700">
                <span className="flex items-center gap-1.5">
                  <RulerIcon size={16} className="text-brand-500" />
                  {t("studio.distance")}
                </span>
                <span className="rounded-lg bg-brand-100 px-2.5 py-0.5 font-mono text-sm font-bold text-brand-700">
                  {distance} km
                </span>
              </label>
              <input
                type="range"
                min={distMin}
                max={distMax}
                step={1}
                value={Math.max(distMin, Math.min(distMax, distance))}
                onChange={(e) => setDistance(Number(e.target.value))}
                className="w-full accent-brand-600"
              />
              <div className="mt-1 flex justify-between text-xs text-slate-400">
                <span>{distMin} km</span>
                <span className="text-accent-600">{t("studio.recommended")}: {city.recommendedKm} km</span>
                <span>{distMax} km</span>
              </div>
              {cyclingShort && (
                <p className="mt-2 flex items-center gap-1.5 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  <AlertIcon size={14} />
                  {t("studio.cyclingWarn")}
                </p>
              )}
            </div>
          )}



          {/* Generate / Cancel */}
          <div className="space-y-2">
            {!polling ? (
              <button
                className="btn-primary w-full py-3.5 text-base shadow-md"
                disabled={!city}
                onClick={generate}
              >
                <PlayIcon size={18} />
                {t("studio.generate")}
              </button>
            ) : (
              <button
                className="btn w-full py-3.5 text-base bg-rose-600 text-white hover:bg-rose-700 focus:ring-rose-500 shadow-md"
                onClick={cancelJob}
              >
                <StopIcon size={18} />
                {t("studio.cancel")}
              </button>
            )}
          </div>




        </div>
      </aside>

      {/* Main area */}
      <main className="flex flex-1 flex-col overflow-hidden">
        <div className="relative flex-1 overflow-hidden">
          {polling ? (
            <div className="flex h-full items-center justify-center bg-grid-pattern bg-[size:40px_40px]">
              <div className="text-center">
                <div className="relative mx-auto mb-4 flex h-20 w-20 items-center justify-center">
                  <div className="absolute inset-0 animate-ping rounded-full bg-brand-400 opacity-20" />
                  <div className="absolute inset-2 animate-pulse rounded-full bg-accent-400 opacity-40" />
                  <div className="relative flex h-full w-full items-center justify-center rounded-3xl bg-gradient-to-br from-brand-500 to-accent-500 text-white shadow-xl shadow-brand-500/30">
                    <SparklesIcon size={40} className="animate-pulse" />
                  </div>
                </div>
                <h3 className="text-xl font-bold text-slate-700 animate-pulse">{t("studio.generating")}</h3>
                <p className="mt-2 max-w-sm text-sm text-slate-500 mb-6">
                  {lang === "hu" ? "Kérlek várj, az algoritmus épp a valós utcahálózatra illeszti a formát..." : "Please wait while the algorithm snaps the shape to the real street network..."}
                </p>

                {/* Progress */}
                {job && (
                  <div className="mx-auto max-w-md rounded-xl border border-slate-200 bg-white/80 backdrop-blur-sm p-5 text-left shadow-sm" aria-live="polite">
                    <div className="mb-2 flex items-center justify-between text-sm">
                      <span className="font-semibold text-slate-700">
                        {job.status === "completed" ? t("studio.complete") : job.status === "failed" ? t("studio.failed") : t("studio.generating")}
                      </span>
                      <span className="font-mono font-bold text-brand-600">{progressPct}%</span>
                    </div>
                    <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${job.status === "failed" ? "bg-rose-500" : "bg-gradient-to-r from-brand-500 to-accent-500"}`}
                        style={{ width: `${progressPct}%` }}
                      />
                    </div>
                    {job.progressStage && polling && (
                      <div className="mt-4 grid grid-cols-2 gap-y-2 gap-x-4">
                        {STAGE_ORDER.filter((s) => s !== "completed").slice(0, 16).map((stage, i) => {
                          const done = i < currentStageIdx;
                          const current = i === currentStageIdx;
                          return (
                            <div key={stage} className={`flex items-center gap-2 text-xs ${done ? "text-accent-600" : current ? "text-brand-600 font-medium" : "text-slate-400 opacity-50"}`}>
                              <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[8px] ${done ? "bg-accent-500 text-white" : current ? "bg-brand-500 text-white animate-pulse" : "bg-slate-200"}`}>
                                {done ? "✓" : i + 1}
                              </span>
                              <span className="truncate">{t("stage." + stage) || stage}</span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : error ? (
            <div className="flex h-full items-center justify-center bg-grid-pattern bg-[size:40px_40px]">
              <div className="text-center max-w-md p-6 bg-white/90 backdrop-blur-sm rounded-2xl shadow-xl border border-rose-200">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-rose-100 text-rose-500">
                  <AlertIcon size={32} />
                </div>
                <h3 className="text-xl font-bold text-slate-800">{t("studio.genFailed")}</h3>
                <p className="mt-3 text-sm text-slate-600">{error}</p>
              </div>
            </div>
          ) : geojson ? (
            <RouteMap key={selected?.candidateId ?? "empty"} geojson={geojson} center={undefined} />
          ) : sortedSuggestions.length > 0 ? (
            <div className="flex h-full items-center justify-center bg-grid-pattern bg-[size:40px_40px]">
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-brand-500 to-accent-500 text-white shadow-xl">
                  <MapPinIcon size={40} />
                </div>
                <h3 className="text-lg font-bold text-slate-700">{t("studio.selectPreview")}</h3>
                <p className="mt-1 text-sm text-slate-400">{t("studio.selectDesc")}</p>
              </div>
            </div>
          ) : !selectedShape ? (
            <div className="flex h-full items-center justify-center bg-grid-pattern bg-[size:40px_40px]">
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-brand-500 to-accent-500 text-white shadow-xl">
                  <GridIcon size={40} />
                </div>
                <h3 className="text-lg font-bold text-slate-700">{t("studio.pickShapeFirst")}</h3>
                <p className="mt-1 text-sm text-slate-400">{t("studio.pickShapeFirstDesc")}</p>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center bg-grid-pattern bg-[size:40px_40px]">
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-brand-500 to-accent-500 text-white shadow-xl">
                  <MapPinIcon size={40} />
                </div>
                <h3 className="text-lg font-bold text-slate-700">{t("studio.ready")}</h3>
                <p className="mt-1 text-sm text-slate-400">{t("studio.readyDesc")}</p>
              </div>
            </div>
          )}
        </div>

        {/* Suggestions */}
        {sortedSuggestions.length > 0 && (
          <div className="h-56 shrink-0 overflow-y-auto border-t border-slate-200 bg-white p-3 scrollbar-thin">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-700">{sortedSuggestions.length} {t("studio.suggestions")}</h2>
              <span className="text-xs text-slate-400">{t("studio.sortedByRank")}</span>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
              {sortedSuggestions.map((c) => {
                const art = artworkMap[c.artworkId];
                const isSel = selected?.candidateId === c.candidateId;
                return (
                  <button
                    key={c.candidateId}
                    className={`card p-2.5 text-left transition-all ${isSel ? "ring-2 ring-brand-500 border-brand-400" : "card-hover"}`}
                    onClick={() => preview(c)}
                  >
                    <div className="flex items-center gap-2">
                      {art && <img src={art.previewSvgUrl} alt={c.artworkName} className="h-10 w-10 shrink-0 rounded-lg bg-slate-50 p-1" />}
                      <div className="min-w-0">
                        <div className="flex items-center gap-1">
                          <span className="text-xs font-bold text-brand-600">#{c.rank}</span>
                        </div>
                        <div className="truncate text-sm font-semibold text-slate-900">{c.artworkName}</div>
                      </div>
                    </div>
                    <div className="mt-2 flex items-center justify-between text-xs">
                      <span className="font-mono font-semibold text-slate-700">{c.distanceKm} km</span>
                      <span className="font-mono font-bold text-accent-600">{Math.round(c.fitScore * 100)}%</span>
                    </div>
                    <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-200">
                      <div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-accent-500" style={{ width: `${Math.round(c.fitScore * 100)}%` }} />
                    </div>
                    {c.warnings.length > 0 && (
                      <div className="mt-1.5 flex items-center gap-1 text-xs text-amber-600">
                        <AlertIcon size={12} />{c.warnings.length}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Detail / Export bar */}
        {selected && (
          <div className="shrink-0 border-t-2 border-slate-200 bg-white p-4 animate-slide-up">
            <div className="flex flex-wrap items-start gap-4">
              <div className="flex items-center gap-3">
                {artworkMap[selected.artworkId] && (
                  <img src={artworkMap[selected.artworkId].previewSvgUrl} alt={selected.artworkName} className="h-14 w-14 rounded-xl bg-slate-50 p-1.5" />
                )}
                <div>
                  <h2 className="text-lg font-bold text-slate-900">{selected.artworkName}</h2>
                  <p className="text-sm text-slate-500">{selected.distanceKm} km · #{selected.rank}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 rounded-xl bg-slate-50 px-4 py-2">
                <ScoreRing value={selected.fitScore} size={56} label={t("ui.fitScore")} />
                <div className="space-y-1.5">
                  <ScoreBar label={t("ui.shape")} value={selected.shapeSimilarityScore} color="accent" />
                  <ScoreBar label={t("ui.road")} value={selected.roadQualityScore} color="brand" />
                </div>
              </div>
              <div className="ml-auto flex flex-wrap items-center gap-2">
                <button className="btn-dark px-4 py-2.5 text-sm" onClick={createRoute} disabled={!selected}>
                  {routeId ? <><CheckIcon size={16} className="text-accent-400" />{t("studio.routeReady")}</> : t("studio.createRoute")}
                </button>
                <a className={`btn px-4 py-2.5 text-sm ${routeId ? "bg-brand-600 text-white hover:bg-brand-700" : "bg-slate-200 text-slate-400 cursor-not-allowed"}`} href={routeId ? api.gpxUrl(routeId, "continuous") : undefined} download="route.gpx">
                  <DownloadIcon size={16} />GPX
                </a>
                <button className="btn-secondary px-4 py-2.5 text-sm" disabled={!routeId} onClick={share}>
                  <ShareIcon size={16} />{t("studio.share")}
                </button>
              </div>
            </div>
            {shareUrl && (
              <div className="mt-3 flex items-center gap-2 rounded-xl bg-brand-50 p-2.5">
                <input className="flex-1 bg-transparent text-sm text-brand-700 outline-none" value={shareUrl} readOnly />
                <button className="btn-primary px-3 py-1.5 text-xs" onClick={copyShare}>
                  {copied ? <><CheckIcon size={14} />{t("studio.copied")}</> : <><CopyIcon size={14} />{t("studio.copy")}</>}
                </button>
                <button className="btn-secondary px-3 py-1.5 text-xs" onClick={() => router.push(shareUrl.replace(window.location.origin, ""))}>
                  {t("studio.open")}
                </button>
              </div>
            )}
            {selected.warnings.length > 0 && (
              <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3">
                <div className="flex items-center gap-1.5 text-xs font-bold text-amber-800">
                  <AlertIcon size={14} />{t("studio.warnings")}
                </div>
                <div className="mt-1.5"><WarningList warnings={selected.warnings} /></div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
