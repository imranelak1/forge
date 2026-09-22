import type { Metadata } from "next";
import { Suspense } from "react";
import { VerifyEmailPage } from "@/features/auth/auth-pages";

export const metadata: Metadata = { title: "Verify email", referrer: "no-referrer" };

export default function Page() {
  return (
    <Suspense
      fallback={
        <p className="auth-loading" role="status">
          Loading...
        </p>
      }
    >
      <VerifyEmailPage />
    </Suspense>
  );
}
