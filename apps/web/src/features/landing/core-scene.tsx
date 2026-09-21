"use client";

import { useEffect, useRef, type RefObject } from "react";
import { createChoreography } from "./core-choreography";

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

      const { motion, parts, map, path, inspection } = createChoreography();
      const timeline = createTimeline({
        autoplay: false,
        defaults: { duration: 650, ease: "inOut(3)" },
      });
      const arrange = (layout: number[][], start: number, duration = 650) => {
        parts.forEach((part, i) =>
          timeline.add(
            part,
            {
              x: layout[i][0],
              y: layout[i][1],
              z: 0,
              size: layout[i][2],
              tilt: 1.32,
              duration,
            },
            start + i * 35,
          ),
        );
      };
      // Connect: withdraw the housing, then unfold the same five parts into a source map.
      timeline.add(motion, { open: 1, lift: 0.25, scale: 1.16, reveal: 1, duration: 800 }, 0);
      arrange(map, 180);
      timeline.add(motion, { links: 1, duration: 260 }, 740);
      // Trace: source modules become an ordered path; the signal follows its connections.
      arrange(path, 1000, 500);
      timeline.add(motion, { chain: 1, duration: 500 }, 1000);
      timeline.add(motion, { signal: 4, duration: 470, ease: "linear" }, 1530);
      // Understand: park the sources and physically open the evidence housing.
      arrange(inspection, 2000, 450);
      timeline.add(motion, { chain: 0, duration: 450 }, 2000);
      timeline.add(motion, { inspect: 1, duration: 450 }, 2500);
      // Investigate: close the inspected part, restore the path, follow it back to code.
      timeline.add(motion, { inspect: 0, duration: 250 }, 3000);
      arrange(path, 3230, 280);
      timeline.add(motion, { chain: 1, duration: 400 }, 3200);
      timeline.add(motion, { signal: 0, duration: 430, ease: "linear" }, 3570);
      // Automate: sources return to their original slots before the covers close.
      timeline.add(motion, { links: 0, duration: 220 }, 4000);
      parts.forEach((part, i) =>
        timeline.add(
          part,
          {
            x: 0,
            y: (i - 2) * 0.36,
            z: 0,
            size: 1,
            tilt: 0,
            duration: 500,
          },
          4120 + i * 65,
        ),
      );
      timeline.add(motion, { open: 0, scale: 1.3, duration: 380 }, 4620);
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
      const from = new THREE.Vector3();
      const to = new THREE.Vector3();
      const axis = new THREE.Vector3(0, 1, 0);
      const direction = new THREE.Vector3();
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
        // Orientation only changes when the housing unfolds. Chapters never spin the object.
        core.root.rotation.set(
          0.64 * (1 - motion.open) + rotationY,
          rotationX,
          -0.24 * (1 - motion.open),
        );
        core.layers.forEach(({ group, rotor, faceMaterial }, i) => {
          const part = parts[i];
          group.position.set(part.x, part.y, part.z);
          group.rotation.set(part.tilt, 0, 0);
          group.scale.setScalar(part.size);
          rotor.position.y = i === 4 ? motion.inspect * 0.55 : 0;
          faceMaterial.emissiveIntensity = focusRef.current === i ? 0.22 : 0;
        });
        core.housing.forEach((piece) => {
          piece.visible = motion.inspect < 0.001;
        });
        core.panels.forEach((panel, i) => {
          const angle = ((i + 0.5) * Math.PI) / 2;
          panel.visible = motion.inspect >= 0.001;
          panel.position.set(
            Math.cos(angle) * motion.inspect * 0.9,
            motion.inspect * 0.1,
            Math.sin(angle) * motion.inspect * 0.9,
          );
        });
        core.caps.forEach((cap, i) => {
          cap.position.set(0, (i ? 1 : -1) * (1.01 + motion.open * 2.3), -motion.open * 1.5);
          cap.scale.setScalar(Math.max(0.001, 1 - motion.open));
        });
        core.shaft.scale.setScalar(Math.max(0.001, 1 - motion.open));
        core.links.forEach((link, i) => {
          const source = parts[i];
          const hub = parts[4];
          const next = parts[Math.min(4, i + 1)];
          from.set(source.x, source.y, -0.08);
          to.set(
            THREE.MathUtils.lerp(hub.x, next.x, motion.chain),
            THREE.MathUtils.lerp(hub.y, next.y, motion.chain),
            -0.08,
          );
          direction.subVectors(to, from).normalize();
          const distance = from.distanceTo(to);
          const sourceRadius = Math.min(source.size * 1.62, distance * 0.45);
          const targetSize = THREE.MathUtils.lerp(hub.size, next.size, motion.chain);
          const targetRadius = Math.min(targetSize * 1.62, distance * 0.45);
          from.addScaledVector(direction, sourceRadius);
          to.addScaledVector(direction, -targetRadius);
          direction.subVectors(to, from);
          link.position.copy(from).add(to).multiplyScalar(0.5);
          link.scale.y = direction.length();
          link.quaternion.setFromUnitVectors(axis, direction.normalize());
          link.material.uniforms.uOpacity.value = motion.links;
          link.material.uniforms.uProgress.value = motion.signal;
          link.visible = motion.links > 0.001;
          if (Math.min(3, Math.floor(motion.signal)) === i) {
            core.marker.position.copy(from).lerp(to, Math.min(1, motion.signal - i));
            core.marker.position.z = 0.2;
          }
        });
        core.marker.visible = motion.links > 0.95 && motion.chain > 0.95;
        renderer.render(scene, camera);
        // Derive caption/control clearance from the rendered parts, at every screen size.
        const bottomOf = (object: InstanceType<typeof THREE.Object3D>, radius: number) => {
          let bottom = 0;
          for (let j = 0; j < 16; j++) {
            const angle = (j * Math.PI) / 8;
            projected.set(Math.cos(angle) * radius, 0, Math.sin(angle) * radius);
            object.localToWorld(projected).project(camera);
            bottom = Math.max(bottom, (-projected.y * 0.5 + 0.5) * height);
          }
          return bottom;
        };
        const moduleBottoms = core.layers.map(({ group }) => bottomOf(group, 1.7));
        // DOM logos share scene coordinates, preserving crisp, undistorted source marks.
        ports.forEach((port, i) => {
          const side = i % 2 ? 1 : -1;
          const x = side * (mobile ? 2.2 : 3.3 - reveal * 0.32);
          const y = lift + (i < 2 ? 0.85 : -0.82) * (mobile ? 1 : 1.25);
          projected.set(x, y, 0);
          if (motion.open > 0.98) {
            projected.set(0, 0, 0);
            core.layers[i].group.localToWorld(projected);
          }
          projected.project(camera);
          const centerY = (-projected.y * 0.5 + 0.5) * height;
          port.style.transform = `translate(${(projected.x * 0.5 + 0.5) * width}px,${(-projected.y * 0.5 + 0.5) * height}px) translate(-50%,-50%)`;
          port.style.setProperty("--port-label-offset", `${moduleBottoms[i] - centerY + 8}px`);
          port.style.opacity = String(progress < 0.1 ? 1 : motion.open);
        });
        stage.dataset.unfolded = String(motion.open > 0.98);
        projected.set(0, 0, 0);
        core.layers[4].group.localToWorld(projected).project(camera);
        evidenceLabel.style.transform = `translate(${(projected.x * 0.5 + 0.5) * width}px,${(-projected.y * 0.5 + 0.5) * height}px) translate(-50%,-50%)`;
        stage.style.setProperty("--core-center", `${((1 - lift / 6) * height) / 2}px`);
        stage.style.setProperty("--story-progress", `${(progress / 5) * 100}%`);
        element!.dataset.progress = progress.toFixed(3);
        element!.dataset.rotation = rotationX.toFixed(3);
        element!.dataset.configuration =
          motion.inspect > 0.95
            ? "inspection"
            : motion.open < 0.05
              ? "assembled"
              : motion.chain > 0.95
                ? "path"
                : "map";
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
    </div>
  );
}
