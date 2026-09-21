import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <section className="not-found">
      <h1>Page not found</h1>
      <p>This page does not exist in the current Forge build.</p>
      <Button asChild variant="outline">
        <Link href="/">Return to overview</Link>
      </Button>
    </section>
  );
}
