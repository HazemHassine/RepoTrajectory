import type { Metadata } from "next";

import { OverviewDashboard } from "@/components/overview-dashboard";
import { api } from "@/lib/api";
import { productApi, type SystemOverview } from "@/lib/product-api";

export const metadata: Metadata = {
  title: "System & Data Overview",
  description:
    "Comprehensive developer reference of RepoTrajectory pages, data origins, storage volume, and extracted telemetry metrics.",
};

export default async function OverviewPage() {
  let overviewData: SystemOverview | null = null;
  let healthData: any = null;
  let facetsData: any = null;

  const [overviewRes, healthRes, facetsRes] = await Promise.allSettled([
    productApi.overview(),
    api.v2.health(),
    api.v2.facets(),
  ]);

  if (overviewRes.status === "fulfilled") {
    overviewData = overviewRes.value;
  }
  if (healthRes.status === "fulfilled") {
    healthData = healthRes.value;
  }
  if (facetsRes.status === "fulfilled") {
    facetsData = facetsRes.value;
  }

  return (
    <OverviewDashboard
      overviewData={overviewData}
      healthData={healthData}
      facetsData={facetsData}
    />
  );
}
