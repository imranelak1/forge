import { Suspense } from "react";
import { TestsPage } from "@/features/test-intelligence/tests-page";
import { AnalyticsLoading } from "@/features/analytics/analytics-ui";
export default function Page() {
  return (
    <Suspense fallback={<AnalyticsLoading />}>
      <TestsPage />
    </Suspense>
  );
}
