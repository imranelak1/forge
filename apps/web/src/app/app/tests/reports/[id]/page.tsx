import { Suspense } from "react";
import { ReportPage } from "@/features/test-intelligence/report-page";
import { AnalyticsLoading } from "@/features/analytics/analytics-ui";
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense fallback={<AnalyticsLoading />}>
      <ReportPage id={id} />
    </Suspense>
  );
}
