"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ArtworkSummary, CitySuggestion, ShapeCompatibility } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import {
  SearchIcon,
  MapPinIcon,
  DownloadIcon,
  SparklesIcon,
  ArrowRightIcon,
  CheckIcon,
  GridIcon,
} from "@/components/Icons";

const CATEGORY_COLORS: Record<string, string> = {
  basic: "from-rose-500 to-pink-500",
  animals: "from-amber-500 to-orange-500",
  sports: "from-accent-500 to-teal-500",
  nature: "from-green-500 to-emerald-500",
  city: "from-brand-500 to-violet-500",
  funny: "from-fuchsia-500 to-pink-500",
  symbols: "from-cyan-500 to-blue-500",
};

export default function Landing() {
  const { t } = useI18n();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<CitySuggestion[]>([]);
  const [searching, setSearching] = useState(false);
  const [artworks, setArtworks] = useState<ArtworkSummary[]>([]);
  const [cityNames, setCityNames] = useState<Record<string, string>>({});
  const [selectedCity, setSelectedCity] = useState<CitySuggestion | null>(null);
  const [cityShapes, setCityShapes] = useState<ShapeCompatibility[]>([]);
  const [loadingShapes, setLoadingShapes] = useState(false);

  useEffect(() => {
    api.listArtworks().then(setArtworks).catch(() => {});
    api.listAllCities().then((cities) => {
      const names: Record<string, string> = {};
      for (const c of cities) names[c.id] = c.name;
      setCityNames(names);
    }).catch(() => {});
  }, []);

  let debounce: ReturnType<typeof setTimeout>;
  const search = (v: string) => {
    setQ(v);
    clearTimeout(debounce);
    if (v.trim().length < 2) {
      setResults([]);
      return;
    }
    setSearching(true);
    debounce = setTimeout(() => {
      api.searchCities(v).then(setResults).catch(() => setResults([])).finally(() => setSearching(false));
    }, 250);
  };

  const selectCity = (c: CitySuggestion) => {
    setSelectedCity(c);
    setResults([]);
    setQ(c.name);
    setLoadingShapes(true);
    setCityShapes([]);
    api.getCityArtworks(c.id).then((r) => {
      setCityShapes(r.items.slice(0, 24));
      setLoadingShapes(false);
    }).catch(() => {
      setCityShapes([]);
      setLoadingShapes(false);
    });
  };

  const featuredCityIds = [
    "budapest", "debrecen", "szeged", "pecs", "gyor", "veszprem",
    "siofok", "balatonfured", "keszthely", "sopron", "eger", "esztergom",
  ];

  return (
    <div className="hero-gradient">
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-grid-pattern bg-[size:40px_40px] opacity-50" />
        <div className="relative mx-auto max-w-4xl px-4 py-20 text-center sm:px-6 sm:py-28">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-white/60 px-4 py-1.5 text-sm font-medium text-brand-700 backdrop-blur">
            <SparklesIcon size={16} />
            {t("landing.badge")}
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 text-balance sm:text-6xl">
            {t("landing.title1")}{" "}
            <span className="gradient-text">{t("landing.title2")}</span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600 text-balance">
            {t("landing.desc")}
          </p>

          <div className="relative mx-auto mt-8 max-w-xl">
            <div className="relative">
              <SearchIcon size={20} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                className="input py-3.5 pl-12 pr-4 text-base shadow-md"
                placeholder={t("landing.searchPlaceholder")}
                value={q}
                onChange={(e) => search(e.target.value)}
                aria-label={t("studio.searchCity")}
              />
              {searching && (
                <div className="absolute right-4 top-1/2 -translate-y-1/2">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
                </div>
              )}
            </div>
            {results.length > 0 && (
              <ul className="absolute z-20 mt-2 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl animate-slide-up">
                {results.map((r) => (
                  <li key={r.id}>
                    <button
                      className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-brand-50 transition-colors"
                      onClick={() => selectCity(r)}
                    >
                      <MapPinIcon size={18} className="text-brand-500" />
                      <div>
                        <div className="font-semibold text-slate-900">{r.name}</div>
                        <div className="text-xs text-slate-500">{r.country}</div>
                      </div>
                      <ArrowRightIcon size={16} className="ml-auto text-slate-300" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/studio" className="btn-primary px-6 py-3 text-base shadow-md">
              <SparklesIcon size={18} />
              {t("landing.openStudio")}
            </Link>
            <Link href="/gallery" className="btn-secondary px-6 py-3 text-base">
              <GridIcon size={18} />
              {t("landing.browseArt")}
            </Link>
          </div>
        </div>
      </section>

      {/* City shape opportunities — shown when a city is selected from search */}
      {selectedCity && (
        <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 animate-slide-up">
          <div className="mb-6 flex items-center justify-between">
            <h2 className="section-title flex items-center gap-2">
              <MapPinIcon size={24} className="text-brand-600" />
              {selectedCity.name} — {t("landing.shapeOpportunities")}
            </h2>
            <button
              className="btn-secondary px-4 py-2 text-sm"
              onClick={() => router.push(`/studio?city=${selectedCity.id}`)}
            >
              <SparklesIcon size={16} />
              {t("landing.openStudio")}
            </button>
          </div>
          {loadingShapes ? (
            <div className="flex items-center gap-3 py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
              <span className="text-sm text-slate-500">{t("studio.loadingCompat")}</span>
            </div>
          ) : cityShapes.length > 0 ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
              {cityShapes.map((s) => (
                <Link
                  key={s.artworkId}
                  href={`/gallery/${s.artworkId}`}
                  className="card card-hover group flex flex-col items-center p-3"
                >
                  <div className={`mb-2 flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br ${CATEGORY_COLORS[s.category] || "from-slate-400 to-slate-500"} p-1.5 shadow-sm`}>
                    <img src={s.previewSvgUrl} alt={s.artworkName} className="h-full w-full invert" />
                  </div>
                  <span className="text-center text-xs font-medium text-slate-700">{s.artworkName}</span>
                  <div className="mt-1 flex items-center gap-1.5 text-[10px]">
                    {s.isSignature && <span className="badge-amber text-[8px]">{t("studio.signature")}</span>}
                    <span className="font-mono text-accent-600">{Math.round(s.fitScore * 100)}%</span>
                    <span className="text-slate-400">{s.minKm}–{s.maxKm}km</span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">{t("studio.noCities")}</p>
          )}
        </section>
      )}

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          {[
            { icon: <GridIcon size={24} />, title: t("landing.step1Title"), desc: t("landing.step1Desc") },
            { icon: <MapPinIcon size={24} />, title: t("landing.step2Title"), desc: t("landing.step2Desc") },
            { icon: <DownloadIcon size={24} />, title: t("landing.step3Title"), desc: t("landing.step3Desc") },
          ].map(({ icon, title, desc }) => (
            <div key={title} className="card card-hover p-6">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-accent-500 text-white shadow-md">
                {icon}
              </div>
              <h3 className="font-bold text-slate-900">{title}</h3>
              <p className="mt-1.5 text-sm text-slate-600">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="section-title">{t("landing.featuredCities")}</h2>
          <Link href="/cities" className="text-sm font-medium text-brand-600 hover:text-brand-700">
            {t("landing.viewAll")}
          </Link>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {featuredCityIds.map((id) => (
            <Link key={id} href={`/cities/${id}`} className="card card-hover group p-4 text-center">
              <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 text-brand-600 transition-colors group-hover:bg-brand-100">
                <MapPinIcon size={22} />
              </div>
              <div className="font-semibold text-sm text-slate-900">{cityNames[id] || id}</div>
              <div className="text-xs text-slate-400">{t("footer.copy").includes("OpenStreetMap") ? "Magyarország" : "Hungary"}</div>
            </Link>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="section-title">{t("landing.artworkLibrary")}</h2>
          <Link href="/gallery" className="text-sm font-medium text-brand-600 hover:text-brand-700">
            {t("landing.browseAll")}
          </Link>
        </div>
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-10">
          {artworks.slice(0, 10).map((a) => (
            <Link key={a.id} href={`/gallery/${a.id}`} className="card card-hover group flex flex-col items-center p-3">
              <div className={`mb-2 flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br ${CATEGORY_COLORS[a.category] || "from-slate-400 to-slate-500"} p-1.5 shadow-sm`}>
                <img src={a.previewSvgUrl} alt={a.name} className="h-full w-full invert" />
              </div>
              <span className="text-center text-xs font-medium text-slate-700">{a.name}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
        <div className="card overflow-hidden p-0">
          <div className="grid grid-cols-1 md:grid-cols-2">
            <div className="p-8">
              <h2 className="section-title">{t("landing.howHood")}</h2>
              <ul className="mt-4 space-y-3">
                {[t("landing.feat1"), t("landing.feat2"), t("landing.feat3"), t("landing.feat4"), t("landing.feat5"), t("landing.feat6")].map((feat) => (
                  <li key={feat} className="flex items-start gap-2.5 text-sm text-slate-700">
                    <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-100 text-accent-600">
                      <CheckIcon size={14} />
                    </div>
                    {feat}
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-gradient-to-br from-brand-600 to-accent-600 p-8 text-white">
              <h3 className="text-lg font-bold">{t("landing.gpxModes")}</h3>
              <div className="mt-4 space-y-4 text-sm">
                <div>
                  <div className="font-semibold">{t("landing.continuousMode")}</div>
                  <p className="mt-1 text-white/80">{t("landing.continuousDesc")}</p>
                </div>
                <div>
                  <div className="font-semibold">{t("landing.dotsMode")}</div>
                  <p className="mt-1 text-white/80">{t("landing.dotsDesc")}</p>
                </div>
              </div>
              <Link href="/studio" className="mt-6 inline-flex items-center gap-2 rounded-xl bg-white/20 px-4 py-2.5 text-sm font-semibold backdrop-blur hover:bg-white/30 transition-colors">
                <SparklesIcon size={16} />
                {t("landing.tryNow")}
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
