import * as THREE from "three";
import { coreColors } from "./landing-palette";
import type { TrackMotion } from "./core-choreography";

const stationDistances = [0.045, 0.31, 0.565, 0.865];

/** A continuous pair of rails, with physically connected inspection and review branches. */
export function createCore() {
  const root = new THREE.Group();
  const resources: { dispose(): void }[] = [];
  const keep = <T extends { dispose(): void }>(item: T) => {
    resources.push(item);
    return item;
  };
  const curve = (points: number[][]) =>
    new THREE.CatmullRomCurve3(
      points.map(([x, y, z = 0]) => new THREE.Vector3(x, y, z)),
      false,
      "centripetal",
    );
  const main = curve([
    [-0.92, 2.85],
    [-0.92, 2.1],
    [0.92, 1.65],
    [0.92, 0.95],
    [-0.92, 0.55],
    [-0.92, -0.15],
    [0.92, -0.55],
    [0.92, -1.25],
    [0, -1.7],
    [0, -2.05],
  ]);
  const inspection = curve([
    [0, -2.05],
    [0, -2.45],
    [-0.65, -2.75],
    [-1.55, -2.35],
    [-1.8, -1.6],
    [-1.65, -0.65],
    [-0.8, 0.05, 0.12],
    [0, 0.2, 0.16],
  ]);
  const investigation = curve([
    [0, 0.2, 0.16],
    [0.65, 0.55, 0.5],
    [1.85, 0.75, 0.55],
    [1.95, 1.8, 0.45],
    [1.2, 2.8, 0.2],
    [-0.92, 2.85],
  ]);
  const review = curve([
    [-0.92, 2.85],
    [-2.05, 2.4],
    [-2.35, 1.1],
    [-2.35, -1.45],
    [-1.8, -2.7],
    [-0.2, -2.95],
  ]);
  const curves = [main, inspection, investigation, review];
  const vec = new THREE.Vector3();
  const tangent = new THREE.Vector3();
  const dummy = new THREE.Object3D();
  const right = new THREE.Vector3();
  const up = new THREE.Vector3();
  const frame = new THREE.Matrix4();

  function sweep(
    path: THREE.Curve<THREE.Vector3>,
    offset: number,
    width: number,
    depth: number,
    base: number,
  ) {
    const count = 160;
    const positions: number[] = [],
      along: number[] = [],
      indices: number[] = [];
    const chamfer = Math.min(width, depth) * 0.24;
    const profile = [
      [-width / 2 + chamfer, 0],
      [width / 2 - chamfer, 0],
      [width / 2, chamfer],
      [width / 2, depth - chamfer],
      [width / 2 - chamfer, depth],
      [-width / 2 + chamfer, depth],
      [-width / 2, depth - chamfer],
      [-width / 2, chamfer],
    ];
    for (let i = 0; i <= count; i++) {
      path.getPointAt(i / count, vec);
      path.getTangentAt(i / count, tangent);
      const normal = new THREE.Vector2(-tangent.y, tangent.x).normalize();
      for (const [x, z] of profile) {
        positions.push(
          vec.x + normal.x * (offset + x),
          vec.y + normal.y * (offset + x),
          vec.z + base + z,
        );
        along.push(i / count);
      }
      if (i < count)
        for (let j = 0; j < 8; j++) {
          const a = i * 8 + j,
            b = i * 8 + ((j + 1) % 8),
            c = b + 8,
            d = a + 8;
          indices.push(a, b, d, b, c, d);
        }
    }
    const geometry = keep(new THREE.BufferGeometry());
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute("aAlong", new THREE.Float32BufferAttribute(along, 1));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    return geometry;
  }

  const vertexShader = `attribute float aAlong;varying float vAlong;varying vec3 vNormal;varying vec3 vView;
    void main(){vAlong=aAlong;vNormal=normalize(normalMatrix*normal);vec4 p=modelViewMatrix*vec4(position,1.);vView=-p.xyz;gl_Position=projectionMatrix*p;}`;
  const fragmentShader = `uniform vec3 uColor;uniform vec3 uAccent;uniform float uReveal;uniform float uCursor;uniform float uMetal;uniform float uStrength;
    varying float vAlong;varying vec3 vNormal;varying vec3 vView;
    void main(){if(vAlong>uReveal)discard;vec3 n=normalize(vNormal),l=normalize(vec3(-.6,.8,1.2));
      float light=.38+.65*max(0.,dot(n,l))+.22*max(0.,dot(n,normalize(vec3(.8,-.4,.5))));
      float spec=pow(max(0.,dot(reflect(-l,n),normalize(vView))),48.)*uMetal;
      float packet=(1.-smoothstep(.005,.065,abs(vAlong-uCursor)))*.14;
      vec3 shaded=uColor*light+vec3(spec*.65)+uAccent*packet;
      gl_FragColor=vec4(mix(vec3(.018),shaded,uStrength),1.);
      #include <colorspace_fragment>
    }`;
  const tieGeometry = keep(new THREE.BoxGeometry(0.64, 0.07, 0.065));
  const tieMaterial = keep(
    new THREE.MeshStandardMaterial({ color: 0x69645f, metalness: 0.5, roughness: 0.4 }),
  );
  const tracks = curves.map((path, index) => {
    const uniforms = {
      uReveal: { value: index === 0 ? 0.48 : 0 },
      uCursor: { value: -1 },
      uStrength: { value: 1 },
      uAccent: {
        value: new THREE.Color(
          index === 1 ? coreColors[2] : index === 2 ? coreColors[3] : coreColors[0],
        ),
      },
    };
    const addRail = (
      offset: number,
      width: number,
      depth: number,
      base: number,
      color: number,
      metal: number,
    ) => {
      const material = keep(
        new THREE.ShaderMaterial({
          uniforms: {
            ...uniforms,
            uColor: { value: new THREE.Color(color) },
            uMetal: { value: metal },
          },
          vertexShader,
          fragmentShader,
        }),
      );
      const mesh = new THREE.Mesh(sweep(path, offset, width, depth, base), material);
      root.add(mesh);
    };
    addRail(0, 0.48, 0.065, -0.035, 0x302e2b, 0.1);
    addRail(-0.21, 0.058, 0.11, 0.035, 0xbab6ac, 0.85);
    addRail(0.21, 0.058, 0.11, 0.035, 0xbab6ac, 0.85);
    if (index > 0)
      addRail(0, 0.034, 0.008, 0.04, coreColors[index === 1 ? 2 : index === 2 ? 3 : 4], 0);
    const tieCount = Math.ceil(path.getLength() / 0.22);
    const ties = keep(new THREE.InstancedMesh(tieGeometry, tieMaterial, tieCount));
    for (let i = 0; i < tieCount; i++) {
      const at = i / (tieCount - 1);
      path.getPointAt(at, dummy.position);
      path.getTangentAt(at, tangent);
      dummy.position.z -= 0.02;
      dummy.rotation.set(0, 0, Math.atan2(tangent.y, tangent.x) - Math.PI / 2);
      dummy.updateMatrix();
      ties.setMatrixAt(i, dummy.matrix);
    }
    ties.instanceMatrix.needsUpdate = true;
    root.add(ties);
    // A quiet guide line previews the route before its rails draw in.
    const guide = new THREE.Line(
      keep(new THREE.BufferGeometry().setFromPoints(path.getSpacedPoints(160))),
      keep(
        new THREE.LineBasicMaterial({
          color: 0x5c5752,
          transparent: true,
          opacity: index === 0 ? 0.35 : 0.15,
        }),
      ),
    );
    guide.position.z = -0.12;
    root.add(guide);
    return { path, uniforms, ties, tieCount, guide };
  });

  const metal = keep(
    new THREE.MeshStandardMaterial({ color: 0x8d8981, metalness: 0.65, roughness: 0.3 }),
  );
  const dark = keep(
    new THREE.MeshStandardMaterial({ color: 0x282624, metalness: 0.4, roughness: 0.45 }),
  );
  const box = keep(new THREE.BoxGeometry(1, 1, 1));
  const meshBox = (
    parent: THREE.Object3D,
    material: THREE.Material,
    size: number[],
    position: number[],
  ) => {
    const item = new THREE.Mesh(box, material);
    item.scale.set(size[0], size[1], size[2]);
    item.position.set(position[0], position[1], position[2]);
    parent.add(item);
    return item;
  };
  const stations = stationDistances.map((at, i) => {
    const group = new THREE.Group();
    main.getPointAt(at, group.position);
    main.getTangentAt(at, tangent);
    group.rotation.z = Math.atan2(tangent.y, tangent.x) - Math.PI / 2;
    const indicator = keep(
      new THREE.MeshStandardMaterial({
        color: coreColors[i],
        emissive: coreColors[i],
        emissiveIntensity: 0.25,
        roughness: 0.4,
        metalness: 0.2,
      }),
    );
    meshBox(group, metal, [0.1, 0.18, 0.5], [-0.38, 0, 0.21]);
    meshBox(group, metal, [0.1, 0.18, 0.5], [0.38, 0, 0.21]);
    meshBox(group, dark, [0.85, 0.2, 0.11], [0, 0, 0.51]);
    meshBox(group, indicator, [0.62, 0.09, 0.018], [0, 0, 0.575]);
    root.add(group);
    const label = group.position.clone();
    label.x = i % 2 === 0 ? -2.25 : 2.25;
    label.z = 0.25;
    return { group, indicator, label };
  });

  // A short tongue pivots about the real junction when the review branch opens.
  const pointsSwitch = new THREE.Group();
  pointsSwitch.position.copy(main.getPointAt(0));
  const switchTongue = new THREE.Group();
  switchTongue.position.set(0.08, 0, 0.18);
  meshBox(switchTongue, metal, [0.055, 0.46, 0.1], [0, -0.23, 0]);
  pointsSwitch.add(switchTongue);
  meshBox(pointsSwitch, dark, [0.2, 0.2, 0.16], [0.38, -0.13, 0.04]);
  const switchLight = keep(new THREE.MeshBasicMaterial({ color: coreColors[4] }));
  meshBox(pointsSwitch, switchLight, [0.07, 0.09, 0.025], [0.38, -0.13, 0.14]);
  root.add(pointsSwitch);

  const carrier = new THREE.Group();
  const carrierColor = keep(
    new THREE.MeshStandardMaterial({
      color: coreColors[0],
      metalness: 0.35,
      roughness: 0.28,
      emissive: coreColors[0],
      emissiveIntensity: 0.13,
    }),
  );
  meshBox(carrier, metal, [0.47, 0.54, 0.085], [0, 0, 0.19]);
  meshBox(carrier, carrierColor, [0.36, 0.42, 0.14], [0, 0, 0.3]);
  const lamp = keep(new THREE.MeshBasicMaterial({ color: 0xffdbb3 }));
  meshBox(carrier, lamp, [0.25, 0.025, 0.014], [0, -0.135, 0.38]);
  meshBox(carrier, dark, [0.18, 0.025, 0.015], [0, 0.1, 0.38]);
  const wheelGeometry = keep(new THREE.CylinderGeometry(0.075, 0.075, 0.055, 12));
  for (const x of [-0.23, 0.23])
    for (const y of [-0.18, 0.18]) {
      const wheel = new THREE.Mesh(wheelGeometry, metal);
      wheel.rotation.z = Math.PI / 2;
      wheel.position.set(x, y, 0.13);
      carrier.add(wheel);
    }
  root.add(carrier);
  const inspectionDock = new THREE.Group();
  inspectionDock.position.copy(inspection.getPointAt(1));
  inspection.getTangentAt(1, tangent);
  inspectionDock.rotation.z = Math.atan2(tangent.y, tangent.x) - Math.PI / 2;
  meshBox(inspectionDock, dark, [0.72, 0.64, 0.06], [0, 0, 0.01]);
  meshBox(inspectionDock, metal, [0.72, 0.06, 0.07], [0, 0.3, 0.08]);
  root.add(inspectionDock);
  const reviewDock = new THREE.Group();
  reviewDock.position.copy(review.getPointAt(1));
  review.getTangentAt(1, tangent);
  reviewDock.rotation.z = Math.atan2(tangent.y, tangent.x) - Math.PI / 2;
  meshBox(reviewDock, dark, [0.75, 0.65, 0.09], [0, 0, -0.04]);
  meshBox(reviewDock, metal, [0.75, 0.065, 0.17], [0, 0.3, 0.1]);
  root.add(reviewDock);

  return {
    root,
    stations,
    packet: carrier.position,
    update(motion: TrackMotion, selected: number) {
      const reveals = [motion.track, motion.inspection, motion.investigation, motion.review];
      const leg = Math.max(0, Math.min(3, Math.ceil(motion.journey) - 1)),
        at = Math.min(1, motion.journey - leg);
      tracks.forEach((track, i) => {
        track.uniforms.uReveal.value = reveals[i];
        track.uniforms.uCursor.value = i === leg ? at : -1;
        track.uniforms.uStrength.value = i === 0 ? 0.88 : i === leg ? 1 : 0.28;
        track.ties.count = Math.max(0, Math.floor(reveals[i] * track.tieCount));
        track.guide.visible = i === 0 || reveals[i] > 0.01;
      });
      stations.forEach((station, i) => {
        station.group.visible = motion.track >= stationDistances[i];
        station.indicator.emissiveIntensity = selected === i ? 0.9 : 0.2;
      });
      curves[leg].getPointAt(at, carrier.position);
      curves[leg].getTangentAt(at, tangent);
      right.set(tangent.y, -tangent.x, 0).normalize();
      up.crossVectors(right, tangent).normalize();
      carrier.quaternion.setFromRotationMatrix(frame.makeBasis(right, tangent, up));
      switchTongue.rotation.z = -motion.switch * 1.15;
      inspectionDock.visible = motion.inspection > 0.95;
      reviewDock.visible = motion.review > 0.95;
    },
    dispose: () => resources.forEach((resource) => resource.dispose()),
  };
}
