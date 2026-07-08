"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export default function Footer() {
  const { t } = useI18n();
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900">CityShapeRunner</h3>
            <p className="mt-2 text-sm text-slate-500">{t("footer.desc")}</p>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-slate-700">{t("footer.explore")}</h4>
            <ul className="mt-2 space-y-1.5 text-sm">
              <li><Link href="/studio" className="text-slate-500 hover:text-brand-600">{t("nav.studio")}</Link></li>
              <li><Link href="/gallery" className="text-slate-500 hover:text-brand-600">{t("nav.gallery")}</Link></li>
              <li><Link href="/cities" className="text-slate-500 hover:text-brand-600">{t("nav.cities")}</Link></li>
              <li><a href="http://localhost:8000/documentation/" target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-brand-600">{t("footer.docs")}</a></li>
              <li><a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-brand-600">{t("footer.apiDocs")}</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-slate-700">{t("footer.about")}</h4>
            <ul className="mt-2 space-y-1.5 text-sm text-slate-500">
              <li>{t("footer.stats")}</li>
              <li>{t("footer.stats2")}</li>
              <li>{t("footer.stats3")}</li>
              <li>{t("footer.stats4")}</li>
            </ul>
          </div>
        </div>
        <div className="mt-8 border-t border-slate-100 pt-4 text-center text-xs text-slate-400">
          {t("footer.copy")}
        </div>
      </div>
    </footer>
  );
}
