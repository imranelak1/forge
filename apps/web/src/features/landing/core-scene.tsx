"use client";

import { useEffect, useRef, type RefObject } from "react";
import { createChoreography } from "./core-choreography";
import { coreBackground } from "./landing-palette";
import { TrackLabels, TrackFallback } from "./track-labels";
import "./track-labels.css";

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
  const selectedRef = useRef(selected);
  const invalidate = useRef(() => {});
  useEffect(() => {
    selectedRef.current = selected;
    invalidate.current();
  }, [selected]);
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
    const stops = Array.from(element.querySelectorAll<HTMLElement>("[data-checkpoint]"));
    const packetLabel = element.querySelector<HTMLElement>(".track-packet-label")!;
    const detail = element.querySelector<HTMLElement>(".track-detail")!;
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
        stops.forEach((stop) => {
          stop.removeAttribute("style");
          stop.inert = false;
        });
        packetLabel.removeAttribute("style");
        detail.removeAttribute("style");
        invalidate.current = () => {};
        stage.removeAttribute("style");
      };
      renderer.setClearColor(coreBackground);
      const scene = new THREE.Scene();
      scene.add(new THREE.HemisphereLight(0xffffff, 0x5a5149, 2.2));
      const key = new THREE.DirectionalLight(0xfff5e4, 4);
      key.position.set(-3, 5, 8);
      scene.add(key);
      const fill = new THREE.DirectionalLight(0xffffff, 2);
      fill.position.set(4, -2, 5);
      scene.add(fill);
      const camera = new THREE.OrthographicCamera(-8, 8, 6, -6, 0.1, 100);
      camera.position.set(0, 0, 16);
      const core = createCore();
      scene.add(core.root);
      disposables.push(core);
      const { motion } = createChoreography();
      const timeline = createTimeline({
        autoplay: false,
        defaults: { duration: 650, ease: "inOut(3)" },
      });
      timeline.add(motion, { reveal: 1, lift: 0, track: 1, duration: 960 }, 0);
      timeline.add(motion, { journey: 0.06, duration: 900 }, 0);
      timeline.add(motion, { journey: 1, duration: 970, ease: "linear" }, 1000);
      timeline.add(motion, { inspection: 1, duration: 530 }, 2010);
      timeline.add(motion, { labels: 1, duration: 420 }, 2000);
      timeline.add(motion, { journey: 2, duration: 690, ease: "linear" }, 2280);
      timeline.add(motion, { investigation: 1, duration: 530 }, 3010);
      timeline.add(motion, { journey: 3, duration: 690, ease: "linear" }, 3280);
      timeline.add(motion, { review: 1, duration: 560 }, 4010);
      timeline.add(motion, { switch: 1, duration: 180 }, 4110);
      timeline.add(motion, { journey: 4, duration: 690, ease: "linear" }, 4310);
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
        const lift = short ? 0.25 : mobile ? -2.1 + motion.reveal * 5.3 : motion.lift;
        const scale = short
          ? 0.86
          : mobile
            ? 0.72 - motion.reveal * 0.04
            : (0.7 + motion.reveal * 0.3) *
              Math.min(1.05, (width * (width < 1100 ? 0.27 : 0.3)) / ((5.6 * height) / 12));
        core.root.position.set(0, lift, 0);
        core.root.scale.setScalar(scale);
        core.root.rotation.set(0.35, -0.16, -0.07);
        core.update(motion, selectedRef.current);
        renderer.render(scene, camera);
        core.root.updateMatrixWorld();
        const place = (
          node: HTMLElement,
          point: InstanceType<typeof THREE.Vector3>,
          x = 0,
          y = 0,
        ) => {
          projected.copy(point);
          core.root.localToWorld(projected).project(camera);
          node.style.transform = `translate3d(${(projected.x * 0.5 + 0.5) * width + x}px,${(-projected.y * 0.5 + 0.5) * height + y}px,0) translate(-50%,-50%)`;
        };
        stops.forEach((stop, i) => {
          const visible = i === 0 || motion.reveal > (i + 1) * 0.2;
          const label = core.stations[i].label
            .clone()
            .lerp(new THREE.Vector3((i - 1.5) * 1.1, mobile ? 3.5 : 3.8, 0.25), motion.labels);
          place(stop, label);
          const baseWidth = width < 1100 ? 99 : 112;
          stop.style.width = `${baseWidth + (44 - baseWidth) * motion.labels}px`;
          stop.style.setProperty("--label-detail", String(1 - motion.labels));
          stop.dataset.compact = String(motion.labels > 0.7);
          stop.style.opacity = String(visible ? 1 : 0);
          stop.inert = !visible;
        });
        place(packetLabel, core.packet, 35, -20);
        packetLabel.style.opacity = String(
          progress < 0.5 || (progress > 1.05 && progress < 1.95) ? 1 : 0,
        );
        place(detail, new THREE.Vector3(0, -3.55, 0), 0, 6);
        element!.dataset.journey = motion.journey.toFixed(3);
        element!.dataset.branch =
          motion.journey <= 1
            ? "delivery"
            : motion.journey <= 2
              ? "reproduction"
              : motion.journey <= 3
                ? "investigation"
                : "review";
        stage.style.setProperty("--story-progress", `${(progress / 5) * 100}%`);
        element!.dataset.progress = progress.toFixed(3);
        element!.dataset.configuration = [
          "commit-on-track",
          "connected-track",
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
      invalidate.current = requestDraw;
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
      <TrackLabels active={active} selected={selected} onSelect={onSelect} />
      <TrackFallback />
    </div>
  );
}
