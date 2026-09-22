import { Suspense } from "react";
import { EnvironmentPage } from "@/features/delivery/environment-page";
import { AnalyticsLoading } from "@/features/analytics/analytics-ui";
export default function Page() {
  return (
    <Suspense fallback={<AnalyticsLoading />}>
      <EnvironmentPage />
    </Suspense>
  );
}
