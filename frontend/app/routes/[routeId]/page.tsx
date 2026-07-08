"use client";

import { use, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { api } from "@/lib/api";
import type { RouteDetail, ShareView } from "@/lib/types";
import { LoadingSpinner, ScoreRing, ScoreBar, WarningList } from "@/components/UI";
import { useI18n } from "@/lib/i18n";
import {
  DownloadIcon,
  ShareIcon,
  RouteIcon,
  CopyIcon,
  CheckIcon,
  AlertIcon,
  RulerIcon,
  ActivityIcon,
  SparklesIcon,
  ArrowRightIcon,
} from "@/components/Icons";

const RouteMap = dynamic(() => import("@/components/RouteMap"), { ssr: false });

export default function RouteViewPage({ params }: { params: Promise<{ routeId: string }> }) {
  const { t } = useI18n();
  const { routeId } = use(params);
  const [route, setRoute] = useState<RouteDetail | null>(null);
  const [share, setShare] = useState<ShareView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [shareUrl, setShareUrl] = useState<string | null>(null);

  useEffect(() => {
    api.getRoute(routeId).then((r) => {
      setRoute(r);
      api.createShare(routeId).then((s) => {
        setShareUrl(`${window.location.origin}/r/${s.shareId}`);
        return api.getShare(s.shareId);
      }).then(setShare).catch(() => {});
    }).catch((e) => setErr((e as Error).message));
  }, [routeId]);

  const copyShare = () => {
    if (!shareUrl) return;
    navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (err) return (
    <div className="mx-auto max-w-2xl px-4 py-16 text-center">
      <AlertIcon size={48} className="mx-auto text-rose-400" />
      <h1 className="mt-4 text-xl font-bold text-rose-700">{t("route.notFound")}</h1>
      <p className="mt-2 text-sm text-slate-500">{err}</p>
      <Link href="/studio" className="btn-primary mt-6 px-6 py-3">
        <SparklesIcon size={18} /> {t("route.openStudio")}
      </Link>
    </div>
  );
  if (!route) return <LoadingSpinner label={t("gallery.loading")} />;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-accent-500 text-white shadow-lg">
            <RouteIcon size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">{route.artworkName}</h1>
            <p className="text-sm text-slate-500 capitalize">
              {t("studio." + route.activity)} · {route.distanceKm} km
              {route.elevationGainM != null && ` · ${route.elevationGainM}m`}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <a className="btn-primary px-4 py-2.5 text-sm" href={api.gpxUrl(route.routeId, "continuous")} download>
            <DownloadIcon size={16} /> GPX
          </a>
          <a className="btn-secondary px-4 py-2.5 text-sm" href={api.gpxUrl(route.routeId, "connect_the_dots")} download>
            <DownloadIcon size={14} /> {t("route.dots")}
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="h-96 overflow-hidden rounded-2xl border border-slate-200 shadow-md lg:h-[500px]">
            {share ? (
              <RouteMap key={route.routeId} geojson={share.geojson} showLayers />
            ) : (
              <LoadingSpinner label={t("gallery.loading")} />
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="card p-5">
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-500">{t("route.scores")}</h2>
            <div className="mt-4 flex items-center gap-4">
              <ScoreRing value={route.scores.fitScore} size={72} label={t("ui.fitScore")} />
              <div className="flex-1 space-y-2">
                <ScoreBar label={t("ui.shape")} value={route.scores.shapeSimilarityScore} color="accent" />
                <ScoreBar label={t("ui.distance")} value={route.scores.distanceAccuracyScore} color="brand" />
                <ScoreBar label={t("ui.road")} value={route.scores.roadQualityScore} color="brand" />
                <ScoreBar label={t("ui.continuity")} value={route.scores.continuityScore} color="accent" />
              </div>
            </div>
          </div>

          <div className="card p-5">
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-500">{t("route.details")}</h2>
            <div className="mt-3 space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 text-slate-500"><RulerIcon size={16} /> {t("route.distance")}</span>
                <span className="font-mono font-bold">{route.distanceKm} km</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 text-slate-500"><ActivityIcon size={16} /> {t("route.activity")}</span>
                <span className="font-semibold capitalize">{t("studio." + route.activity)}</span>
              </div>
              {route.elevationGainM != null && (
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2 text-slate-500"><AlertIcon size={16} /> {t("route.elevation")}</span>
                  <span className="font-mono font-bold">{route.elevationGainM} m</span>
                </div>
              )}
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 text-slate-500"><CheckIcon size={16} /> {t("route.visibility")}</span>
                <span className="font-semibold capitalize">{route.visibility}</span>
              </div>
            </div>
          </div>

          {route.warnings.length > 0 && (
            <div className="card border-amber-200 bg-amber-50 p-5">
              <h2 className="flex items-center gap-1.5 text-sm font-bold text-amber-800">
                <AlertIcon size={16} /> {t("route.warnings")}
              </h2>
              <div className="mt-2">
                <WarningList warnings={route.warnings} />
              </div>
            </div>
          )}

          <div className="card p-5">
            <h2 className="flex items-center gap-1.5 text-sm font-bold uppercase tracking-wide text-slate-500">
              <ShareIcon size={16} /> {t("route.share")}
            </h2>
            {shareUrl ? (
              <div className="mt-3 space-y-2">
                <div className="flex items-center gap-2 rounded-lg bg-slate-50 p-2">
                  <input className="flex-1 bg-transparent text-sm text-slate-700 outline-none" value={shareUrl} readOnly />
                  <button className="btn-primary px-3 py-1.5 text-xs" onClick={copyShare}>
                    {copied ? <><CheckIcon size={14} /> {t("studio.copied")}</> : <><CopyIcon size={14} /> {t("studio.copy")}</>}
                  </button>
                </div>
                <Link href={shareUrl.replace(window.location.origin, "")} className="btn-secondary w-full py-2 text-sm">
                  {t("studio.open")} <ArrowRightIcon size={14} />
                </Link>
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-400">...</p>
            )}
          </div>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="card p-5">
          <div className="flex items-center gap-2">
            <DownloadIcon size={20} className="text-brand-600" />
            <h3 className="font-bold">{t("route.continuous")}</h3>
          </div>
          <p className="mt-2 text-sm text-slate-600">{t("route.continuousDesc")}</p>
          <a className="btn-primary mt-3 w-full py-2.5 text-sm" href={api.gpxUrl(route.routeId, "continuous")} download>
            <DownloadIcon size={16} /> {t("route.downloadContinuous")}
          </a>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-2">
            <DownloadIcon size={20} className="text-slate-600" />
            <h3 className="font-bold">{t("route.dots")}</h3>
          </div>
          <p className="mt-2 text-sm text-slate-600">{t("route.dotsDesc")}</p>
          <a className="btn-secondary mt-3 w-full py-2.5 text-sm" href={api.gpxUrl(route.routeId, "connect_the_dots")} download>
            <DownloadIcon size={14} /> {t("route.downloadDots")}
          </a>
        </div>
      </div>
    </div>
  );
}
