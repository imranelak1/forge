import type { Metadata } from "next";
import { LandingPage } from "@/features/landing/landing-page";
import "@/features/landing/landing.css";

export const metadata: Metadata = {
  title: "Forge — Every change. Every signal. Connected.",
  description:
    "Explore Forge: engineering intelligence that connects code changes, CI, tests, deployments and production errors.",
};

export default function HomePage() {
  return <LandingPage />;
}
