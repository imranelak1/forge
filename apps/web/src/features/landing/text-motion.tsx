"use client";

import { Fragment, useEffect, type RefObject } from "react";

/** React owns the word spans so selection, wrapping, and reconciliation stay intact. */
export function TextLines({ lines }: { lines: string[] }) {
  return lines.map((line, lineIndex) => (
    <Fragment key={line}>
      {lineIndex > 0 && " "}
      <span className="motion-line" data-text-line={lineIndex}>
        {line.split(" ").map((word, wordIndex) => (
          <Fragment key={`${wordIndex}-${word}`}>
            {wordIndex > 0 && " "}
            <span className="motion-word" data-text-word>
              {word}
            </span>
          </Fragment>
        ))}
      </span>
    </Fragment>
  ));
}

export function useLandingTextMotion(root: RefObject<HTMLDivElement | null>) {
  useEffect(() => {
    const element = root.current;
    if (!element) return;
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    const scenes = Array.from(element.querySelectorAll<HTMLElement>("[data-text-scene]"));
    const seen = new Set<HTMLElement>();
    let generation = 0;
    let cleanup = () => {};

    async function configure() {
      const version = ++generation;
      cleanup();
      cleanup = () => {};
      element!.dataset.textMotion = preference.matches ? "static" : "loading";
      if (preference.matches) return;
      try {
        const { createTimeline, stagger } = await import("animejs");
        if (version !== generation) return;
        const running = new Map<HTMLElement, ReturnType<typeof createTimeline>>();
        const finish = (scene: HTMLElement) => running.get(scene)?.complete();
        const observer = new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              const scene = entry.target as HTMLElement;
              if (!entry.isIntersecting) {
                finish(scene);
                continue;
              }
              if (seen.has(scene)) continue;
              seen.add(scene);
              const words = Array.from(scene.querySelectorAll<HTMLElement>("[data-text-word]"));
              const copy = scene.querySelector<HTMLElement>("[data-text-copy]");
              const kind = scene.dataset.textScene;
              const reverse = kind === "investigate";
              const inspect = kind === "understand";
              const assemble = kind === "hero" || kind === "automate" || kind === "close";
              scene.dataset.textState = "running";
              const timeline = createTimeline({
                autoplay: false,
                defaults: { duration: assemble ? 640 : 500, ease: "out(4)" },
                onComplete: () => {
                  timeline.revert();
                  running.delete(scene);
                  scene.dataset.textState = "complete";
                },
              });
              timeline.add(
                words,
                {
                  x: {
                    from: (target?: unknown) =>
                      inspect
                        ? 0
                        : assemble
                          ? target instanceof HTMLElement &&
                            target.parentElement?.dataset.textLine === "0"
                            ? -14
                            : 14
                          : reverse
                            ? 18
                            : -18,
                    to: 0,
                  },
                  opacity: [0.35, 1],
                  filter: inspect ? ["blur(4px)", "blur(0px)"] : ["blur(0px)", "blur(0px)"],
                  delay: stagger(Math.min(45, 180 / Math.max(1, words.length - 1)), {
                    from: reverse ? "last" : "first",
                  }),
                },
                0,
              );
              if (copy)
                timeline.add(
                  copy,
                  {
                    opacity: [0.5, 1],
                    y: [6, 0],
                    duration: 420,
                  },
                  120,
                );
              running.set(scene, timeline);
              timeline.play();
            }
          },
          { rootMargin: "0px 0px -12% 0px", threshold: 0.12 },
        );
        const onFocus = (event: FocusEvent) => {
          if (event.target instanceof Element) {
            const scene = event.target.closest<HTMLElement>("[data-text-scene]");
            if (scene) finish(scene);
          }
        };
        const onVisibility = () => {
          if (document.hidden) [...running.keys()].forEach(finish);
        };
        scenes.forEach((scene) => observer.observe(scene));
        element!.addEventListener("focusin", onFocus);
        document.addEventListener("visibilitychange", onVisibility);
        element!.dataset.textMotion = "ready";
        cleanup = () => {
          observer.disconnect();
          running.forEach((timeline) => timeline.revert());
          running.clear();
          scenes.forEach((scene) => delete scene.dataset.textState);
          element!.removeEventListener("focusin", onFocus);
          document.removeEventListener("visibilitychange", onVisibility);
        };
      } catch {
        if (version === generation) element!.dataset.textMotion = "static";
      }
    }

    const onPreference = () => {
      void configure();
    };
    onPreference();
    preference.addEventListener("change", onPreference);
    return () => {
      generation++;
      cleanup();
      preference.removeEventListener("change", onPreference);
      delete element.dataset.textMotion;
    };
  }, [root]);
}
