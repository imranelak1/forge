"use client";

import { useEffect, useRef, type RefObject } from "react";
import { TrackLabels } from "./track-labels";
import "./track-labels.css";

export const chapterNames = ["Connect", "Trace", "Understand", "Investigate", "Automate"];

// One drawn line: pull request -> build -> tests -> release -> review.
const buildPath = "M80 50H280a55 55 0 0 1 0 110";
const testPath = `${buildPath}H120a55 55 0 0 0 0 110`;
const deliveryPath = `${testPath}H280a55 55 0 0 1 0 110`;
const reviewPath = "M280 380H245q-45 0-45 45v15";
const fullPath = `${deliveryPath}H245q-45 0-45 45v15`;

export function seekStory(root: HTMLDivElement | null, progress: number) {
  if (!root) return;
  const points = [
    root.getBoundingClientRect().top + scrollY,
    ...Array.from(root.querySelectorAll<HTMLElement>("[data-chapter]")).map(
      (el) => el.getBoundingClientRect().top + scrollY - innerHeight * 0.08,
    ),
  ];
  const index = Math.min(4, Math.floor(progress));
  scrollTo({
    top: points[index] + (points[index + 1] - points[index]) * Math.min(1, progress - index),
    behavior: "instant",
  });
}

export function CoreScene({
  story,
  onStageChange,
  active,
  selected,
  onSelect,
}: {
  story: RefObject<HTMLDivElement | null>;
  onStageChange: (stage: number) => void;
  active: number;
  selected: number;
  onSelect: (source: number) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = host.current;
    const root = story.current;
    if (!element || !root) return;
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    const track = element.querySelector<HTMLElement>(".svg-track")!;
    const scrubber = root.querySelector<HTMLInputElement>("[data-story-scrubber]")!;
    const stops = Array.from(element.querySelectorAll<HTMLElement>("[data-checkpoint]"));
    let cancelled = false;
    let destroy = () => {};

    void import("animejs")
      .then(({ animate, createTimeline, svg }) => {
        if (cancelled) return;
        const route = element.querySelector<SVGPathElement>("[data-motion-route]")!;
        const delivery = element.querySelector<SVGPathElement>("[data-delivery-route]")!;
        const test = element.querySelector<SVGPathElement>("[data-test-route]")!;
        const packet = element.querySelector<SVGGElement>(".track-packet")!;
        const { translateX, translateY } = svg.createMotionPath(route)!;
        // Keeping the follower inside the SVG makes the path exact at every viewport size.
        const follower = animate(packet, {
          translateX,
          translateY,
          duration: 1000,
          ease: "linear",
          autoplay: false,
        });
        const deliveryDraw = svg.createDrawable(delivery);
        const reviewDraw = svg.createDrawable(
          element.querySelector<SVGPathElement>(".track-review-path")!,
        );
        const motion = { position: 0, reveal: 0.12 };
        const length = route.getTotalLength();
        const deliveryEnd = delivery.getTotalLength() / length;
        const testStop = test.getTotalLength() / length;
        const timeline = createTimeline({ autoplay: false, defaults: { ease: "inOut(3)" } })
          .add(deliveryDraw, { draw: ["0 .12", "0 1"], duration: 1000 }, 0)
          .add(motion, { reveal: [0.12, 1], duration: 1000 }, 0)
          .add(motion, { position: deliveryEnd, duration: 900, ease: "linear" }, 1100)
          .add(motion, { position: testStop, duration: 850 }, 2150)
          .add(motion, { position: 0, duration: 850 }, 3150)
          .add(motion, { position: 1, duration: 950, ease: "linear" }, 4050)
          .add(reviewDraw, { draw: ["0 0", "0 1"], duration: 500 }, 4500);
        let frame = 0,
          lastTime = 0,
          target = 0,
          progress = 0,
          previousStage = -2;
        let visible = true;
        let anchors: number[] = [];
        let height = 0,
          introTop = 0,
          top = 0,
          introSize = 0,
          size = 0;
        const measure = () => {
          const width = element.clientWidth;
          height = element.clientHeight;
          const mobile = width < 800;
          const short = innerHeight <= 600;
          size = short
            ? 290
            : mobile
              ? Math.min(305, height * 0.4)
              : Math.min(470, width * 0.35, height * 0.68);
          introTop = short ? 20 : Math.max(mobile ? 370 : 320, height * 0.43);
          introSize = short
            ? size
            : Math.min(size, height * 0.36, Math.max(140, height - 160 - introTop));
          top = short ? 20 : mobile ? 12 : (height - size) * 0.43;

          anchors = [
            root.getBoundingClientRect().top + scrollY,
            ...Array.from(root.querySelectorAll<HTMLElement>("[data-chapter]")).map(
              (el) => el.getBoundingClientRect().top + scrollY - innerHeight * 0.08,
            ),
          ];
        };
        const readProgress = () => {
          target = 0;
          for (let i = 0; i < anchors.length - 1; i++) {
            if (scrollY >= anchors[i])
              target =
                i + Math.min(1, (scrollY - anchors[i]) / Math.max(1, anchors[i + 1] - anchors[i]));
          }
          const nextStage = Math.min(4, Math.max(-1, Math.floor(target + 0.5) - 1));
          if (nextStage !== previousStage) {
            previousStage = nextStage;
            onStageChange(nextStage);
            scrubber.setAttribute(
              "aria-valuetext",
              nextStage < 0 ? "Introduction" : chapterNames[nextStage],
            );
          }
          scrubber.value = String(target);
        };
        const draw = (time: number) => {
          frame = 0;
          if (!visible || document.hidden) return;
          const dt = Math.min((time - lastTime) / 1000 || 0.016, 0.05);
          lastTime = time;
          const reduced = preference.matches;
          progress = reduced ? target : progress + (target - progress) * (1 - Math.exp(-dt * 12));
          if (Math.abs(target - progress) < 0.001) progress = target;
          timeline.seek(progress * 1000, true);
          follower.seek(motion.position * 1000, true);
          const intro = 1 - Math.min(1, progress);
          const trackHeight = size + (introSize - size) * intro;
          track.style.width = `${(trackHeight * 400) / 470}px`;
          track.style.top = `${top + (introTop - top) * intro}px`;
          stops.forEach((stop, i) => {
            const reached = reduced || motion.reveal >= [0, 0.34, 0.65, 0.98][i];
            stop.dataset.reached = String(reached);
            // Controls stay available; the drawn line reveals the relationship between them.
          });
          element.dataset.renderer = reduced ? "static" : "svg";
          element.dataset.reducedMotion = String(reduced);
          element.dataset.progress = progress.toFixed(3);
          element.dataset.journey = Math.max(0, progress - 1).toFixed(3);
          element.dataset.branch = [
            "delivery",
            "delivery",
            "delivery",
            "reproduction",
            "investigation",
            "review",
          ][Math.min(5, Math.floor(progress + 0.5))];
          element.dataset.configuration = [
            "commit-on-track",
            "connected-track",
            "delivery-trace",
            "test-failure",
            "investigation",
            "review-request",
          ][Math.min(5, Math.floor(progress + 0.5))];
          const moving = !reduced && progress !== target;
          element.dataset.moving = String(moving);
          if (moving) frame = requestAnimationFrame(draw);
        };
        const requestDraw = () => {
          if (!frame && visible && !document.hidden) frame = requestAnimationFrame(draw);
        };
        const onScroll = () => {
          readProgress();
          requestDraw();
        };
        const onResize = () => {
          measure();
          onScroll();
        };
        const onVisibility = () => {
          if (document.hidden) {
            cancelAnimationFrame(frame);
            frame = 0;
          } else onScroll();
        };
        const observer = new IntersectionObserver(([entry]) => {
          visible = entry.isIntersecting;
          if (visible) onScroll();
          else {
            cancelAnimationFrame(frame);
            frame = 0;
          }
        });
        observer.observe(root);
        const resize = new ResizeObserver(onResize);
        resize.observe(element);
        resize.observe(root);
        window.addEventListener("scroll", onScroll, { passive: true });
        window.addEventListener("resize", onResize);
        document.addEventListener("visibilitychange", onVisibility);
        preference.addEventListener("change", onScroll);
        destroy = () => {
          cancelAnimationFrame(frame);
          timeline.revert();
          follower.revert();
          observer.disconnect();
          resize.disconnect();
          window.removeEventListener("scroll", onScroll);
          window.removeEventListener("resize", onResize);
          document.removeEventListener("visibilitychange", onVisibility);
          preference.removeEventListener("change", onScroll);
        };
        measure();
        readProgress();
        progress = target;
        requestDraw();
      })
      .catch(() => {
        element.dataset.renderer = "static";
      });
    return () => {
      cancelled = true;
      destroy();
    };
  }, [story, onStageChange]);

  return (
    <div className="core-renderer" ref={host} data-renderer="static" data-view={active}>
      <div className="svg-track">
        <svg
          className="track-art"
          viewBox="0 0 400 470"
          fill="none"
          role="img"
          aria-label="One commit connects a GitHub pull request, Actions build, JUnit tests and Sentry error. Follow the evidence back to the code, then request a review."
        >
          <path className="track-guide" d={fullPath} />
          <path className="track-line" data-delivery-route d={deliveryPath} />
          <path className="track-review-path" d={reviewPath} />
          <path data-motion-route d={fullPath} visibility="hidden" />
          <path data-test-route d={testPath} visibility="hidden" />
          <circle className="track-review-stop" cx="200" cy="440" r="5" />
          <g className="track-packet" style={{ transform: "translateX(80px) translateY(50px)" }}>
            <circle r="9" fill="var(--land-bg)" />
            <circle r="5" fill="var(--land-accent)" />
          </g>
        </svg>
        <TrackLabels active={active} selected={selected} onSelect={onSelect} />
      </div>
    </div>
  );
}
