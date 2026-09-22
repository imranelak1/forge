import { Suspense } from "react";
import { OverviewPage } from "@/features/analytics/overview-page";
import { AnalyticsLoading } from "@/features/analytics/analytics-ui";

export default function Page() {
  return (
    <Suspense fallback={<AnalyticsLoading />}>
      <OverviewPage />
    </Suspense>
  );
}
