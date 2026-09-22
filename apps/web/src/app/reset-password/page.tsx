import type { Metadata } from "next";
import { Suspense } from "react";
import { ResetPasswordPage } from "@/features/auth/auth-pages";

export const metadata: Metadata = { title: "Choose a new password", referrer: "no-referrer" };

export default function Page() {
  return (
    <Suspense
      fallback={
        <p className="auth-loading" role="status">
          Loading...
        </p>
      }
    >
      <ResetPasswordPage />
    </Suspense>
  );
}
