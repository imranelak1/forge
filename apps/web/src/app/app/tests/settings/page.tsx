import { Suspense } from "react";
import { TestSettingsPage } from "@/features/test-intelligence/settings-page";
import { AnalyticsLoading } from "@/features/analytics/analytics-ui";
export default function Page() {
  return (
    <Suspense fallback={<AnalyticsLoading />}>
      <TestSettingsPage />
    </Suspense>
  );
}
