import type { Metadata } from "next";
import { Suspense } from "react";
import { ForgotPasswordPage } from "@/features/auth/auth-pages";

export const metadata: Metadata = { title: "Reset your password", referrer: "no-referrer" };

export default function Page() {
  return (
    <Suspense
      fallback={
        <p className="auth-loading" role="status">
          Loading...
        </p>
      }
    >
      <ForgotPasswordPage />
    </Suspense>
  );
}
