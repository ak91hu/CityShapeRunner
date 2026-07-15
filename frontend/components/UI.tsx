import type { ReactNode } from "react";
import { useI18n } from "@/lib/i18n";

export function ScoreBar({
  label,
  value,
  color = "brand",
  showValue = true,
}: {
  label: string;
  value: number;
  color?: "brand" | "accent" | "amber";
  showValue?: boolean;
}) {
  const pct = Math.round(value * 100);
  const colorMap = {
    brand: "bg-brand-500",
    accent: "bg-accent-500",
    amber: "bg-amber-500",
  };
  return (
    <div className="flex items-center gap-2">
      <span className="w-20 shrink-0 text-xs font-medium text-slate-500">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full transition-all duration-500 ${colorMap[color]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showValue && <span className="w-9 shrink-0 text-right text-xs font-mono font-semibold text-slate-700">{pct}%</span>}
    </div>
  );
}

export function ScoreRing({ value, size = 64, label }: { value: number; size?: number; label?: string }) {
  const pct = Math.round(value * 100);
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - value);
  const color = pct >= 80 ? "#10b981" : pct >= 60 ? "#6366f1" : pct >= 40 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e2e8f0" strokeWidth={4} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={4}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-700"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-sm font-bold" style={{ color }}>{pct}%</span>
        {label && <span className="text-[8px] text-slate-400">{label}</span>}
      </div>
    </div>
  );
}

export function CategoryBadge({ category }: { category: string }) {
  const { t } = useI18n();
  const map: Record<string, string> = {
    basic: "badge-blue",
    animals: "badge-amber",
    sports: "badge-green",
    nature: "badge bg-green-100 text-green-700",
    city: "badge bg-purple-100 text-purple-700",
    funny: "badge bg-pink-100 text-pink-700",
    symbols: "badge bg-cyan-100 text-cyan-700",
  };
  const cls = map[category] || "badge-slate";
  return <span className={cls}>{t("cat." + category) || category}</span>;
}

export function ComplexityBadge({ complexity }: { complexity: string }) {
  const { t } = useI18n();
  const map: Record<string, string> = {
    easy: "badge-green",
    medium: "badge-amber",
    hard: "badge-rose",
  };
  return <span className={map[complexity] || "badge-slate"}>{t("cx." + complexity) || complexity}</span>;
}

export function WarningList({ warnings }: { warnings: string[] }) {
  const { t } = useI18n();
  if (warnings.length === 0) return null;
  const friendly: Record<string, string> = {
    distance_outside_preferred_tolerance: lang_eq(t, "Távolság a megengedett tartományon kívül", "Distance outside preferred tolerance"),
    contains_private_access_penalty: lang_eq(t, "Az útvonal privát utakat is érint", "Route uses some private-access roads"),
    contains_stairs: lang_eq(t, "Lépcsőt tartalmaz az útvonal", "Route includes stairs"),
    high_detour_ratio: lang_eq(t, "Nagyobb kerülő, mint optimális lenne", "High detour ratio"),
    low_shape_similarity: lang_eq(t, "Az alak kevésbé hasonlít a motívumra", "Lower shape similarity"),
    route_crosses_city_boundary: lang_eq(t, "Az útvonal átlépi a városhatárt", "Route crosses city boundary"),
    connect_the_dots_recommended: lang_eq(t, "Pontközi mód javasolt", "Connect-the-dots mode recommended"),
    route_disconnected: lang_eq(t, "Az útvonal nem folytonos", "Route is disconnected"),
  };
  return (
    <div className="space-y-1">
      {warnings.map((w) => (
        <div key={w} className="flex items-start gap-1.5 text-xs text-amber-700">
          <span className="mt-0.5">!</span>
          <span>{friendly[w] || w}</span>
        </div>
      ))}
    </div>
  );
}

function lang_eq(t: (k: string) => string, hu: string, en: string): string {
  return t("nav.home") === "Főoldal" ? hu : en;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
      {icon && <div className="mb-4 text-slate-300">{icon}</div>}
      <h3 className="text-base font-semibold text-slate-700">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-400">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function LoadingSpinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16">
      <div className="h-8 w-8 animate-spin rounded-full border-3 border-brand-200 border-t-brand-600" />
      {label && <p className="text-sm text-slate-500">{label}</p>}
    </div>
  );
}

export function StatCard({
  label,
  value,
  icon,
  color = "brand",
}: {
  label: string;
  value: string | number;
  icon?: ReactNode;
  color?: "brand" | "accent" | "amber" | "slate";
}) {
  const colorMap = {
    brand: "bg-brand-50 text-brand-600",
    accent: "bg-accent-50 text-accent-600",
    amber: "bg-amber-50 text-amber-600",
    slate: "bg-slate-100 text-slate-600",
  };
  return (
    <div className="card p-3">
      <div className="flex items-center gap-2">
        {icon && <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${colorMap[color]}`}>{icon}</div>}
        <div>
          <div className="text-xs font-medium text-slate-500">{label}</div>
          <div className="text-sm font-bold text-slate-900">{value}</div>
        </div>
      </div>
    </div>
  );
}
