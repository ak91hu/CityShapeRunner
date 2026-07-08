import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { I18nProvider } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "CityShapeRunner — GPS art útvonalak bármely városból",
  description:
    "Generálj GPS art útvonalakat bármelyik városból. Válassz egy várost, aktivitást és távolságot, majd tölts le egy GPX fájlt az órádhoz.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="hu">
      <body className="flex min-h-screen flex-col">
        <I18nProvider>
          <Navbar />
          <div className="flex-1">{children}</div>
          <Footer />
        </I18nProvider>
      </body>
    </html>
  );
}
