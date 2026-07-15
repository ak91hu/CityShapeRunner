"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { CityDetail } from "@/lib/types";
import { LoadingSpinner, EmptyState, StatCard } from "@/components/UI";
import { useI18n } from "@/lib/i18n";
import {
  BuildingIcon,
  MapPinIcon,
  RiverIcon,
  BridgeIcon,
  SparklesIcon,
  ArrowRightIcon,
  SearchIcon,
} from "@/components/Icons";

export default function CitiesPage() {
  const { t } = useI18n();
  const [cities, setCities] = useState<CityDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("All");
  const [visibleCount, setVisibleCount] = useState(30);

  // Reset pagination when filter changes
  useEffect(() => {
    setVisibleCount(30);
  }, [search, activeTab]);

  useEffect(() => {
    api.listAllCities().then((items) => {
      setCities(items);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const TABS = ["All", "Hungary", "Europe", "North America", "South America", "Asia", "Africa", "Oceania"];

  const filtered = cities.filter((c) => {
    if (search && !c.name.toLowerCase().includes(search.toLowerCase())) return false;
    if (activeTab === "All") return true;
    if (activeTab === "Hungary") return c.countryCode === "HU";
    if (activeTab === "Europe") return c.cityAffinityTags?.includes("european") || c.countryCode === "HU";
    return c.cityAffinityTags?.includes(activeTab);
  });

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="mb-8">
        <h1 className="flex items-center gap-2 text-3xl font-extrabold tracking-tight">
          <BuildingIcon size={28} className="text-brand-600" />
          {t("cities.title")}
        </h1>
        <p className="mt-2 text-slate-600">
          {cities.length} {t("cities.desc")}
        </p>
      </div>

      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative max-w-md w-full">
          <SearchIcon size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            className="input pl-11 w-full"
            placeholder={t("cities.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        
        <div className="flex overflow-x-auto pb-1 scrollbar-hide gap-2">
          {TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                activeTab === tab
                  ? "bg-brand-600 text-white shadow-sm"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {tab === "Hungary" ? "Magyarország" : tab === "All" ? t("gallery.all") : tab}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <LoadingSpinner label={t("cities.loading")} />
      ) : filtered.length === 0 ? (
        <EmptyState icon={<MapPinIcon size={48} />} title={t("gallery.empty")} />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.slice(0, visibleCount).map((c) => (
              <Link key={c.id} href={`/cities/${c.id}`} className="card card-hover group p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-accent-500 text-white shadow-md">
                    <MapPinIcon size={24} />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900">{c.name}</h3>
                    <p className="text-xs text-slate-500">{c.country}</p>
                  </div>
                </div>
                <ArrowRightIcon size={18} className="text-slate-300 transition-colors group-hover:text-brand-500" />
              </div>

              <div className="mt-4 grid grid-cols-3 gap-2">
                <StatCard label={t("cities.roadDensity")} value={c.roadDensity ? c.roadDensity.toFixed(2) : "-"} icon={<SparklesIcon size={14} />} color="brand" />
                <StatCard label={t("cities.bridges")} value={c.bridgeCount ?? 0} icon={<BridgeIcon size={14} />} color={c.bridgeCount ? "accent" : "slate"} />
                <StatCard label={t("cities.river")} value={c.hasRiver ? t("cities.yes") : t("cities.no")} icon={<RiverIcon size={14} />} color={c.hasRiver ? "accent" : "slate"} />
              </div>


              </Link>
            ))}
          </div>
          {visibleCount < filtered.length && (
            <div className="mt-8 flex justify-center">
              <button
                onClick={() => setVisibleCount((v) => v + 30)}
                className="rounded-full bg-brand-50 px-6 py-2 text-sm font-medium text-brand-700 hover:bg-brand-100 transition-colors"
              >
                {t("cities.loadMore") || "Load more..."}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
