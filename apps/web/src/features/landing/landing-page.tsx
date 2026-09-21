"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { ArrowDown, ArrowRight, ArrowUpRight, MoveUpRight, RotateCcw } from "lucide-react";
import { FlowDemo, integrations, roadmap, ToolLogo } from "./integrations";
import { CoreScene, chapterNames, seekStory } from "./core-scene";
import { TextLines, useLandingTextMotion } from "./text-motion";
import { CodePreview } from "./code-preview";

const chapters = [
  {
    id: "connect",
    title: "Connect the tools.\nKeep the context.",
    description:
      "Bring a pull request, its CI run, test report and production error together. Forge is being built to link them by the change they share.",
    detail: "One example throughout this tour",
    items: ["Checkout service", "PR #184", "Commit 8f3a2c1"],
    caption:
      "Connect: four source records share commit 8f3a2c1. Select a record to inspect its example event.",
  },
  {
    id: "trace",
    title: "Follow the change\ninto production.",
    description:
      "See which build tested a commit and which release shipped it. A shared commit creates a trail you can follow across tools.",
    detail: "The same checkout change",
    items: ["PR #184", "CI #928", "Release 8f3a2c1"],
    caption:
      "Trace: the pull request, passing CI run and production error line up around the same commit.",
  },
  {
    id: "understand",
    title: "Make the failure\nunderstandable.",
    description:
      "The original tests passed, but checkout failed without a coupon. A new regression test reproduces the error and gives the team evidence to work from.",
    detail: "Reproduction after the production error",
    items: ["CI #929", "Null coupon", "Failing test"],
    caption:
      "Understand: open the new regression test. Checkout without a coupon reproduces the error.",
  },
  {
    id: "investigate",
    title: "Find the line.\nReview the fix.",
    description:
      "Trace the error back to its release and related code. Compare the suspected change with a candidate fix, then verify it with the failing test.",
    detail: "Evidence before conclusions",
    items: ["Sentry error", "Related commit", "Candidate diff"],
    caption:
      "Investigate: compare the production error with a candidate change, then verify it with the failing test.",
  },
  {
    id: "automate",
    title: "Set a condition.\nChoose a response.",
    description:
      "A failed regression test can become a review request with the linked commit attached. Planned rules will explain why they matched and record the response.",
    detail: "An explicit, reviewable response",
    items: ["Failed test", "Request review", "Human decision"],
    caption:
      "Automate: collect the linked evidence into a review request. A person decides what happens next.",
  },
];

export function LandingPage() {
  const landing = useRef<HTMLDivElement>(null);
  useLandingTextMotion(landing);
  const story = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(-1);
  const [selectedTool, setSelectedTool] = useState(0);
  return (
    <div className="landing" ref={landing}>
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
        <div className="core-story" ref={story}>
          <div className="core-stage" data-active={active >= 0 ? chapters[active].id : "intro"}>
            <CoreScene
              story={story}
              onStageChange={setActive}
              active={active}
              selected={selectedTool}
              onSelect={setSelectedTool}
            />
          </div>
          <div className="core-stage-footer">
            <div className="core-scrubber">
              <label htmlFor="story-progress">Follow the change</label>
              <input
                id="story-progress"
                data-story-scrubber
                type="range"
                min="0"
                max="5"
                step="0.01"
                defaultValue="0"
                aria-label="Story progress"
                aria-valuetext="Introduction"
                onChange={(event) => seekStory(story.current, Number(event.target.value))}
              />
              <button
                type="button"
                className="core-reset"
                aria-label="Restart story"
                onClick={() => seekStory(story.current, 0)}
              >
                <RotateCcw size={13} aria-hidden="true" />
                <span>Restart</span>
              </button>
            </div>
            <p className="core-caption">
              {active >= 0
                ? chapters[active].caption
                : "One checkout change. Follow its code, tests and production error."}
            </p>
            <nav className="core-navigation" aria-label="Story chapters">
              {chapters.map((chapter, i) => (
                <a
                  key={chapter.id}
                  href={`#${chapter.id}`}
                  aria-current={active === i ? "step" : undefined}
                >
                  {chapterNames[i]}
                </a>
              ))}
            </nav>
          </div>
          <section className="core-hero" aria-labelledby="hero-title">
            <div className="hero-copy" data-text-scene="hero">
              <h1 id="hero-title">
                <TextLines lines={["Every change.", "In context."]} />
              </h1>
              <p data-text-copy>
                Connect pull requests, builds, tests and production errors.
                <br />
                Find the change. Understand what happened.
              </p>
              <div className="hero-actions">
                <Link href="/app" className="landing-button">
                  Explore Forge <ArrowUpRight size={16} aria-hidden="true" />
                </Link>
                <a href="#connect" className="landing-link">
                  Follow a change <ArrowDown size={15} aria-hidden="true" />
                </a>
              </div>
              <p className="preview-note">
                Interactive example. Integrations and automation are in development.
              </p>
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
              className={`core-chapter ${i % 2 ? "chapter-right" : "chapter-left"}`}
              aria-labelledby={`${chapter.id}-title`}
            >
              <div className="chapter-inner">
                <div className="chapter-copy" data-text-scene={chapter.id}>
                  <p className="sr-only">
                    Step {i + 1} of 5: {chapterNames[i]}
                  </p>
                  <h2 id={`${chapter.id}-title`}>
                    <TextLines lines={chapter.title.split("\n")} />
                  </h2>
                  <p className="chapter-description" data-text-copy>
                    {chapter.description}
                  </p>
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
                <aside className="chapter-endpoint" aria-label={chapterNames[i] + " illustration"}>
                  <p>
                    Illustrative example ·{" "}
                    {i === 0
                      ? "source events"
                      : i === 1
                        ? "delivery workflow"
                        : i === 2
                          ? "regression test"
                          : i === 3
                            ? "candidate fix"
                            : "response logic"}
                  </p>
                  {i === 0 && (
                    <div className="workflow-tools">
                      {integrations.map((tool, n) => (
                        <button
                          key={tool.id}
                          type="button"
                          aria-label={"Inspect " + tool.name}
                          aria-pressed={selectedTool === n}
                          onClick={() => {
                            setSelectedTool(n);
                          }}
                        >
                          <ToolLogo id={tool.id} />
                          <span>{tool.short}</span>
                        </button>
                      ))}
                    </div>
                  )}
                  <CodePreview step={i} source={selectedTool} />
                  {(i === 0 || i === 1 || i === 3) && (
                    <>
                      <FlowDemo
                        reverse={i === 3}
                        onSelect={(step) => {
                          setSelectedTool(step);
                        }}
                      />
                      <div className="tool-explanation" aria-live="polite">
                        <strong>{integrations[selectedTool].name}</strong>
                        <p>{integrations[selectedTool].detail}</p>
                      </div>
                    </>
                  )}
                </aside>
              </div>
            </section>
          ))}
        </div>
        <section className="integration-section" aria-labelledby="integrations-title">
          <div className="integration-intro" data-text-scene="integrations">
            <h2 id="integrations-title">
              <TextLines lines={["Built around", "your engineering stack."]} />
            </h2>
            <p data-text-copy>
              Start with the tools that carry your delivery story. More connections are on the
              roadmap.
            </p>
          </div>
          <div className="integration-current">
            <h3>Initial integrations (in development)</h3>
            <div className="integration-list">
              {integrations.map((tool) => (
                <div key={tool.id}>
                  <ToolLogo id={tool.id} />
                  <h4>{tool.name}</h4>
                  <p>{tool.detail}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="integration-roadmap">
            <h3>On the roadmap</h3>
            <ul>
              {roadmap.map(([id, name]) => (
                <li key={id}>
                  <ToolLogo id={id} />
                  <span>{name}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
        <section className="landing-close" aria-labelledby="close-title" data-text-scene="close">
          <MoveUpRight size={38} strokeWidth={1} aria-hidden="true" />
          <h2 id="close-title">
            <TextLines lines={["The whole story.", "A clearer next step."]} />
          </h2>
          <p data-text-copy>
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
