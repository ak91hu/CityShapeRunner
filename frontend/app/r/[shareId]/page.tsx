"use client";

import { use, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ShareView } from "@/lib/types";
import { LoadingSpinner } from "@/components/UI";
import { useI18n } from "@/lib/i18n";
import {
  DownloadIcon,
  RouteIcon,
  MapPinIcon,
  ActivityIcon,
  RulerIcon,
  SparklesIcon,
  AlertIcon,
} from "@/components/Icons";

const RouteMap = dynamic(() => import("@/components/RouteMap"), { ssr: false });

export default function SharePage({ params }: { params: Promise<{ shareId: string }> }) {
  const { t, tShape } = useI18n();
  const { shareId } = use(params);
  const [data, setData] = useState<ShareView | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.getShare(shareId).then(setData).catch((e) => setErr((e as Error).message));
  }, [shareId]);

  if (err) return (
    <div className="mx-auto max-w-2xl px-4 py-16 text-center">
      <AlertIcon size={48} className="mx-auto text-rose-400" />
      <h1 className="mt-4 text-xl font-bold text-rose-700">{t("share.notFound")}</h1>
      <p className="mt-2 text-sm text-slate-500">{err}</p>
      <Link href="/studio" className="btn-primary mt-6 px-6 py-3">
        <SparklesIcon size={18} /> {t("share.openStudio")}
      </Link>
    </div>
  );
  if (!data) return <LoadingSpinner label={t("gallery.loading")} />;

  return (
    <div className="flex flex-col">
      <div className="bg-gradient-to-br from-brand-600 via-brand-700 to-accent-600 text-white">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/20 backdrop-blur">
                <RouteIcon size={28} />
              </div>
              <div>
                <h1 className="text-2xl font-extrabold tracking-tight">{tShape("", data.artworkName)}</h1>
                <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-white/80">
                  <span className="flex items-center gap-1">
                    <MapPinIcon size={14} /> {data.cityName}
                  </span>
                  <span className="flex items-center gap-1 capitalize">
                    <ActivityIcon size={14} /> {t("studio." + data.activity)}
                  </span>
                  <span className="flex items-center gap-1">
                    <RulerIcon size={14} /> {data.distanceKm} km
                  </span>
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <a className="btn bg-white/20 px-4 py-2.5 text-sm backdrop-blur hover:bg-white/30 text-white" href={`/api/routes/${data.routeId}/export/gpx?mode=continuous`} download="route.gpx">
                <DownloadIcon size={16} /> GPX
              </a>
            </div>
          </div>
        </div>
      </div>

      <div className="h-[60vh] w-full overflow-hidden">
        <RouteMap key={shareId} geojson={data.geojson} showLayers />
      </div>

      <div className="bg-slate-50">
        <div className="mx-auto max-w-7xl px-4 py-8 text-center sm:px-6">
          <h2 className="text-xl font-bold text-slate-900">{t("share.createOwn")}</h2>
          <p className="mt-2 text-sm text-slate-600">{t("share.createOwnDesc")}</p>
          <Link href="/studio" className="btn-primary mt-4 px-6 py-3">
            <SparklesIcon size={18} />
            {t("share.openStudio")}
          </Link>
        </div>
      </div>
    </div>
  );
}
