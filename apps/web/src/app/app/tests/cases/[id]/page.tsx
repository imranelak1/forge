import { Suspense } from "react";
import { TestHistoryPage } from "@/features/test-intelligence/history-page";
import { AnalyticsLoading } from "@/features/analytics/analytics-ui";
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense fallback={<AnalyticsLoading />}>
      <TestHistoryPage id={id} />
    </Suspense>
  );
}
