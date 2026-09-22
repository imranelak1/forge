"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useAuth } from "./auth-provider";
import { CreateOrganization } from "@/features/organizations/create-organization";

export function AuthBoundary({ children }: { children: React.ReactNode }) {
  const { identity, loading, error, reload } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  useEffect(() => {
    if (identity === null && !loading && !error)
      router.replace(`/login?returnTo=${encodeURIComponent(pathname)}`);
  }, [identity, loading, error, pathname, router]);
  if (error)
    return (
      <section className="account-section">
        <h1>Could not load your workspace</h1>
        <p role="alert">{error.message}</p>
        <Button variant="outline" onClick={() => void reload()}>
          Try again
        </Button>
        <Link className="text-link" href="/system">
          Check system status
        </Link>
      </section>
    );
  if (!identity)
    return (
      <>
        <p role="status">{loading ? "Checking your session..." : "Opening sign in..."}</p>
        <noscript>
          <p>
            JavaScript is required for secure workspace access. Enable it, then{" "}
            <Link className="text-link" href="/login">
              Sign in
            </Link>
            .
          </p>
        </noscript>
      </>
    );
  if (!identity.organizations.length && pathname !== "/app/account")
    return <CreateOrganization onboarding />;
  return <>{children}</>;
}
