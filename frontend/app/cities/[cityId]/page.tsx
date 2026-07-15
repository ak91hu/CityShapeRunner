"use client";

import { use, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ArtworkSummary, CityDetail } from "@/lib/types";
import { LoadingSpinner, StatCard, CategoryBadge } from "@/components/UI";
import { useI18n } from "@/lib/i18n";
import {
  MapPinIcon,
  RiverIcon,
  BridgeIcon,
  SparklesIcon,
  ArrowRightIcon,
  BuildingIcon,
  RulerIcon,
} from "@/components/Icons";

const RouteMap = dynamic(() => import("@/components/RouteMap"), { ssr: false });

const CATEGORY_COLORS: Record<string, string> = {
  basic: "from-rose-500 to-pink-500",
  animals: "from-amber-500 to-orange-500",
  sports: "from-accent-500 to-teal-500",
  nature: "from-green-500 to-emerald-500",
  city: "from-brand-500 to-violet-500",
  funny: "from-fuchsia-500 to-pink-500",
  symbols: "from-cyan-500 to-blue-500",
};

export default function CityDetailPage({ params }: { params: Promise<{ cityId: string }> }) {
  const { t, tShape } = useI18n();
  const { cityId } = use(params);
  const [city, setCity] = useState<CityDetail | null>(null);
  const [signatureArtworks, setSignatureArtworks] = useState<ArtworkSummary[]>([]);
  const [allArtworks, setAllArtworks] = useState<ArtworkSummary[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.getCity(cityId).then((c) => {
      setCity(c);
      if (c) {
        api.listArtworks({ cityId: c.id }).then(setAllArtworks).catch(() => {});
      }
    }).catch((e) => setErr((e as Error).message));
  }, [cityId]);

  useEffect(() => {
    if (city && allArtworks.length > 0) {
      const sig = city.signatureArtworkIds
        .map((id) => allArtworks.find((a) => a.id === id))
        .filter((a): a is ArtworkSummary => a !== null);
      setSignatureArtworks(sig);
    }
  }, [city, allArtworks]);

  if (err) return <div className="p-8 text-rose-600">Error: {err}</div>;
  if (!city) return <LoadingSpinner label={t("cities.loading")} />;

  const boundaryGeojson: GeoJSON.FeatureCollection =
    city.boundaryGeojson ?? {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: { kind: "boundary" },
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [city.bbox[0], city.bbox[1]],
                [city.bbox[2], city.bbox[1]],
                [city.bbox[2], city.bbox[3]],
                [city.bbox[0], city.bbox[3]],
                [city.bbox[0], city.bbox[1]],
              ],
            ],
          },
        },
      ],
    };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <Link href="/cities" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-brand-600">
        {t("city.back")}
      </Link>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-accent-500 text-white shadow-lg">
              <MapPinIcon size={28} />
            </div>
            <div>
              <h1 className="text-3xl font-extrabold tracking-tight">{city.name}</h1>
              <p className="text-slate-500">{city.country}</p>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-3">
            <StatCard label={t("cities.roadDensity")} value={city.roadDensity ? city.roadDensity.toFixed(2) : "-"} icon={<SparklesIcon size={16} />} color="brand" />
            <StatCard label={t("cities.bridges")} value={city.bridgeCount ?? 0} icon={<BridgeIcon size={16} />} color={city.bridgeCount ? "accent" : "slate"} />
            <StatCard label={t("cities.river")} value={city.hasRiver ? t("cities.yes") : t("cities.no")} icon={<RiverIcon size={16} />} color={city.hasRiver ? "accent" : "slate"} />
            <StatCard label="OSM ID" value={city.osmId ?? "-"} icon={<BuildingIcon size={16} />} color="slate" />
          </div>

          {city.cityAffinityTags && city.cityAffinityTags.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-bold text-slate-700">{t("city.characteristics")}</h3>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {city.cityAffinityTags.map((tag) => (
                  <span key={tag} className="badge-blue">{tag}</span>
                ))}
              </div>
            </div>
          )}

          <div className="mt-6 card p-4">
            <h3 className="text-sm font-bold text-slate-700">{t("city.coordinates")}</h3>
            <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-slate-500">{t("city.centroid")}</span>
                <span className="ml-2 font-mono font-semibold">
                  {city.centroid.lat.toFixed(4)}, {city.centroid.lon.toFixed(4)}
                </span>
              </div>
              <div>
                <span className="text-slate-500">{t("city.bbox")}</span>
                <span className="ml-2 font-mono text-xs font-semibold">
                  {city.bbox[0].toFixed(2)}, {city.bbox[1].toFixed(2)} → {city.bbox[2].toFixed(2)}, {city.bbox[3].toFixed(2)}
                </span>
              </div>
            </div>
          </div>

          <Link href={`/studio?city=${city.id}`} className="btn-primary mt-6 w-full py-3 text-base shadow-md">
            <SparklesIcon size={18} />
            {t("city.generate")} {city.name}
            <ArrowRightIcon size={16} />
          </Link>
        </div>

        <div className="h-96 overflow-hidden rounded-2xl border border-slate-200 shadow-md lg:h-full">
          <RouteMap key={city.id} geojson={boundaryGeojson} center={[city.centroid.lat, city.centroid.lon]} showLayers={false} />
        </div>
      </div>


      {allArtworks.length > 0 && (
        <div className="mt-10">
          <h2 className="section-title">{t("city.allArtworks")} {city.name}</h2>
          <p className="mt-1 text-sm text-slate-500">{allArtworks.length} {t("city.shapesInCatalog")}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {allArtworks.map((a) => (
              <Link key={a.id} href={`/gallery/${a.id}`} className="card card-hover flex items-center gap-2.5 px-3 py-2">
                <img src={a.previewSvgUrl} alt={a.name} className="h-8 w-8 rounded-lg bg-slate-50 p-1" />
                <div>
                  <div className="text-sm font-semibold text-slate-900">{tShape(a.id, a.name)}</div>
                  <div className="text-xs text-slate-500">{a.recommendedMinKm}-{a.recommendedMaxKm} km</div>
                </div>
                <CategoryBadge category={a.category} />
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
