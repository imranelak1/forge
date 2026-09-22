"use client";

import { Fragment, useEffect, type RefObject } from "react";

export function TextLines({ lines }: { lines: string[] }) {
  return lines.map((line, index) => (
    <Fragment key={line}>
      {index > 0 && " "}
      <span className="motion-line" data-text-line={index}>
        {line}
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
    let generation = 0;
    let cleanup = () => {};

    async function configure() {
      const version = ++generation;
      cleanup();
      cleanup = () => {};
      element!.dataset.textMotion = preference.matches ? "static" : "loading";
      if (preference.matches) return;
      const { createTimeline, splitText, stagger } = await import("animejs");
      if (version !== generation) return;
      const seen = new Set<HTMLElement>();
      const running = new Map<HTMLElement, () => void>();
      const finish = (scene: HTMLElement) => running.get(scene)?.();
      const reveal = (scene: HTMLElement) => {
        const headings = Array.from(scene.querySelectorAll<HTMLElement>("[data-text-line]"));
        const copy = scene.querySelector<HTMLElement>("[data-text-copy]");
        // Split only for the entrance, then restore the original DOM for natural text flow.
        const titles = headings.map((line) =>
          splitText(line, { words: { wrap: "clip" }, chars: true }),
        );
        const body = copy ? splitText(copy, { words: { wrap: "clip" } }) : null;
        const chars = titles.flatMap((title) => title.chars);
        scene.dataset.textState = "running";
        const timeline = createTimeline({ autoplay: false, onComplete: () => finish(scene) });
        const restore = () => {
          timeline.revert();
          titles.forEach((title) => title.revert());
          body?.revert();
          running.delete(scene);
          scene.dataset.textState = "complete";
        };
        running.set(scene, restore);
        const reverse = scene.dataset.textScene === "investigate";
        timeline.add(
          chars,
          {
            y: [reverse ? "-105%" : "105%", "0%"],
            duration: 440,
            ease: "out(4)",
            delay: stagger(Math.min(12, 180 / Math.max(1, chars.length - 1))),
          },
          0,
        );
        if (body)
          timeline.add(
            body.words,
            {
              y: ["110%", "0%"],
              duration: 330,
              ease: "out(4)",
              delay: stagger(Math.min(14, 230 / Math.max(1, body.words.length - 1))),
            },
            60,
          );
        timeline.play();
      };
      const observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            const scene = entry.target as HTMLElement;
            if (!entry.isIntersecting) {
              finish(scene);
              if (entry.boundingClientRect.bottom < 0 || entry.boundingClientRect.top > innerHeight)
                seen.delete(scene);
            } else if (!seen.has(scene)) {
              seen.add(scene);
              reveal(scene);
            }
          }
        },
        { rootMargin: "0px 0px -5% 0px", threshold: 0.2 },
      );
      const finishAll = () => [...running.keys()].forEach(finish);
      const onFocus = (event: FocusEvent) => {
        if (event.target instanceof Element) {
          const scene = event.target.closest<HTMLElement>("[data-text-scene]");
          if (scene) finish(scene);
        }
      };
      const onVisibility = () => {
        if (document.hidden) finishAll();
      };
      scenes.forEach((scene) => observer.observe(scene));
      element!.addEventListener("focusin", onFocus);
      window.addEventListener("resize", finishAll);
      document.addEventListener("visibilitychange", onVisibility);
      element!.dataset.textMotion = "ready";
      cleanup = () => {
        observer.disconnect();
        finishAll();
        scenes.forEach((scene) => delete scene.dataset.textState);
        element!.removeEventListener("focusin", onFocus);
        window.removeEventListener("resize", finishAll);
        document.removeEventListener("visibilitychange", onVisibility);
      };
    }
    const onPreference = () => {
      void configure().catch(() => {
        element.dataset.textMotion = "static";
      });
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
