import { Suspense } from "react";
import Screener from "@/components/Screener";
import { CardSkeletons } from "@/components/States";

export default function Page() {
  return (
    <Suspense fallback={<div className="p-4"><CardSkeletons /></div>}>
      <Screener />
    </Suspense>
  );
}
