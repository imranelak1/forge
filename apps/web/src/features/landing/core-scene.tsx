"use client";

import { useEffect, useRef, type RefObject } from "react";
import { RotateCcw } from "lucide-react";

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
    const reset = element.querySelector<HTMLButtonElement>(".core-reset")!;
    const ports = Array.from(root.querySelectorAll<HTMLElement>("[data-core-port]"));
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
        invalidate.current = () => {};
      };
      renderer.setClearColor(0xfafafa);
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

      const motion = {
        spread: 0.36,
        rx: 0.64,
        ry: -0.35,
        rz: -0.42,
        lift: -1.65,
        scale: 1.18,
        turn: 0,
        signal: 0,
        reveal: 0,
      };
      const timeline = createTimeline({
        autoplay: false,
        defaults: { duration: 1000, ease: "inOut(3)" },
      });
      const poses = [
        {
          spread: 0.62,
          rx: 0.78,
          ry: 0.3,
          rz: -0.27,
          lift: 0.2,
          scale: 1.34,
          turn: 0.45,
          signal: 2,
          reveal: 1,
        },
        {
          spread: 0.48,
          rx: 1.05,
          ry: -0.35,
          rz: 0.2,
          lift: 0.25,
          scale: 1.3,
          turn: 1.8,
          signal: 8,
          reveal: 1,
        },
        {
          spread: 0.98,
          rx: 0.58,
          ry: 0.45,
          rz: -0.32,
          lift: 0.2,
          scale: 1.04,
          turn: 2.65,
          signal: 12,
          reveal: 1,
        },
        {
          spread: 0.81,
          rx: 0.76,
          ry: -0.5,
          rz: 0.27,
          lift: 0.2,
          scale: 1.13,
          turn: 1.4,
          signal: 4,
          reveal: 1,
        },
        {
          spread: 0.36,
          rx: 1.13,
          ry: 0,
          rz: 0,
          lift: 0.2,
          scale: 1.5,
          turn: 3.2,
          signal: 14,
          reveal: 1,
        },
      ];
      poses.forEach((pose, i) =>
        timeline.label(chapterNames[i], i * 1000).add(motion, pose, i * 1000),
      );
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
        const scale = short ? 0.86 : motion.scale * (mobile ? 0.76 - reveal * 0.12 : 1);
        core.root.position.set(0, lift, 0);
        core.root.scale.setScalar(scale);
        core.root.rotation.set(motion.rx + rotationY, motion.ry + rotationX, motion.rz);
        core.layers.forEach(({ group, rotor, face }, i) => {
          group.position.y = (i - 2) * motion.spread;
          group.rotation.y = motion.turn * (i % 2 ? -0.6 : 0.6);
          rotor.rotation.y = motion.turn * (i % 2 ? 1.7 : -1.7);
          const focused = focusRef.current === i;
          face.scale.setScalar(focused ? 1.035 : 1);
          group.position.x = focused ? 0.13 : 0;
        });
        core.caps.forEach((cap, i) => {
          cap.position.y = (i ? 1 : -1) * (motion.spread * 2 + 0.29 + reveal * 0.12);
        });
        core.shaft.scale.y = (motion.spread * 4 + 0.5) / 2.2;
        core.signalMaterial.uniforms.uTravel.value = motion.signal;
        core.signalMaterial.uniforms.uIntensity.value = progress > 1 ? 1 : 0.35;
        camera.zoom = 1 + Math.sin((progress * Math.PI) / 5) * 0.035;
        camera.updateProjectionMatrix();
        renderer.render(scene, camera);
        // DOM logos share scene coordinates, preserving crisp, undistorted source marks.
        ports.forEach((port, i) => {
          const side = i % 2 ? 1 : -1;
          const x = side * (mobile ? 2.2 : 3.3 - reveal * 0.32);
          const y = lift + (i < 2 ? 0.85 : -0.82) * (mobile ? 1 : 1.25);
          projected.set(x, y, 0).project(camera);
          port.style.transform = `translate(${(projected.x * 0.5 + 0.5) * width}px,${(-projected.y * 0.5 + 0.5) * height}px) translate(-50%,-50%)`;
        });
        stage.style.setProperty("--core-center", `${((1 - lift / 6) * height) / 2}px`);
        stage.style.setProperty("--story-progress", `${(progress / 5) * 100}%`);
        element!.dataset.progress = progress.toFixed(3);
        element!.dataset.rotation = rotationX.toFixed(3);
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
        <path d="M250 95v255" stroke="#999" strokeWidth="32" />
        {[0, 1, 2, 3, 4].map((i) => (
          <g key={i} transform={`translate(250 ${110 + i * 50}) rotate(-16)`}>
            <ellipse cy="12" rx="125" ry="42" fill="#292929" stroke="#111" />
            <ellipse
              rx="125"
              ry="42"
              fill={i % 2 ? "#bbb" : "#eee"}
              stroke="#333"
              strokeWidth="2"
            />
            <ellipse rx="110" ry="35" stroke="#777" strokeDasharray="2 5" />
            <ellipse rx="43" ry="15" fill="#333" stroke="#111" />
          </g>
        ))}
      </svg>
      <button
        type="button"
        className="core-grip"
        aria-label="Rotate mechanical core. Drag or use left and right arrow keys."
      />
      <button type="button" className="core-reset" aria-label="Reset core rotation">
        <RotateCcw size={13} aria-hidden="true" />
        <span>Drag to rotate · Reset</span>
      </button>
    </div>
  );
}
