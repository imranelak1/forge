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

const clamp = (value: number) => Math.max(0, Math.min(1, value));

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
      const [{ createTimeline, splitText, stagger }] = await Promise.all([
        import("animejs"),
        document.fonts.ready,
      ]);
      if (version !== generation) return;
      let frame = 0,
        lastTime = 0;
      const passages = scenes.map((scene) => {
        const headings = Array.from(scene.querySelectorAll<HTMLElement>("[data-text-line]"));
        const copy = scene.querySelector<HTMLElement>("[data-text-copy]");
        // Persistent splits let scrolling scrub both entrance and exit without restarting.
        // Anime.js keeps an unsplit, visually hidden copy for assistive technology.
        const titles = headings.map((line) =>
          splitText(line, { words: { wrap: "clip" }, chars: true }),
        );
        const body = copy ? splitText(copy, { words: { wrap: "clip" } }) : null;
        const chars = titles.flatMap((title) => title.chars);
        const words = body?.words ?? [];
        const evidence = scene.querySelector<HTMLElement>(".chapter-evidence");
        const direction = scene.dataset.textScene === "investigate" ? -1 : 1;
        const titleStagger = stagger(Math.min(16, 180 / Math.max(1, chars.length - 1)));
        const wordStagger = stagger(Math.min(18, 200 / Math.max(1, words.length - 1)));
        const timeline = createTimeline({ autoplay: false }).add(
          chars,
          {
            y: [`${direction * 120}%`, "0%"],
            x: [direction * 8, 0],
            opacity: [0, 1],
            duration: 540,
            delay: titleStagger,
            ease: "out(3)",
          },
          0,
        );
        if (words.length)
          timeline.add(
            words,
            {
              y: ["115%", "0%"],
              opacity: [0, 1],
              duration: 400,
              delay: wordStagger,
              ease: "out(3)",
            },
            120,
          );
        timeline.add(
          chars,
          {
            y: ["0%", `${direction * -120}%`],
            x: [0, direction * -8],
            opacity: [1, 0],
            duration: 320,
            delay: titleStagger,
            ease: "in(2)",
          },
          900,
        );
        if (words.length)
          timeline.add(
            words,
            {
              y: ["0%", "-115%"],
              opacity: [1, 0],
              duration: 280,
              delay: stagger(Math.min(14, 150 / Math.max(1, words.length - 1))),
              ease: "in(2)",
            },
            950,
          );
        if (evidence)
          timeline
            .add(evidence, { y: [12, 0], opacity: [0, 1], duration: 300, ease: "out(3)" }, 260)
            .add(evidence, { y: [0, -12], opacity: [1, 0], duration: 240, ease: "in(2)" }, 1040);
        return { scene, headings, copy, titles, body, timeline, target: 0, progress: 0 };
      });
      const read = () => {
        for (const passage of passages) {
          const { scene, headings, copy } = passage;
          const top = headings[0].getBoundingClientRect().top;
          const bottom = (copy ?? headings.at(-1)!).getBoundingClientRect().bottom;
          const height = bottom - top;
          const chapter = Boolean(scene.closest("[data-chapter]"));
          // Keep a reading interval, including room to read unusually tall paragraphs.
          const exitStart = Math.min(
            chapter ? innerHeight * 0.22 : Math.min(80, innerHeight * 0.1),
            innerHeight * 0.82 - height,
          );
          const exitEnd = exitStart - Math.max(110, Math.min(190, height * 0.6));
          const entrance = clamp((innerHeight * 0.94 - top) / (innerHeight * 0.42));
          const exit = clamp((exitStart - top) / (exitStart - exitEnd));
          passage.target = exit > 0 ? 1 + exit : entrance;
          if (scene.contains(document.activeElement) && top < innerHeight && bottom > 0)
            passage.target = 1;
        }
      };
      const draw = (time: number) => {
        frame = 0;
        if (document.hidden) return;
        const dt = Math.min((time - lastTime) / 1000 || 0.016, 0.05);
        lastTime = time;
        let moving = false;
        for (const passage of passages) {
          passage.progress += (passage.target - passage.progress) * (1 - Math.exp(-dt * 16));
          if (Math.abs(passage.target - passage.progress) < 0.001)
            passage.progress = passage.target;
          const progress = passage.progress;
          const clock = progress <= 1 ? progress * 720 : 900 + (progress - 1) * 500;
          passage.timeline.seek(clock, true);
          passage.scene.dataset.textProgress = progress.toFixed(3);
          passage.scene.dataset.textState =
            progress === 0
              ? "before"
              : progress === 2
                ? "after"
                : progress === 1
                  ? "visible"
                  : progress < 1
                    ? "entering"
                    : "exiting";
          moving ||= progress !== passage.target;
        }
        element!.dataset.textMoving = String(moving);
        if (moving) frame = requestAnimationFrame(draw);
      };
      const requestDraw = () => {
        if (!frame && !document.hidden) frame = requestAnimationFrame(draw);
      };
      const onScroll = () => {
        read();
        requestDraw();
      };
      const onVisibility = () => {
        if (document.hidden) {
          cancelAnimationFrame(frame);
          frame = 0;
        } else onScroll();
      };
      const onFocus = () => {
        read();
        for (const passage of passages) {
          if (passage.scene.contains(document.activeElement)) passage.progress = passage.target;
        }
        requestDraw();
      };
      const resize = new ResizeObserver(onScroll);
      passages.forEach(({ scene }) => resize.observe(scene));
      window.addEventListener("scroll", onScroll, { passive: true });
      window.addEventListener("resize", onScroll);
      element!.addEventListener("focusin", onFocus);
      element!.addEventListener("focusout", onScroll);
      document.addEventListener("visibilitychange", onVisibility);
      read();
      for (const passage of passages) {
        // Animate the first visible passage on load; offscreen text takes its scroll state.
        passage.progress = passage.target > 0 && passage.target <= 1 ? 0 : passage.target;
      }
      element!.dataset.textMotion = "ready";
      requestDraw();
      cleanup = () => {
        cancelAnimationFrame(frame);
        resize.disconnect();
        window.removeEventListener("scroll", onScroll);
        window.removeEventListener("resize", onScroll);
        element!.removeEventListener("focusin", onFocus);
        element!.removeEventListener("focusout", onScroll);
        document.removeEventListener("visibilitychange", onVisibility);
        passages.forEach(({ scene, timeline, titles, body }) => {
          timeline.revert();
          titles.forEach((title) => title.revert());
          body?.revert();
          delete scene.dataset.textState;
          delete scene.dataset.textProgress;
        });
        delete element!.dataset.textMoving;
      };
    }
    const onPreference = () => {
      void configure().catch(() => {
        cleanup();
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
