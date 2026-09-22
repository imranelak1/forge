import type { Metadata } from "next";
import { Suspense } from "react";
import { CredentialsPage } from "@/features/auth/auth-pages";

export const metadata: Metadata = { title: "Create account", referrer: "no-referrer" };

export default function Page() {
  return (
    <Suspense
      fallback={
        <p className="auth-loading" role="status">
          Loading...
        </p>
      }
    >
      <CredentialsPage mode="register" />
    </Suspense>
  );
}
