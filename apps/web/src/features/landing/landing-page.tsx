"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { ArrowDown, ArrowRight, ArrowUpRight, MoveUpRight } from "lucide-react";
import { CableScene, chapterNames } from "./cable-scene";

const chapters = [
  {
    id: "connect",
    title: "Separate tools.\nA shared thread.",
    description:
      "Bring code, builds, tests and production errors into the same story. Keep each signal connected to where it came from.",
    detail: "Planned connections",
    items: ["GitHub", "GitHub Actions", "JUnit", "Sentry"],
    caption: "Independent signals become one continuous thread.",
  },
  {
    id: "trace",
    title: "Nothing happens\nin isolation.",
    description:
      "Follow a change from its pull request to the build that tested it and the deployment that shipped it.",
    detail: "The delivery lifecycle",
    items: ["Pull request", "Commit", "Build", "Deployment"],
    caption: "One signal. Every step from code to production.",
  },
  {
    id: "understand",
    title: "See what’s\nholding you back.",
    description:
      "Unpick slow reviews, unreliable tests and repeated build failures. Every insight leads back to the evidence behind it.",
    detail: "Planned intelligence",
    items: ["Review time", "Build reliability", "Test failures"],
    caption: "Open the thread. Understand its individual signals.",
  },
  {
    id: "investigate",
    title: "Follow the signal.\nFind the context.",
    description:
      "Start with a production error and work backward. Connect the release to its related changes, without losing the trail.",
    detail: "Illustrated investigation",
    items: ["Production error", "Deployment", "Related commit"],
    caption: "Trace the story backward, from incident to change.",
  },
  {
    id: "automate",
    title: "Close the loop.\nKeep control.",
    description:
      "Turn explicit conditions into deliberate pipeline responses. Understand why a rule matched and keep a record of what happened next.",
    detail: "Planned automation",
    items: ["Conditions", "Action", "Audit trail"],
    caption: "From connected evidence to accountable action.",
  },
];

export function LandingPage() {
  const story = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(-1);
  const [focus, setFocus] = useState(-1);
  return (
    <div className="landing">
      <a className="skip-link" href="#landing-content">
        Skip to content
      </a>
      <header className="landing-header">
        <Link className="landing-wordmark" href="/" aria-label="Forge home">
          forge.
        </Link>
        <nav aria-label="Website navigation">
          <a href="#connect">The platform</a>
          <Link href="/guide">
            Build notes <ArrowUpRight size={13} aria-hidden="true" />
          </Link>
        </nav>
        <Link href="/app" className="landing-open">
          Open platform <ArrowUpRight size={15} aria-hidden="true" />
        </Link>
      </header>
      <main id="landing-content" tabIndex={-1}>
        <div className="cable-story" ref={story}>
          <div className="cable-stage" data-active={active >= 0 ? chapters[active].id : "intro"}>
            <CableScene story={story} onStageChange={setActive} focus={focus} />
            <div className="cable-stage-footer">
              <p className="cable-caption">
                {active >= 0
                  ? chapters[active].caption
                  : "Five capabilities. One connected system."}
              </p>
              <nav
                className="cable-navigation"
                aria-label="Story chapters"
                onMouseLeave={() => setFocus(-1)}
              >
                {chapters.map((chapter, i) => (
                  <a
                    key={chapter.id}
                    href={`#${chapter.id}`}
                    aria-current={active === i ? "step" : undefined}
                    onMouseEnter={() => setFocus(i)}
                    onFocus={() => setFocus(i)}
                    onBlur={() => setFocus(-1)}
                  >
                    {chapterNames[i]}
                  </a>
                ))}
              </nav>
            </div>
          </div>
          <section className="cable-hero" aria-labelledby="hero-title">
            <div className="hero-copy">
              <h1 id="hero-title">
                Everything.
                <br />
                Connected.
              </h1>
              <p>
                From the first commit to production.
                <br />
                Your engineering story, connected.
              </p>
              <div className="hero-actions">
                <Link href="/app" className="landing-button">
                  Explore Forge <ArrowUpRight size={16} aria-hidden="true" />
                </Link>
                <a href="#connect" className="landing-link">
                  Follow the thread <ArrowDown size={15} aria-hidden="true" />
                </a>
              </div>
              <p className="preview-note">In development. Explore the working foundation.</p>
            </div>
            <span className="hero-scroll-cue" aria-hidden="true">
              Scroll to connect <ArrowDown size={13} />
            </span>
          </section>
          {chapters.map((chapter, i) => (
            <section
              key={chapter.id}
              id={chapter.id}
              data-chapter={chapter.id}
              className={`cable-chapter ${i % 2 ? "chapter-right" : "chapter-left"}`}
              aria-labelledby={`${chapter.id}-title`}
            >
              <div className="chapter-inner">
                <div className="chapter-copy">
                  <p className="sr-only">
                    Step {i + 1} of 5: {chapterNames[i]}
                  </p>
                  <h2 id={`${chapter.id}-title`}>
                    {chapter.title.split("\n").map((line, n) => (
                      <span key={line}>
                        {n > 0 && <br />}
                        {line}
                      </span>
                    ))}
                  </h2>
                  <p className="chapter-description">{chapter.description}</p>
                  <div className="chapter-evidence">
                    <p>{chapter.detail}</p>
                    <ul>
                      {chapter.items.map((item, n) => (
                        <li key={item}>
                          {item}
                          {n < chapter.items.length - 1 && <span aria-hidden="true">/</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                <span className="chapter-endpoint" aria-hidden="true">
                  <span />
                  {chapterNames[i]}
                </span>
              </div>
            </section>
          ))}
        </div>
        <section className="landing-close" aria-labelledby="close-title">
          <MoveUpRight size={38} strokeWidth={1} aria-hidden="true" />
          <h2 id="close-title">
            The whole story.
            <br />A clearer next step.
          </h2>
          <p>
            We’re building Forge to turn connected engineering evidence into decisions you can
            explain.
          </p>
          <Link href="/app" className="landing-button">
            Open the foundation <ArrowRight size={16} aria-hidden="true" />
          </Link>
          <div className="build-disclosure">
            <span>Available now</span>
            <p>
              Application shell, live system checks and setup guide. Integrations, intelligence and
              automation are in development.
            </p>
          </div>
          <a className="back-to-top" href="#hero-title">
            Back to the start <ArrowUpRight size={13} aria-hidden="true" />
          </a>
        </section>
      </main>
      <footer className="landing-footer">
        <Link href="/" className="landing-wordmark" aria-label="Forge home">
          forge.
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
