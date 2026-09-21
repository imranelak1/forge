"use client";

import { Button } from "@/components/ui/button";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <section className="not-found">
      <h1>This page could not load</h1>
      <p>Retry the request. If the problem continues, inspect the frontend logs.</p>
      <Button variant="outline" onClick={reset}>
        Try again
      </Button>
    </section>
  );
}
