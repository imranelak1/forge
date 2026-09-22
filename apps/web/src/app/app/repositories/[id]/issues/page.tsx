import { Suspense } from "react";
import { RepositoryIssues } from "@/features/analytics/history-pages";
import { AnalyticsLoading } from "@/features/analytics/analytics-ui";
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense fallback={<AnalyticsLoading />}>
      <RepositoryIssues id={id} />
    </Suspense>
  );
}
