"use client";

import { useEffect, useRef, type RefObject } from "react";
import {
  backgroundFragmentShader,
  backgroundVertexShader,
  cableFragmentShader,
  cableVertexShader,
} from "./cable-shaders";

export const chapterNames = ["Connect", "Trace", "Understand", "Investigate", "Automate"];

export function CableScene({
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
    let destroyScene: (() => void) | undefined;
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    let generation = 0;
    const updateStatic = () => {
      if (element.dataset.renderer === "webgl") return;
      let stage = -1;
      root.querySelectorAll<HTMLElement>("[data-chapter]").forEach((chapter, i) => {
        if (chapter.getBoundingClientRect().top < innerHeight * 0.5) stage = i;
      });
      onStageChange(stage);
    };
    window.addEventListener("scroll", updateStatic, { passive: true });

    async function initialize() {
      const currentGeneration = ++generation;
      destroyScene?.();
      destroyScene = undefined;
      element!.dataset.renderer = preference.matches ? "static" : "loading";
      element!.dataset.reducedMotion = String(preference.matches);
      updateStatic();
      if (preference.matches) return;
      const THREE = await import("three");
      if (cancelled || generation !== currentGeneration) return;
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
      const disposables: { dispose: () => void }[] = [];
      let stop = () => {};
      destroyScene = () => {
        stop();
        disposables.forEach((resource) => resource.dispose());
        renderer.dispose();
        renderer.forceContextLoss();
        canvas.remove();
        invalidate.current = () => {};
      };
      canvas.setAttribute("aria-hidden", "true");
      element!.appendChild(canvas);
      const scene = new THREE.Scene();
      const camera = new THREE.OrthographicCamera(-8, 8, 6, -6, 0.1, 100);
      camera.position.z = 12;
      const uniforms = {
        uProgress: { value: 0 },
        uMobile: { value: 0 },
        uPointer: { value: 0 },
        uFocus: { value: -1 },
      };
      const material = new THREE.ShaderMaterial({
        vertexShader: cableVertexShader,
        fragmentShader: cableFragmentShader,
        uniforms,
        side: THREE.DoubleSide,
      });
      const longitudinal = 220;
      disposables.push(material);
      const radial = 12;
      const vertexCount = 5 * (longitudinal + 1) * (radial + 1);
      const positions = new Float32Array(vertexCount * 3);
      const uvs = new Float32Array(vertexCount * 2);
      const strands = new Float32Array(vertexCount);
      const indices: number[] = [];
      let vertex = 0;
      for (let strand = 0; strand < 5; strand++) {
        const base = vertex;
        for (let i = 0; i <= longitudinal; i++)
          for (let j = 0; j <= radial; j++) {
            uvs[vertex * 2] = i / longitudinal;
            uvs[vertex * 2 + 1] = j / radial;
            strands[vertex] = strand;
            vertex++;
          }
        for (let i = 0; i < longitudinal; i++)
          for (let j = 0; j < radial; j++) {
            const a = base + i * (radial + 1) + j;
            const b = a + radial + 1;
            indices.push(a, b, a + 1, b, b + 1, a + 1);
          }
      }
      const geometry = new THREE.BufferGeometry();
      disposables.push(geometry);
      geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      geometry.setAttribute("uv", new THREE.BufferAttribute(uvs, 2));
      geometry.setAttribute("aStrand", new THREE.BufferAttribute(strands, 1));
      geometry.setIndex(indices);
      const cable = new THREE.Mesh(geometry, material);
      cable.frustumCulled = false;
      scene.add(cable);
      const backgroundGeometry = new THREE.PlaneGeometry(2, 2);
      disposables.push(backgroundGeometry);
      const backgroundMaterial = new THREE.ShaderMaterial({
        vertexShader: backgroundVertexShader,
        fragmentShader: backgroundFragmentShader,
        depthWrite: false,
        depthTest: false,
      });
      const background = new THREE.Mesh(backgroundGeometry, backgroundMaterial);
      disposables.push(backgroundMaterial);
      background.frustumCulled = false;
      background.renderOrder = -1;
      scene.add(background);
      let shaderFailed = false;
      renderer.debug.onShaderError = (gl, _program, vertexShader, fragmentShader) => {
        shaderFailed = true;
        console.warn(
          "Forge cable shader unavailable",
          gl.getShaderInfoLog(vertexShader),
          gl.getShaderInfoLog(fragmentShader),
        );
      };
      renderer.compile(scene, camera);
      let frame = 0;
      let lastTime = 0;
      let target = 0;
      let pointer = 0;
      let visible = true;
      let contextLost = false;
      let previousStage = -2;
      let anchors: number[] = [];

      const measure = () => {
        const width = element!.clientWidth;
        const height = element!.clientHeight;
        camera.left = (-6 * width) / Math.max(1, height);
        camera.right = -camera.left;
        camera.updateProjectionMatrix();
        renderer.setPixelRatio(Math.min(devicePixelRatio, width < 800 ? 1.25 : 1.75));
        renderer.setSize(width, height, false);
        uniforms.uMobile.value = width < 800 ? 1 : 0;
        anchors = [
          root!.getBoundingClientRect().top + scrollY,
          ...Array.from(root!.querySelectorAll<HTMLElement>("[data-chapter]")).map(
            (item) => item.getBoundingClientRect().top + scrollY - innerHeight * 0.08,
          ),
        ];
      };
      const readProgress = () => {
        const y = scrollY;
        let value = 0;
        for (let i = 0; i < anchors.length - 1; i++) {
          if (y >= anchors[i])
            value =
              i +
              Math.max(0, Math.min(1, (y - anchors[i]) / Math.max(1, anchors[i + 1] - anchors[i])));
        }
        target = Math.min(5, value);
        const stage = Math.min(4, Math.max(-1, Math.floor(target + 0.5) - 1));
        if (stage !== previousStage) {
          previousStage = stage;
          onStageChange(stage);
        }
      };
      const draw = (time: number) => {
        frame = 0;
        if (!visible || document.hidden || contextLost || shaderFailed) return;
        const delta = Math.min((time - lastTime) / 1000 || 0.016, 0.05);
        lastTime = time;
        const damping = 1 - Math.exp(-delta * 9);
        uniforms.uProgress.value += (target - uniforms.uProgress.value) * damping;
        uniforms.uPointer.value += (pointer - uniforms.uPointer.value) * damping;
        uniforms.uFocus.value = focusRef.current;
        renderer.render(scene, camera);
        element!.dataset.progress = uniforms.uProgress.value.toFixed(3);
        element!.dataset.renderer = shaderFailed ? "fallback" : "webgl";
        const moving =
          Math.abs(target - uniforms.uProgress.value) > 0.001 ||
          Math.abs(pointer - uniforms.uPointer.value) > 0.001;
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
      const onPointer = (event: PointerEvent) => {
        if (event.pointerType === "mouse") {
          pointer = (event.clientX / innerWidth - 0.5) * 2;
          requestDraw();
        }
      };
      const onVisibility = () => {
        if (document.hidden) {
          cancelAnimationFrame(frame);
          frame = 0;
        } else {
          readProgress();
          requestDraw();
        }
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
      const resizeObserver = new ResizeObserver(onResize);
      resizeObserver.observe(element!);
      window.addEventListener("scroll", onScroll, { passive: true });
      window.addEventListener("pointermove", onPointer, { passive: true });
      window.addEventListener("resize", onResize);
      document.addEventListener("visibilitychange", onVisibility);
      canvas.addEventListener("webglcontextlost", lost);
      canvas.addEventListener("webglcontextrestored", restored);
      measure();
      readProgress();
      uniforms.uProgress.value = target;
      requestDraw();
      if (shaderFailed) element!.dataset.renderer = "fallback";

      stop = () => {
        cancelAnimationFrame(frame);
        observer.disconnect();
        resizeObserver.disconnect();
        window.removeEventListener("scroll", onScroll);
        window.removeEventListener("resize", onResize);
        window.removeEventListener("pointermove", onPointer);
        document.removeEventListener("visibilitychange", onVisibility);
        canvas.removeEventListener("webglcontextlost", lost);
        canvas.removeEventListener("webglcontextrestored", restored);
      };
    }
    const configure = () => {
      void initialize().catch(() => {
        if (!cancelled) {
          destroyScene?.();
          destroyScene = undefined;
          element.dataset.renderer = "fallback";
        }
      });
    };
    configure();
    preference.addEventListener("change", configure);
    return () => {
      cancelled = true;
      generation++;
      window.removeEventListener("scroll", updateStatic);
      preference.removeEventListener("change", configure);
      destroyScene?.();
    };
  }, [story, onStageChange]);

  return (
    <div className="cable-renderer" ref={host} data-renderer="static" aria-hidden="true">
      <svg className="cable-fallback" viewBox="0 0 600 800" fill="none">
        {[0, 1, 2, 3, 4].map((i) => (
          <path
            key={i}
            d={`M${180 + i * 55} 150 C${490 - i * 25} 270 ${90 + i * 23} 305 ${280 + i * 10} 420 S${480 - i * 37} 580 ${250 + i * 18} 690`}
            stroke={i % 2 ? "#777" : "#191919"}
            strokeWidth="8"
            strokeLinecap="round"
          />
        ))}
      </svg>
    </div>
  );
}
