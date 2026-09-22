import { Suspense } from "react";
import { DeliveryPage } from "@/features/delivery/delivery-pages";
import { AnalyticsLoading } from "@/features/analytics/analytics-ui";
export default function Page() {
  return (
    <Suspense fallback={<AnalyticsLoading />}>
      <DeliveryPage kind="ci" />
    </Suspense>
  );
}
