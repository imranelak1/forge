import type { Metadata } from "next";
import { Suspense } from "react";
import { IntegrationsPage } from "@/features/github/integrations-page";
export const metadata: Metadata = { title: "Integrations", referrer: "no-referrer" };
export default function Page() {
  return (
    <Suspense fallback={<p role="status">Loading integrations...</p>}>
      <IntegrationsPage />
    </Suspense>
  );
}
