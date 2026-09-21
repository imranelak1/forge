"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { createTimeline } from "animejs";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Check,
  GitBranch,
  GitCommitHorizontal,
  GitPullRequest,
  Layers3,
  Play,
  RotateCcw,
  Workflow,
} from "lucide-react";
import { CircuitBoard, modules } from "./circuit-board";

const chapters = [
  {
    id: "connect",
    title: "Your tools.\nA common language.",
    description:
      "Code lives in GitHub. Builds live in CI. Errors live in production. Bring their signals together, without losing where they came from.",
    detail: "Planned sources",
    items: ["GitHub", "GitHub Actions", "JUnit", "Sentry"],
    caption: "Separate sources. Shared context.",
  },
  {
    id: "trace",
    title: "Follow the change.\nKeep the context.",
    description:
      "Connect the pull request to its commits, checks and deployment. Follow the evidence across the entire delivery lifecycle.",
    detail: "One connected lifecycle",
    items: ["Pull request", "Commit", "Build", "Deployment"],
    caption: "A path from code to production.",
  },
  {
    id: "understand",
    title: "Find where\nprogress gets stuck.",
    description:
      "See where reviews wait, builds slow down and tests become unreliable. Every insight should lead back to the events behind it.",
    detail: "Planned intelligence",
    items: ["Review time", "Build reliability", "Test failures"],
    caption: "Measure the process. Keep the evidence.",
  },
  {
    id: "investigate",
    title: "An error is\nonly the beginning.",
    description:
      "Start with a production error. Trace its release and related changes backward, so the next question has somewhere to go.",
    detail: "Illustrated investigation",
    items: ["Production error", "Deployment", "Related commit"],
    caption: "Follow the signal back to the change.",
  },
  {
    id: "automate",
    title: "Close the loop.\nStay in control.",
    description:
      "Turn explicit conditions into deliberate pipeline responses. See why a rule matched, what it did and the record it left behind.",
    detail: "Planned automation",
    items: ["Evaluate conditions", "Run an action", "Keep an audit trail"],
    caption: "Connected evidence. Accountable action.",
  },
];

export function LandingPage() {
  const story = useRef<HTMLDivElement>(null);
  const board = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(-1);
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const root = story.current;
    const canvas = board.current;
    if (!root || !canvas) return;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    let timeline: ReturnType<typeof createTimeline> | undefined;
    let previous = -2;
    const chaptersElements = Array.from(root.querySelectorAll<HTMLElement>("[data-chapter]"));
    const signal = canvas.querySelector<SVGCircleElement>(".incident-signal");
    const signalPath = canvas.querySelector<SVGPathElement>(".incident-path");
    const signalLength = signalPath?.getTotalLength() ?? 0;
    const signalPosition = { value: 0 };

    const update = () => {
      frame = 0;
      const viewportAnchor = window.innerHeight * (window.innerWidth < 900 ? 0.68 : 0.52);
      let chapter = -1;
      chaptersElements.forEach((element, i) => {
        if (element.getBoundingClientRect().top <= viewportAnchor) chapter = i;
      });
      if (chapter !== previous) {
        previous = chapter;
        setActive(chapter);
      }
      if (!timeline) return;
      const target = chaptersElements[Math.max(0, chapter)];
      const position = target.getBoundingClientRect();
      const local = Math.max(
        0,
        Math.min(
          1,
          (viewportAnchor - position.top) /
            Math.min(position.height * 0.7, window.innerHeight * 0.65),
        ),
      );
      const progress = chapter < 0 ? 0 : (chapter + local) * 1000;
      timeline.seek(progress);
      if (signal && signalPath && chapter === 3) {
        const point = signalPath.getPointAtLength(signalLength * signalPosition.value);
        signal.setAttribute("cx", String(point.x));
        signal.setAttribute("cy", String(point.y));
      }
      canvas.dataset.progress = String(Math.round(progress));
    };
    const requestUpdate = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    const configure = () => {
      timeline?.revert();
      timeline = undefined;
      setReduced(media.matches);
      if (!media.matches) {
        timeline = createTimeline({ autoplay: false, defaults: { ease: "linear" } });
        modules.forEach((_, i) => {
          timeline!.add(
            canvas.querySelectorAll(`.module-${i}`),
            { opacity: [0, 1], translateY: [-38, 0], duration: 450, ease: "out(3)" },
            i * 1000,
          );
          timeline!.add(
            canvas.querySelectorAll(`.trace-${i}`),
            { strokeDashoffset: [1, 0], duration: 750 },
            i * 1000 + 150,
          );
          timeline!.add(
            canvas.querySelectorAll(`.node-${i}`),
            { opacity: [0, 1], duration: 300 },
            i * 1000 + 350,
          );
        });
        timeline.add(
          canvas.querySelector(".circuit-object")!,
          { rotateX: [32, 8], rotateZ: [-24, 0], duration: 5000 },
          0,
        );
        timeline.add(signalPosition, { value: [0, 1], duration: 850 }, 3100);
        timeline.add(
          canvas.querySelectorAll(".incident-path"),
          { strokeDashoffset: [1, 0], opacity: [0, 1], duration: 900 },
          3000,
        );
        timeline.add(
          canvas.querySelectorAll(".incident-path"),
          { opacity: [1, 0], duration: 300 },
          4100,
        );
        timeline.add(
          canvas.querySelectorAll(".incident-signal"),
          { opacity: [0, 1], duration: 80 },
          3100,
        );
        timeline.add(
          canvas.querySelectorAll(".incident-signal"),
          { opacity: [1, 0], duration: 150 },
          3950,
        );
        // Prime every future child before the first seek so unassembled modules
        // start hidden, including when this component remounts through navigation.
        timeline.seek(timeline.duration);
        timeline.seek(0);
      }
      update();
    };
    configure();
    window.addEventListener("scroll", requestUpdate, { passive: true });
    window.addEventListener("resize", requestUpdate);
    media.addEventListener("change", configure);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", requestUpdate);
      window.removeEventListener("resize", requestUpdate);
      media.removeEventListener("change", configure);
      timeline?.revert();
    };
  }, []);

  return (
    <div className="landing">
      <a className="skip-link" href="#landing-content">
        Skip to content
      </a>
      <header className="landing-header">
        <Link className="landing-wordmark" href="/" aria-label="Forge home">
          forge<span aria-hidden="true">.</span>
        </Link>
        <nav aria-label="Website navigation">
          <a href="#connect">The platform</a>
          <Link href="/guide">
            Build notes <ArrowUpRight size={13} aria-hidden="true" />
          </Link>
        </nav>
        <Link href="/app" className="landing-open">
          Open platform <ArrowUpRight size={16} aria-hidden="true" />
        </Link>
      </header>

      <main id="landing-content" tabIndex={-1}>
        <div className="assembly-story" ref={story}>
          <div className="story-copy">
            <section className="landing-hero" aria-labelledby="hero-title">
              <h1 id="hero-title">
                Every change.
                <br />
                Every signal.
                <br />
                <span>Connected.</span>
              </h1>
              <p className="hero-description">
                Engineering intelligence, from the first commit to what happens in production.
              </p>
              <div className="hero-actions">
                <Link href="/app" className="landing-button">
                  Explore Forge <ArrowUpRight size={17} aria-hidden="true" />
                </Link>
                <a href="#connect" className="landing-link">
                  See how it connects <ArrowDown size={16} aria-hidden="true" />
                </a>
              </div>
              <p className="preview-note">In development. Explore the working foundation.</p>
              <a href="#connect" className="scroll-invitation">
                <span className="scroll-line" aria-hidden="true" />
                Scroll to assemble the bigger picture
              </a>
            </section>

            {chapters.map((chapter, i) => (
              <section
                key={chapter.id}
                id={chapter.id}
                data-chapter={chapter.id}
                className={`story-chapter chapter-${chapter.id}`}
                aria-labelledby={`${chapter.id}-title`}
              >
                <p className="sr-only">
                  Step {i + 1} of 5: {chapter.id}
                </p>
                <h2 id={`${chapter.id}-title`}>
                  {chapter.title.split("\n").map((line, n) => (
                    <span key={n}>
                      {line}
                      {n === 0 && <br />}
                    </span>
                  ))}
                </h2>
                <p className="chapter-description">{chapter.description}</p>
                <div className="chapter-evidence">
                  <p>{chapter.detail}</p>
                  {i === 0 ? (
                    <ul className="source-list">
                      {chapter.items.map((item, n) => (
                        <li key={item}>
                          {n === 0 ? (
                            <GitBranch size={17} />
                          ) : n === 1 ? (
                            <Workflow size={17} />
                          ) : n === 2 ? (
                            <Check size={17} />
                          ) : (
                            <Layers3 size={17} />
                          )}
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <ol className="evidence-path">
                      {chapter.items.map((item, n) => (
                        <li key={item}>
                          <span>{item}</span>
                          {n < chapter.items.length - 1 && (
                            <ArrowRight size={13} aria-hidden="true" />
                          )}
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              </section>
            ))}
          </div>

          <div
            ref={board}
            className="board-stage"
            data-active={active >= 0 ? modules[active].id : "core"}
            data-highlight={highlighted ?? "none"}
            data-reduced-motion={reduced}
          >
            <div className="board-overline">
              <span>One connected system</span>
              <span>Product preview</span>
            </div>
            <div className="circuit-perspective">
              <div className="circuit-object">
                <CircuitBoard />
              </div>
            </div>
            <div className="board-caption">
              <span className="caption-marker" aria-hidden="true" />
              <p>
                {active >= 0 ? chapters[active].caption : "The whole lifecycle. Coming together."}
              </p>
            </div>
            <nav
              className="circuit-navigation"
              aria-label="Circuit chapters"
              onMouseLeave={() => setHighlighted(null)}
            >
              {modules.map((mod, i) => (
                <a
                  key={mod.id}
                  href={`#${mod.id}`}
                  aria-current={active === i ? "step" : undefined}
                  onMouseEnter={() => setHighlighted(mod.id)}
                  onFocus={() => setHighlighted(mod.id)}
                  onBlur={() => setHighlighted(null)}
                >
                  <span className="circuit-step-number">0{i + 1}</span>
                  <span>{mod.label}</span>
                </a>
              ))}
            </nav>
          </div>
        </div>

        <section className="landing-close" aria-labelledby="close-title">
          <div className="close-topline">
            <GitPullRequest size={20} aria-hidden="true" />
            <span className="close-connector" />
            <GitCommitHorizontal size={20} aria-hidden="true" />
            <span className="close-connector" />
            <Play size={18} aria-hidden="true" />
            <span className="close-connector" />
            <Layers3 size={20} aria-hidden="true" />
          </div>
          <h2 id="close-title">
            See the system.
            <br />
            <span>Understand the change.</span>
          </h2>
          <p>
            We’re building Forge to connect engineering evidence with decisions you can explain.
          </p>
          <Link href="/app" className="landing-button">
            Open the foundation <ArrowUpRight size={17} aria-hidden="true" />
          </Link>
          <div className="build-disclosure">
            <span>Available now</span>
            <p>
              Application shell, live system checks and setup guide. Integrations, intelligence and
              automation are in development.
            </p>
          </div>
          <a href="#hero-title" className="replay-link">
            <RotateCcw size={14} aria-hidden="true" />
            Back to the circuit
          </a>
        </section>
      </main>

      <footer className="landing-footer">
        <Link href="/" className="landing-wordmark" aria-label="Forge home">
          forge<span aria-hidden="true">.</span>
        </Link>
        <p>Engineering, connected.</p>
        <nav aria-label="Footer navigation">
          <Link href="/guide">Setup guide</Link>
          <Link href="/system">System status</Link>
          <Link href="/app">
            Platform <ArrowUpRight size={13} aria-hidden="true" />
          </Link>
        </nav>
      </footer>
    </div>
  );
}
