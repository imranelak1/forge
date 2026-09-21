import * as THREE from "three";
import { coreColors } from "./landing-palette";
import type { DeliveryPart } from "./core-choreography";

/** WebGL carries only the delivery relationships; readable records are native HTML. */
export function createCore() {
  const root = new THREE.Group();
  const resources: { dispose(): void }[] = [];
  const keep = <T extends { dispose(): void }>(item: T) => {
    resources.push(item);
    return item;
  };
  const routes = [
    [
      [4, 0],
      [4, 1],
      [4, 2],
      [4, 3],
    ],
    [
      [0, 1],
      [1, 2],
      [2, 3],
      [3, 4],
    ],
    [
      [0, 2],
      [1, 2],
      [2, 3],
      [2, 4],
    ],
    [
      [3, 0],
      [2, 0],
      [1, 0],
      [0, 4],
    ],
    [
      [0, 4],
      [1, 4],
      [2, 4],
      [3, 4],
    ],
  ];
  const links = Array.from({ length: 4 }, (_, i) => {
    const vertices = new Float32Array(49 * 3);
    const along = Float32Array.from({ length: 49 }, (_, n) => n / 48);
    const geometry = keep(new THREE.BufferGeometry());
    geometry.setAttribute("position", new THREE.BufferAttribute(vertices, 3));
    geometry.setAttribute("aAlong", new THREE.BufferAttribute(along, 1));
    const material = keep(
      new THREE.ShaderMaterial({
        transparent: true,
        toneMapped: false,
        uniforms: {
          uColor: { value: new THREE.Color(coreColors[i]) },
          uOpacity: { value: 0 },
          uSignal: { value: 0 },
        },
        vertexShader: `attribute float aAlong;varying float vAlong;void main(){vAlong=aAlong;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
        fragmentShader: `varying float vAlong;uniform vec3 uColor;uniform float uOpacity;uniform float uSignal;
      void main(){float pulse=1.-smoothstep(.02,.18,abs(vAlong-uSignal));gl_FragColor=vec4(mix(uColor,vec3(1.),pulse),uOpacity);
      #include <colorspace_fragment>
      }`,
      }),
    );
    const line = new THREE.Line(geometry, material);
    line.frustumCulled = false;
    root.add(line);
    return { geometry, material, vertices, curve: new THREE.CubicBezierCurve3() };
  });
  const marker = new THREE.Mesh(
    keep(new THREE.SphereGeometry(0.048, 12, 8)),
    keep(new THREE.MeshBasicMaterial({ color: 0xf6f4f2, toneMapped: false })),
  );
  root.add(marker);
  const point = new THREE.Vector3();
  return {
    root,
    update(parts: DeliveryPart[], route: number, opacity: number, signal: number) {
      const index = Math.min(4, Math.floor(route)),
        next = Math.min(4, index + 1),
        mix = route - index;
      links.forEach((link, i) => {
        const a = routes[index][i],
          b = routes[next][i];
        const from = parts[a[0]],
          fromNext = parts[b[0]],
          to = parts[a[1]],
          toNext = parts[b[1]];
        link.curve.v0.set(
          THREE.MathUtils.lerp(from.x, fromNext.x, mix),
          THREE.MathUtils.lerp(from.y, fromNext.y, mix),
          0,
        );
        link.curve.v3.set(
          THREE.MathUtils.lerp(to.x, toNext.x, mix),
          THREE.MathUtils.lerp(to.y, toNext.y, mix),
          0,
        );
        const middle = (link.curve.v0.y + link.curve.v3.y) / 2;
        link.curve.v1.set(link.curve.v0.x, middle, 0);
        link.curve.v2.set(link.curve.v3.x, middle, 0);
        for (let j = 0; j < 49; j++) {
          link.curve.getPoint(j / 48, point);
          point.toArray(link.vertices, j * 3);
        }
        link.geometry.attributes.position.needsUpdate = true;
        link.material.uniforms.uOpacity.value = opacity * 0.75;
        link.material.uniforms.uSignal.value = Math.min(1, Math.max(0, signal - i));
        if (Math.min(3, Math.floor(signal)) === i)
          link.curve.getPoint(Math.min(1, signal - i), marker.position);
      });
      marker.visible = opacity > 0.95 && signal > 0 && signal < 4;
    },
    dispose: () => resources.forEach((resource) => resource.dispose()),
  };
}
