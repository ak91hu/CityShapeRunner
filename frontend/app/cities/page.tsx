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

  useEffect(() => {
    api.listAllCities().then((items) => {
      setCities(items);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const filtered = cities.filter((c) =>
    !search || c.name.toLowerCase().includes(search.toLowerCase()),
  );

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

      <div className="relative mb-6 max-w-md">
        <SearchIcon size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          className="input pl-11"
          placeholder={t("cities.search")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {loading ? (
        <LoadingSpinner label={t("cities.loading")} />
      ) : filtered.length === 0 ? (
        <EmptyState icon={<MapPinIcon size={48} />} title={t("gallery.empty")} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((c) => (
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
                <StatCard label={t("cities.roadDensity")} value={c.roadDensity ? c.roadDensity.toFixed(2) : "—"} icon={<SparklesIcon size={14} />} color="brand" />
                <StatCard label={t("cities.bridges")} value={c.bridgeCount ?? 0} icon={<BridgeIcon size={14} />} color={c.bridgeCount ? "accent" : "slate"} />
                <StatCard label={t("cities.river")} value={c.hasRiver ? t("cities.yes") : t("cities.no")} icon={<RiverIcon size={14} />} color={c.hasRiver ? "accent" : "slate"} />
              </div>

              {c.signatureArtworkIds.length > 0 && (
                <div className="mt-3">
                  <div className="text-xs font-medium text-slate-500">{t("cities.signature")}</div>
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {c.signatureArtworkIds.slice(0, 5).map((aid) => (
                      <span key={aid} className="badge-blue text-[10px]">{aid}</span>
                    ))}
                  </div>
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
