"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

export default function HealthBadge() {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    let active = true;
    const check = () =>
      api.health().then((h) => active && setHealth(h)).catch(() => active && setHealth(null));
    check();
    const id = setInterval(check, 30000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  if (!health) {
    return (
      <span className="badge bg-slate-100 text-slate-500" title="API unreachable">
        <span className="inline-block h-2 w-2 rounded-full bg-slate-400" />
        API offline
      </span>
    );
  }

  const ok = health.status === "ok";
  return (
    <span
      className={ok ? "badge-green" : "badge-amber"}
      title={`v${health.version} · DB: ${health.db ? "connected" : "in-memory"}`}
    >
      <span
        className={`inline-block h-2 w-2 rounded-full ${ok ? "bg-accent-500 animate-pulse" : "bg-amber-500"}`}
      />
      {ok ? "Online" : "Degraded"}
      {health.db && <span className="text-accent-600">·DB</span>}
    </span>
  );
}
