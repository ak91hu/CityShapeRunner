"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ArtworkDetail } from "@/lib/types";
import { CategoryBadge, ComplexityBadge, LoadingSpinner, StatCard } from "@/components/UI";
import { useI18n } from "@/lib/i18n";
import {
  ArrowRightIcon,
  SparklesIcon,
  RulerIcon,
  InfoIcon,
  MapPinIcon,
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

export default function ArtworkDetailPage({ params }: { params: Promise<{ artworkId: string }> }) {
  const { t } = useI18n();
  const { artworkId } = use(params);
  const [art, setArt] = useState<ArtworkDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.getArtwork(artworkId).then(setArt).catch((e) => setErr((e as Error).message));
  }, [artworkId]);

  if (err) return <div className="p-8 text-rose-600">Error: {err}</div>;
  if (!art) return <LoadingSpinner label={t("gallery.loading")} />;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <Link href="/gallery" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-brand-600">
        {t("artwork.back")}
      </Link>

      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
        <div className={`flex aspect-square items-center justify-center rounded-3xl bg-gradient-to-br ${CATEGORY_COLORS[art.category] || "from-slate-400 to-slate-500"} p-12 shadow-xl`}>
          <img src={art.previewSvgUrl} alt={art.name} className="h-full w-full invert" />
        </div>

        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-extrabold tracking-tight">{art.name}</h1>
            {art.isCitySignature && (
              <span className="badge-amber">
                <SparklesIcon size={12} /> {t("artwork.citySignature")}
              </span>
            )}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <CategoryBadge category={art.category} />
            <ComplexityBadge complexity={art.complexity} />
            {art.symmetric && <span className="badge-blue">{t("artwork.symmetric")}</span>}
            <span className={`badge ${art.closedPath ? "badge-green" : "badge-slate"}`}>
              {art.closedPath ? t("artwork.closedPath") : t("artwork.openPath")}
            </span>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-3">
            <StatCard label={t("artwork.recDistance")} value={`${art.recommendedMinKm}–${art.recommendedMaxKm} km`} icon={<RulerIcon size={16} />} />
            <StatCard label={t("artwork.sampleCount")} value={art.defaultSampleCount} icon={<InfoIcon size={16} />} color="slate" />
            <StatCard label={t("artwork.aspectRatio")} value={art.aspectRatio.toFixed(1)} icon={<InfoIcon size={16} />} color="slate" />
            <StatCard label={t("artwork.normLength")} value={art.normalizedLength.toFixed(2)} icon={<InfoIcon size={16} />} color="slate" />
          </div>

          {art.tags.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-bold text-slate-700">{t("artwork.tags")}</h3>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {art.tags.map((tag) => (
                  <span key={tag} className="badge-slate">#{tag}</span>
                ))}
              </div>
            </div>
          )}

          {art.cityAffinityTags.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-bold text-slate-700">{t("artwork.affinity")}</h3>
              <p className="mt-1 text-xs text-slate-500">{t("artwork.affinityDesc")}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {art.cityAffinityTags.map((tag) => (
                  <span key={tag} className="badge-blue">
                    <MapPinIcon size={10} /> {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          <Link href="/studio" className="btn-primary mt-8 w-full py-3 text-base shadow-md">
            <SparklesIcon size={18} />
            {t("artwork.generate")}
            <ArrowRightIcon size={16} />
          </Link>
        </div>
      </div>

      <div className="mt-10 card p-6">
        <h2 className="text-lg font-bold">{t("artwork.howTitle")}</h2>
        <ul className="mt-3 space-y-2.5 text-sm text-slate-600">
          {[t("artwork.step1"), t("artwork.step2"), t("artwork.step3"), t("artwork.step4"), t("artwork.step5"), t("artwork.step6")].map((step, i) => (
            <li key={i} className="flex items-start gap-2.5">
              <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-600 text-xs font-bold">
                {i + 1}
              </div>
              {step}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
