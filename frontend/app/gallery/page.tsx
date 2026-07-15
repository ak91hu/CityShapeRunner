"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ArtworkSummary } from "@/lib/types";
import { CATEGORIES, COMPLEXITIES } from "@/lib/types";
import { CategoryBadge, ComplexityBadge, EmptyState, LoadingSpinner } from "@/components/UI";
import { useI18n } from "@/lib/i18n";
import { GridIcon, SearchIcon, SparklesIcon, RulerIcon } from "@/components/Icons";

const CATEGORY_COLORS: Record<string, string> = {
  basic: "from-rose-500 to-pink-500",
  animals: "from-amber-500 to-orange-500",
  sports: "from-accent-500 to-teal-500",
  nature: "from-green-500 to-emerald-500",
  city: "from-brand-500 to-violet-500",
  funny: "from-fuchsia-500 to-pink-500",
  symbols: "from-cyan-500 to-blue-500",
};

export default function GalleryPage() {
  const { t, tShape } = useI18n();
  const [artworks, setArtworks] = useState<ArtworkSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [complexity, setComplexity] = useState<string | null>(null);

  useEffect(() => {
    api.listArtworks().then(setArtworks).finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    return artworks.filter((a) => {
      if (search && !a.name.toLowerCase().includes(search.toLowerCase())) return false;
      if (category && a.category !== category) return false;
      if (complexity && a.complexity !== complexity) return false;
      return true;
    });
  }, [artworks, search, category, complexity]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="mb-8">
        <h1 className="flex items-center gap-2 text-3xl font-extrabold tracking-tight">
          <GridIcon size={28} className="text-brand-600" />
          {t("gallery.title")}
        </h1>
        <p className="mt-2 text-slate-600">
          {artworks.length} {t("gallery.desc")}
        </p>
      </div>

      <div className="mb-6 space-y-4">
        <div className="relative max-w-md">
          <SearchIcon size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            className="input pl-11"
            placeholder={t("gallery.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-all ${
              !category ? "bg-brand-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:border-brand-300"
            }`}
            onClick={() => setCategory(null)}
          >
            {t("gallery.all")}
          </button>
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-all ${
                category === cat ? "bg-brand-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:border-brand-300"
              }`}
              onClick={() => setCategory(category === cat ? null : cat)}
            >
              {t("cat." + cat) || cat}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-slate-500">{t("gallery.difficulty")}</span>
          {COMPLEXITIES.map((c) => (
            <button
              key={c}
              className={`rounded-lg px-3 py-1 text-xs font-medium transition-all ${
                complexity === c ? "bg-slate-800 text-white" : "bg-white border border-slate-200 text-slate-600 hover:border-slate-400"
              }`}
              onClick={() => setComplexity(complexity === c ? null : c)}
            >
              {t("cx." + c) || c}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <LoadingSpinner label={t("gallery.loading")} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<GridIcon size={48} />}
          title={t("gallery.empty")}
          description={t("gallery.emptyDesc")}
        />
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {filtered.map((a) => (
            <Link
              key={a.id}
              href={`/gallery/${a.id}`}
              className="card card-hover group flex flex-col overflow-hidden"
            >
              <div
                className={`flex h-32 items-center justify-center bg-gradient-to-br ${CATEGORY_COLORS[a.category] || "from-slate-400 to-slate-500"} p-4`}
              >
                <img
                  src={a.previewSvgUrl}
                  alt={a.name}
                  className="h-full w-full invert transition-transform group-hover:scale-110"
                />
              </div>
              <div className="p-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-slate-900">{tShape(a.id, a.name)}</h3>
                  {a.isCitySignature && <SparklesIcon size={14} className="text-amber-500" />}
                </div>
                <div className="mt-1.5 flex items-center gap-1.5">
                  <CategoryBadge category={a.category} />
                  <ComplexityBadge complexity={a.complexity} />
                </div>
                <div className="mt-2 flex items-center gap-1 text-xs text-slate-500">
                  <RulerIcon size={12} />
                  {a.recommendedMinKm}-{a.recommendedMaxKm} km
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
