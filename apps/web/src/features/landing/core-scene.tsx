"use client";

import { useEffect, useRef, type RefObject } from "react";
import { createChoreography } from "./core-choreography";
import { coreBackground, coreColors } from "./landing-palette";

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
  focus,
}: {
  story: RefObject<HTMLDivElement | null>;
  onStageChange: (stage: number) => void;
  focus: number;
}) {
  const host = useRef<HTMLDivElement>(null);
  const focusRef = useRef(focus);
  const invalidate = useRef<() => void>(() => {});
  useEffect(() => {
    focusRef.current = focus;
    invalidate.current();
  }, [focus]);

  useEffect(() => {
    const element = host.current;
    const root = story.current;
    if (!element || !root) return;
    let cancelled = false;
    let generation = 0;
    let destroy: (() => void) | undefined;
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    const stage = root.querySelector<HTMLElement>(".core-stage")!;
    const scrubber = root.querySelector<HTMLInputElement>("[data-story-scrubber]")!;
    const grip = element.querySelector<HTMLButtonElement>(".core-grip")!;
    const reset = root.querySelector<HTMLButtonElement>(".core-reset")!;
    const ports = Array.from(root.querySelectorAll<HTMLElement>("[data-core-port]"));
    const evidenceLabel = root.querySelector<HTMLElement>(".core-evidence-label")!;
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
      const [THREE, { createCore }, { createTimeline }, { RoomEnvironment }] = await Promise.all([
        import("three"),
        import("./core-model"),
        import("animejs"),
        import("three/addons/environments/RoomEnvironment.js"),
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
        ports.forEach((port) => port.removeAttribute("style"));
        stage.removeAttribute("style");
        delete stage.dataset.unfolded;
        evidenceLabel.removeAttribute("style");
        invalidate.current = () => {};
      };
      renderer.setClearColor(coreBackground);
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 0.95;
      const scene = new THREE.Scene();
      const camera = new THREE.OrthographicCamera(-8, 8, 6, -6, 0.1, 100);
      camera.position.set(0, 0, 16);
      const environment = new RoomEnvironment();
      const pmrem = new THREE.PMREMGenerator(renderer);
      const reflection = pmrem.fromScene(environment, 0.04);
      scene.environment = reflection.texture;
      environment.dispose();
      pmrem.dispose();
      disposables.push(reflection);
      scene.add(new THREE.HemisphereLight(0xffffff, 0x555555, 1));
      const key = new THREE.DirectionalLight(0xffffff, 2);
      key.position.set(-5, 6, 8);
      scene.add(key);
      const fill = new THREE.DirectionalLight(0xffffff, 1);
      fill.position.set(5, -2, -3);
      scene.add(fill);
      const core = createCore();
      scene.add(core.root);
      disposables.push(core);

      const { motion, parts, connect, trace, understand, investigate, complete } =
        createChoreography();
      const timeline = createTimeline({
        autoplay: false,
        defaults: { duration: 650, ease: "inOut(3)" },
      });
      const arrange = (layout: number[][], start: number, duration = 600) => {
        parts.forEach((part, i) =>
          timeline.add(
            part,
            {
              x: layout[i][0],
              y: layout[i][1],
              z: layout[i][2],
              size: layout[i][3],
              duration,
            },
            start + i * 35,
          ),
        );
      };
      // The optical payload stays identifiable while electronics and frame assemble around it.
      arrange(connect, 80, 650);
      timeline.add(
        motion,
        { reveal: 1, assembly: 0.65, spread: 1, lift: 0, scale: 0.95, duration: 900 },
        0,
      );
      arrange(trace, 1080, 600);
      timeline.add(motion, { assembly: 0.82, spread: 0.4, signal: 1, duration: 850 }, 1100);
      arrange(understand, 2050, 500);
      timeline.add(
        motion,
        { spread: 0.9, inspect: 0.85, aperture: 1, signal: 0.5, duration: 800 },
        2100,
      );
      arrange(investigate, 3060, 620);
      timeline.add(motion, { spread: 0.65, inspect: 1, signal: 0, duration: 850 }, 3100);
      arrange(complete, 4020, 600);
      timeline.add(
        motion,
        { spread: 0, inspect: 0, assembly: 1, aperture: 0.3, scale: 0.86, duration: 650 },
        4100,
      );
      timeline.add(motion, { deploy: 1, signal: 1, duration: 330 }, 4670);
      let frame = 0,
        lastTime = 0,
        target = 0,
        progress = 0;
      let pointerX = 0,
        pointerY = 0,
        rotationX = 0,
        rotationY = 0;
      let visible = true,
        contextLost = false,
        shaderFailed = false,
        previousStage = -2;
      let width = 0,
        height = 0,
        mobile = false,
        short = false;
      let anchors: number[] = [];
      let dragging = false,
        pointerId = -1,
        lastX = 0,
        lastY = 0;
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
        camera.left = (-6 * width) / Math.max(1, height);
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
        const damping = 1 - Math.exp(-dt * 10);
        progress += (target - progress) * damping;
        rotationX += (pointerX - rotationX) * damping;
        rotationY += (pointerY - rotationY) * damping;
        timeline.seek(progress * 1000, true);
        const reveal = motion.reveal;
        const lift = short ? 0.7 : mobile ? -1.8 + reveal * 4.35 : motion.lift;
        const scale = short
          ? 0.86
          : mobile
            ? (motion.scale + (1 - reveal) * 0.28) * (0.76 - reveal * 0.12)
            : motion.scale;
        core.root.position.set(0, lift, 0);
        core.root.scale.setScalar(scale);
        // One fixed technical view; rotation is exclusively a direct user action.
        core.root.rotation.set(0.58 + rotationY, 0.48 + rotationX, -0.12);
        core.layers.forEach(({ group }, i) => {
          const part = parts[i];
          group.position.set(part.x, part.y, part.z);
          group.scale.setScalar(part.size);
        });
        core.update(motion, focusRef.current);
        renderer.render(scene, camera);
        // DOM logos share scene coordinates, preserving crisp, undistorted source marks.
        ports.forEach((port, i) => {
          const side = i % 2 ? 1 : -1;
          const x = side * (mobile ? 2.2 : 3.3 - reveal * 0.32);
          const y = lift + (i < 2 ? 0.85 : -0.82) * (mobile ? 1 : 1.25);
          projected.set(x, y, 0);
          if (motion.reveal > 0.98) {
            projected.set(0, 0, 0);
            core.layers[i].port.localToWorld(projected);
          }
          projected.project(camera);
          const labelX =
            motion.reveal > 0.98
              ? width / 2 + side * (mobile ? 126 : Math.min(185, width * 0.135))
              : (projected.x * 0.5 + 0.5) * width;
          port.style.transform = `translate(${labelX}px,${(-projected.y * 0.5 + 0.5) * height}px) translate(-50%,-50%)`;
          port.style.setProperty("--port-label-offset", "27px");
          port.style.opacity = String(progress < 0.1 ? 1 : motion.reveal);
        });
        stage.dataset.unfolded = String(motion.reveal > 0.98);
        projected.set(0, 0, 0);
        core.layers[4].group.localToWorld(projected).project(camera);
        evidenceLabel.style.transform = `translate(${(projected.x * 0.5 + 0.5) * width}px,${(-projected.y * 0.5 + 0.5) * height}px) translate(-50%,-50%)`;
        stage.style.setProperty("--core-center", `${((1 - lift / 6) * height) / 2}px`);
        stage.style.setProperty("--story-progress", `${(progress / 5) * 100}%`);
        element!.dataset.progress = progress.toFixed(3);
        element!.dataset.rotation = rotationX.toFixed(3);
        element!.dataset.configuration =
          progress < 0.5
            ? "optical-payload"
            : progress < 1.5
              ? "connected-stack"
              : progress < 2.5
                ? "signal-bus"
                : progress < 3.5
                  ? "sensor-inspection"
                  : progress < 4.5
                    ? "payload-exploded"
                    : "satellite";
        element!.dataset.renderer = shaderFailed ? "fallback" : "webgl";
        const moving =
          Math.abs(target - progress) > 0.001 ||
          Math.abs(pointerX - rotationX) > 0.001 ||
          Math.abs(pointerY - rotationY) > 0.001;
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
      const onDown = (event: PointerEvent) => {
        if (event.button !== 0) return;
        dragging = true;
        pointerId = event.pointerId;
        lastX = event.clientX;
        lastY = event.clientY;
        grip.setPointerCapture(pointerId);
        grip.dataset.dragging = "true";
      };
      const onMove = (event: PointerEvent) => {
        if (!dragging || event.pointerId !== pointerId) return;
        pointerX = Math.max(-1.8, Math.min(1.8, pointerX + (event.clientX - lastX) * 0.008));
        pointerY = Math.max(-0.55, Math.min(0.55, pointerY + (event.clientY - lastY) * 0.006));
        lastX = event.clientX;
        lastY = event.clientY;
        requestDraw();
      };
      const onUp = () => {
        dragging = false;
        grip.dataset.dragging = "false";
      };
      const onKey = (event: KeyboardEvent) => {
        const delta = { ArrowLeft: -0.2, ArrowRight: 0.2 }[event.key];
        if (delta !== undefined) {
          event.preventDefault();
          pointerX = Math.max(-1.8, Math.min(1.8, pointerX + delta));
          requestDraw();
        }
        if (event.key === "Home") {
          event.preventDefault();
          pointerX = 0;
          pointerY = 0;
          requestDraw();
        }
      };
      const onReset = () => {
        pointerX = 0;
        pointerY = 0;
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
      // Source previews have different heights; their layout changes move every later chapter.
      resize.observe(root!);
      window.addEventListener("scroll", onScroll, { passive: true });
      window.addEventListener("resize", onResize);
      document.addEventListener("visibilitychange", onVisibility);
      grip.addEventListener("pointerdown", onDown);
      grip.addEventListener("pointermove", onMove);
      grip.addEventListener("pointerup", onUp);
      grip.addEventListener("pointercancel", onUp);
      grip.addEventListener("lostpointercapture", onUp);
      grip.addEventListener("keydown", onKey);
      reset.addEventListener("click", onReset);
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
        grip.removeEventListener("pointerdown", onDown);
        grip.removeEventListener("pointermove", onMove);
        grip.removeEventListener("pointerup", onUp);
        grip.removeEventListener("pointercancel", onUp);
        grip.removeEventListener("lostpointercapture", onUp);
        grip.removeEventListener("keydown", onKey);
        reset.removeEventListener("click", onReset);
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
    <div className="core-renderer" ref={host} data-renderer="static">
      <svg className="core-fallback" viewBox="0 0 500 440" fill="none" aria-hidden="true">
        <path
          d="M155 115 290 90 347 135 347 310 215 345 155 300Z"
          fill="#292725"
          stroke="#93908d"
          strokeWidth="5"
        />
        <path
          d="m155 115 60 45 132-25M215 160v185M290 90v180l57 40"
          stroke="#615e5b"
          strokeWidth="4"
        />
        <path
          d="m155 160-120 30 3 110 117-30m192-91 116-30 2 110-118 31"
          fill="#233f57"
          stroke="#93908d"
          strokeWidth="3"
        />
        <path
          d="m76 180 2 108m39-119 1 108m266-108 1 110m39-120 1 110M36 226l119-29m192 20 117-31M37 264l118-29m192 18 118-30"
          stroke="#4d9cff"
        />
        {[0, 1, 2, 3, 4].map((i) => (
          <path
            key={i}
            d={"M164 " + (155 + i * 32) + " 217 " + (190 + i * 32) + " 337 " + (163 + i * 32)}
            stroke={"#" + coreColors[i].toString(16).padStart(6, "0")}
            strokeWidth="3"
          />
        ))}
        <ellipse
          cx="247"
          cy="121"
          rx="39"
          ry="19"
          fill="#171615"
          stroke="#a39b91"
          strokeWidth="9"
        />
        <ellipse cx="247" cy="121" rx="22" ry="10" fill="#073b45" stroke="#05dbe9" />
        <path d="m247 100 0-45m0 12L116 47m131 20 129-34" stroke="#b18754" strokeWidth="3" />
      </svg>
      <button
        type="button"
        className="core-grip"
        aria-label="Rotate mechanical core. Drag or use left and right arrow keys."
      />
    </div>
  );
}
