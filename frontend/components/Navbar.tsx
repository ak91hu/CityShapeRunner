"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { RouteIcon, GridIcon, BuildingIcon, SparklesIcon } from "./Icons";
import { useI18n } from "@/lib/i18n";

export default function Navbar() {
  const pathname = usePathname();
  const { lang, setLang, t } = useI18n();

  const LINKS = [
    { href: "/", label: t("nav.home"), icon: RouteIcon },
    { href: "/studio", label: t("nav.studio"), icon: SparklesIcon },
    { href: "/gallery", label: t("nav.gallery"), icon: GridIcon },
    { href: "/cities", label: t("nav.cities"), icon: BuildingIcon },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/80 backdrop-blur-md">
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-600 to-accent-500 text-white shadow-md transition-transform group-hover:scale-105">
            <RouteIcon size={20} />
          </div>
          <div className="flex flex-col leading-none">
            <span className="text-base font-bold tracking-tight">CityShapeRunner</span>
            <span className="text-[10px] font-medium text-slate-400">GPS Art Generator</span>
          </div>
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {LINKS.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                <Icon size={16} />
                {label}
              </Link>
            );
          })}
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center rounded-lg border border-slate-200 bg-white p-0.5">
            <button
              className={`rounded-md px-2 py-1 text-xs font-bold transition-colors ${
                lang === "hu" ? "bg-brand-600 text-white" : "text-slate-500 hover:text-slate-700"
              }`}
              onClick={() => setLang("hu")}
            >
              HU
            </button>
            <button
              className={`rounded-md px-2 py-1 text-xs font-bold transition-colors ${
                lang === "en" ? "bg-brand-600 text-white" : "text-slate-500 hover:text-slate-700"
              }`}
              onClick={() => setLang("en")}
            >
              EN
            </button>
          </div>
        </div>
      </nav>

      <div className="flex items-center gap-1 overflow-x-auto px-4 pb-2 md:hidden">
        {LINKS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                active ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </div>
    </header>
  );
}
