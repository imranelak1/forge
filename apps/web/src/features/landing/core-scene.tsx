"use client";

import { useEffect, useRef, type RefObject } from "react";
import { createChoreography } from "./core-choreography";
import { coreBackground, coreColors } from "./landing-palette";
import { DeliveryRecords } from "./delivery-records";
import "./delivery-records.css";

export const chapterNames = ["Connect", "Trace", "Understand", "Investigate", "Automate"];

export function seekStory(root: HTMLDivElement | null, progress: number) {
  if (!root) return;
  const points = [
    root.getBoundingClientRect().top + scrollY,
    ...Array.from(root.querySelectorAll<HTMLElement>("[data-chapter]")).map(
      (el) => el.getBoundingClientRect().top + scrollY - innerHeight * 0.08,
    ),
  ];
  const index = Math.min(4, Math.floor(progress));
  const fraction = Math.min(1, progress - index);
  scrollTo({
    top: points[index] + (points[index + 1] - points[index]) * fraction,
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
    let cancelled = false,
      generation = 0;
    let destroy: (() => void) | undefined;
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    const stage = root.querySelector<HTMLElement>(".core-stage")!;
    const scrubber = root.querySelector<HTMLInputElement>("[data-story-scrubber]")!;
    const records = Array.from(element.querySelectorAll<HTMLElement>("[data-record]"));
    const staticScroll = () => {
      if (element.dataset.renderer === "webgl") return;
      let active = -1;
      root.querySelectorAll<HTMLElement>("[data-chapter]").forEach((section, i) => {
        if (section.getBoundingClientRect().top < innerHeight * 0.5) active = i;
      });
      onStageChange(active);
      scrubber.value = String(active + 1);
      scrubber.setAttribute("aria-valuetext", active < 0 ? "Introduction" : chapterNames[active]);
    };
    window.addEventListener("scroll", staticScroll, { passive: true });

    async function initialize() {
      const version = ++generation;
      destroy?.();
      destroy = undefined;
      element!.dataset.renderer = preference.matches ? "static" : "loading";
      element!.dataset.reducedMotion = String(preference.matches);
      staticScroll();
      if (preference.matches) return;
      const [THREE, { createCore }, { createTimeline }] = await Promise.all([
        import("three"),
        import("./core-model"),
        import("animejs"),
      ]);
      if (cancelled || version !== generation) return;
      let renderer: InstanceType<typeof THREE.WebGLRenderer>;
      try {
        renderer = new THREE.WebGLRenderer({
          antialias: true,
          alpha: false,
          powerPreference: "low-power",
        });
      } catch {
        element!.dataset.renderer = "fallback";
        return;
      }
      const canvas = renderer.domElement;
      canvas.setAttribute("aria-hidden", "true");
      element!.appendChild(canvas);
      const disposables: { dispose(): void }[] = [];
      let stop = () => {};
      destroy = () => {
        stop();
        disposables.forEach((item) => item.dispose());
        renderer.dispose();
        renderer.forceContextLoss();
        canvas.remove();
        records.forEach((record) => {
          record.removeAttribute("style");
          record.inert = false;
        });
        stage.removeAttribute("style");
      };
      renderer.setClearColor(coreBackground);
      const scene = new THREE.Scene();
      const camera = new THREE.OrthographicCamera(-8, 8, 6, -6, 0.1, 100);
      camera.position.set(0, 0, 16);
      const core = createCore();
      scene.add(core.root);
      disposables.push(core);
      const { motion, parts, layouts } = createChoreography();
      const timeline = createTimeline({
        autoplay: false,
        defaults: { duration: 650, ease: "inOut(3)" },
      });
      layouts.forEach((layout, step) => {
        parts.forEach((part, i) =>
          timeline.add(
            part,
            {
              x: layout[i][0],
              y: layout[i][1],
              width: layout[i][2],
              height: layout[i][3],
              opacity: 1,
              duration: 720,
            },
            step * 1000 + 70 + i * 28,
          ),
        );
        if (step) timeline.add(motion, { route: step, duration: 800 }, step * 1000 + 70);
      });
      timeline.add(motion, { reveal: 1, lift: 0, links: 1, duration: 950 }, 0);
      timeline.add(motion, { signal: 4, duration: 900 }, 1100);
      timeline.add(motion, { signal: 0, duration: 800 }, 3100);
      // Preserve the final hold so seeking 5 maps to the complete review request.
      timeline.add(motion, { scale: 1, duration: 100 }, 4900);
      let frame = 0,
        lastTime = 0,
        target = 0,
        progress = 0;
      let visible = true,
        contextLost = false,
        shaderFailed = false,
        previousStage = -2;
      let width = 0,
        height = 0,
        mobile = false,
        short = false;
      let anchors: number[] = [];
      let viewHeight = 12;
      const projected = new THREE.Vector3();
      renderer.debug.onShaderError = () => {
        shaderFailed = true;
        element!.dataset.renderer = "fallback";
      };
      const measure = () => {
        width = element!.clientWidth;
        height = element!.clientHeight;
        mobile = width < 800;
        short = innerHeight <= 600;
        viewHeight = short ? 7.5 : 12;
        camera.top = viewHeight / 2;
        camera.bottom = -viewHeight / 2;
        camera.left = ((-viewHeight / 2) * width) / Math.max(1, height);
        camera.right = -camera.left;
        camera.updateProjectionMatrix();
        renderer.setPixelRatio(Math.min(devicePixelRatio, mobile ? 1.25 : 1.6));
        renderer.setSize(width, height, false);
        anchors = [
          root!.getBoundingClientRect().top + scrollY,
          ...Array.from(root!.querySelectorAll<HTMLElement>("[data-chapter]")).map(
            (el) => el.getBoundingClientRect().top + scrollY - innerHeight * 0.08,
          ),
        ];
      };
      const readProgress = () => {
        target = 0;
        for (let i = 0; i < anchors.length - 1; i++)
          if (scrollY >= anchors[i])
            target =
              i +
              Math.max(
                0,
                Math.min(1, (scrollY - anchors[i]) / Math.max(1, anchors[i + 1] - anchors[i])),
              );
        target = Math.min(5, target);
        const active = Math.min(4, Math.max(-1, Math.floor(target + 0.5) - 1));
        if (active !== previousStage) {
          previousStage = active;
          onStageChange(active);
          scrubber.setAttribute(
            "aria-valuetext",
            active < 0 ? "Introduction" : chapterNames[active],
          );
        }
        scrubber.value = String(target);
      };
      const draw = (time: number) => {
        frame = 0;
        if (!visible || document.hidden || contextLost || shaderFailed) return;
        const dt = Math.min((time - lastTime) / 1000 || 0.016, 0.05);
        lastTime = time;
        progress += (target - progress) * (1 - Math.exp(-dt * 10));
        timeline.seek(progress * 1000, true);
        const lift = short ? 0.3 : mobile ? -1.85 + motion.reveal * 4.75 : motion.lift;
        const scale = short
          ? 0.95
          : mobile
            ? 0.95 - motion.reveal * 0.09
            : Math.min(1.15, (width * 0.3) / ((5.4 * height) / 12));
        core.root.position.set(0, lift, 0);
        core.root.scale.setScalar(scale);
        core.update(parts, motion.route, motion.links, motion.signal);
        renderer.render(scene, camera);
        core.root.updateMatrixWorld();
        records.forEach((record, i) => {
          const part = parts[i];
          projected.set(part.x, part.y, 0);
          core.root.localToWorld(projected).project(camera);
          record.style.transform = `translate3d(${(projected.x * 0.5 + 0.5) * width}px,${(-projected.y * 0.5 + 0.5) * height}px,0) translate(-50%,-50%)`;
          record.style.width = `${((part.width * height) / viewHeight) * scale}px`;
          record.style.height = `${((part.height * height) / viewHeight) * scale}px`;
          record.style.opacity = String(part.opacity);
          record.inert = part.opacity < 0.95;
        });
        stage.style.setProperty("--story-progress", `${(progress / 5) * 100}%`);
        element!.dataset.progress = progress.toFixed(3);
        element!.dataset.configuration = [
          "pull-request",
          "linked-sources",
          "delivery-trace",
          "test-failure",
          "investigation",
          "review-request",
        ][Math.min(5, Math.floor(progress + 0.5))];
        element!.dataset.renderer = shaderFailed ? "fallback" : "webgl";
        const moving = Math.abs(target - progress) > 0.001;
        element!.dataset.moving = String(moving);
        if (moving) frame = requestAnimationFrame(draw);
      };
      const requestDraw = () => {
        if (!frame && visible && !document.hidden && !contextLost)
          frame = requestAnimationFrame(draw);
      };
      const onScroll = () => {
        readProgress();
        requestDraw();
      };
      const onResize = () => {
        measure();
        readProgress();
        requestDraw();
      };
      const onVisibility = () => {
        if (document.hidden) {
          cancelAnimationFrame(frame);
          frame = 0;
        } else onScroll();
      };
      const lost = (event: Event) => {
        event.preventDefault();
        contextLost = true;
        cancelAnimationFrame(frame);
        frame = 0;
        element!.dataset.renderer = "fallback";
      };
      const restored = () => {
        contextLost = false;
        requestDraw();
      };
      const observer = new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
        if (visible) requestDraw();
        else {
          cancelAnimationFrame(frame);
          frame = 0;
        }
      });
      observer.observe(root!);
      const resize = new ResizeObserver(onResize);
      resize.observe(element!);
      resize.observe(root!);
      window.addEventListener("scroll", onScroll, { passive: true });
      window.addEventListener("resize", onResize);
      document.addEventListener("visibilitychange", onVisibility);
      canvas.addEventListener("webglcontextlost", lost);
      canvas.addEventListener("webglcontextrestored", restored);
      stop = () => {
        cancelAnimationFrame(frame);
        timeline.revert();
        observer.disconnect();
        resize.disconnect();
        window.removeEventListener("scroll", onScroll);
        window.removeEventListener("resize", onResize);
        document.removeEventListener("visibilitychange", onVisibility);
        canvas.removeEventListener("webglcontextlost", lost);
        canvas.removeEventListener("webglcontextrestored", restored);
      };
      measure();
      readProgress();
      progress = target;
      requestDraw();
    }
    const configure = () => {
      void initialize().catch(() => {
        if (!cancelled) {
          destroy?.();
          destroy = undefined;
          element.dataset.renderer = "fallback";
        }
      });
    };
    configure();
    preference.addEventListener("change", configure);
    return () => {
      cancelled = true;
      generation++;
      window.removeEventListener("scroll", staticScroll);
      preference.removeEventListener("change", configure);
      destroy?.();
    };
  }, [story, onStageChange]);

  return (
    <div className="core-renderer" ref={host} data-renderer="static" data-view={active}>
      <DeliveryRecords active={active} selected={selected} onSelect={onSelect} />
      <svg
        className="core-fallback"
        viewBox="0 0 500 380"
        fill="none"
        role="img"
        aria-label="Example delivery: pull request 184 connects to CI run 928, its tests and a checkout production error through commit 8f3a2c1."
      >
        <path d="M250 62V320" stroke="#85827e" strokeWidth="2" />
        {[
          "GitHub · PR #184",
          "Actions · CI #928 passed",
          "JUnit · 3 tests passed",
          "Sentry · checkout error",
        ].map((label, i) => (
          <g key={label}>
            <rect
              x="78"
              y={22 + i * 88}
              width="344"
              height="64"
              rx="3"
              fill="#2a2928"
              stroke={"#" + coreColors[i].toString(16).padStart(6, "0")}
            />
            <circle
              cx="104"
              cy={54 + i * 88}
              r="4"
              fill={"#" + coreColors[i].toString(16).padStart(6, "0")}
            />
            <text x="125" y={60 + i * 88} fill="#f6f4f2" fontSize="17" fontFamily="monospace">
              {label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
