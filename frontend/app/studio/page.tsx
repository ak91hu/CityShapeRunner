import { Suspense } from "react";
import Studio from "@/components/Studio";

export default function StudioPage() {
  return (
    <Suspense fallback={<div className="p-8">Loading studio…</div>}>
      <Studio />
    </Suspense>
  );
}
