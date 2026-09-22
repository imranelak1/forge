import type { Metadata } from "next";
import { Suspense } from "react";
import { InvitePage } from "@/features/auth/auth-pages";

export const metadata: Metadata = { title: "Join your team", referrer: "no-referrer" };

export default function Page() {
  return (
    <Suspense
      fallback={
        <p className="auth-loading" role="status">
          Loading...
        </p>
      }
    >
      <InvitePage />
    </Suspense>
  );
}
