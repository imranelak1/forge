"use client";

import { useEffect, useRef, useState } from "react";
import { Play } from "lucide-react";

/* Brand SVGs retain their source geometry; source URLs are recorded in public/integrations/SOURCES.md. */
export const integrations = [
  {
    id: "github",
    name: "GitHub",
    short: "Code",
    detail: "Pull requests, commits and deployments. The starting point for a traceable delivery.",
  },
  {
    id: "githubactions",
    name: "GitHub Actions",
    short: "Build",
    detail:
      "Workflow runs, build outcomes and durations, linked back to the change that triggered them.",
  },
  {
    id: "junit",
    name: "JUnit reports",
    short: "Test",
    detail: "JUnit XML test suites, case results and failures, tied to their build.",
  },
  {
    id: "sentry",
    name: "Sentry",
    short: "Observe",
    detail: "Production errors and releases, connected to the delivery history behind them.",
  },
];

export const roadmap = [
  ["gitlab", "GitLab"],
  ["jira", "Jira"],
  ["linear", "Linear"],
  ["jenkins", "Jenkins"],
  ["sonarqube", "SonarQube"],
  ["playwright", "Playwright"],
  ["selenium", "Selenium"],
  ["aws", "AWS"],
];

export function ToolLogo({ id, className = "" }: { id: string; className?: string }) {
  // Local source SVGs do not benefit from raster image optimization.
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      className={`tool-logo ${className}`}
      src={`/integrations/${id}.svg`}
      width={28}
      height={28}
      alt=""
      draggable={false}
    />
  );
}

export function FlowDemo({
  reverse,
  onSelect,
}: {
  reverse: boolean;
  onSelect: (step: number) => void;
}) {
  const pulse = useRef<HTMLSpanElement>(null);
  const cancel = useRef<() => void>(() => {});
  const mounted = useRef(false);
  const busy = useRef(false);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      cancel.current();
    };
  }, []);
  async function play() {
    if (busy.current) return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      onSelect(reverse ? 0 : 3);
      return;
    }
    busy.current = true;
    setPlaying(true);
    try {
      const { animate } = await import("animejs");
      if (!mounted.current) return;
      const state = { progress: 0 };
      let previous = -1;
      const animation = animate(state, {
        progress: 1,
        duration: 2400,
        ease: "linear",
        onUpdate: () => {
          const step = Math.min(3, Math.floor(state.progress * 4));
          if (step !== previous) {
            previous = step;
            onSelect(reverse ? 3 - step : step);
          }
          if (pulse.current) pulse.current.style.left = `${4 + state.progress * 92}%`;
        },
        onComplete: () => {
          if (mounted.current) {
            busy.current = false;
            setPlaying(false);
          }
        },
      });
      cancel.current = () => animation.revert();
    } catch {
      busy.current = false;
      if (mounted.current) setPlaying(false);
    }
  }
  return (
    <div className="flow-demo" data-playing={playing}>
      <div className="flow-rail" aria-hidden="true">
        <span ref={pulse} />
      </div>
      <button type="button" onClick={() => void play()} disabled={playing}>
        <Play size={11} aria-hidden="true" />
        {playing
          ? "Following the signal…"
          : reverse
            ? "Trace an example backward"
            : "Play a delivery example"}
      </button>
    </div>
  );
}
