import { Suspense } from "react";
import { HistoryPage } from "@/features/analytics/history-pages";
import { AnalyticsLoading } from "@/features/analytics/analytics-ui";
export default function Page() {
  return (
    <Suspense fallback={<AnalyticsLoading />}>
      <HistoryPage kind="commits" />
    </Suspense>
  );
}
