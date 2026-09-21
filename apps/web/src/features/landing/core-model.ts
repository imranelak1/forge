import * as THREE from "three";
import { coreColors } from "./landing-palette";

/** An optical payload and the persistent hardware that assembles around it into a CubeSat. */
export function createCore() {
  const root = new THREE.Group();
  const resources: { dispose(): void }[] = [];
  const keep = <T extends { dispose(): void }>(item: T) => {
    resources.push(item);
    return item;
  };
  const metal = keep(
    new THREE.MeshStandardMaterial({ color: 0xa39b91, metalness: 0.8, roughness: 0.3 }),
  );
  const graphite = keep(
    new THREE.MeshStandardMaterial({ color: 0x2b2926, metalness: 0.5, roughness: 0.42 }),
  );
  const black = keep(
    new THREE.MeshStandardMaterial({ color: 0x121211, metalness: 0.15, roughness: 0.68 }),
  );
  const copper = keep(
    new THREE.MeshStandardMaterial({ color: 0xb18754, metalness: 0.78, roughness: 0.32 }),
  );
  const glass = keep(
    new THREE.MeshPhysicalMaterial({
      color: 0x073b45,
      metalness: 0.5,
      roughness: 0.12,
      clearcoat: 1,
    }),
  );
  const accents = coreColors.map((color) =>
    keep(new THREE.MeshBasicMaterial({ color, toneMapped: false })),
  );
  const unit = keep(new THREE.BoxGeometry(1, 1, 1));
  const box = (parent: THREE.Object3D, size: number[], pos: number[], material: THREE.Material) => {
    const mesh = new THREE.Mesh(unit, material);
    mesh.scale.set(size[0], size[1], size[2]);
    mesh.position.set(pos[0], pos[1], pos[2]);
    parent.add(mesh);
    return mesh;
  };
  const cylinder = (
    parent: THREE.Object3D,
    radius: number,
    height: number,
    pos: number[],
    material: THREE.Material,
    segments = 32,
  ) => {
    const mesh = new THREE.Mesh(
      keep(new THREE.CylinderGeometry(radius, radius, height, segments)),
      material,
    );
    mesh.position.set(pos[0], pos[1], pos[2]);
    parent.add(mesh);
    return mesh;
  };
  const annulus = (outer: number, inner: number, depth: number) => {
    const shape = new THREE.Shape();
    shape.absarc(0, 0, outer, 0, Math.PI * 2, false);
    const hole = new THREE.Path();
    hole.absarc(0, 0, inner, 0, Math.PI * 2, true);
    shape.holes.push(hole);
    const geo = keep(
      new THREE.ExtrudeGeometry(shape, {
        depth,
        bevelEnabled: true,
        bevelSize: 0.018,
        bevelThickness: 0.018,
        bevelSegments: 2,
        steps: 1,
        curveSegments: 64,
      }),
    );
    geo.rotateX(Math.PI / 2);
    geo.translate(0, depth / 2, 0);
    return geo;
  };
  const dummy = new THREE.Object3D();
  const screwGeo = keep(new THREE.CylinderGeometry(0.045, 0.045, 0.06, 6));
  const frame = new THREE.Group();
  root.add(frame);
  for (const x of [-1.25, 1.25])
    for (const z of [-1.05, 1.05]) {
      box(frame, [0.12, 3.35, 0.12], [x, 0, z], metal);
      box(frame, [0.035, 3.2, 0.035], [x - Math.sign(x) * 0.08, 0, z - Math.sign(z) * 0.08], black);
    }
  for (const y of [-1.64, 1.64]) {
    for (const z of [-1.05, 1.05]) box(frame, [2.62, 0.13, 0.14], [0, y, z], metal);
    for (const x of [-1.25, 1.25]) box(frame, [0.14, 0.13, 2.14], [x, y, 0], metal);
  }
  const fasteners = keep(new THREE.InstancedMesh(screwGeo, black, 16));
  for (let i = 0; i < 16; i++) {
    dummy.position.set(i % 2 ? 1.25 : -1.25, i % 4 < 2 ? 1.72 : -1.72, i < 8 ? 1.05 : -1.05);
    dummy.rotation.set(0, 0, 0);
    dummy.updateMatrix();
    fasteners.setMatrixAt(i, dummy.matrix);
  }
  frame.add(fasteners);
  const layers = Array.from({ length: 5 }, (_, i) => {
    const group = new THREE.Group();
    root.add(group);
    const faceMaterial = keep(
      new THREE.MeshStandardMaterial({
        color: [0x47352e, 0x39372b, 0x293c32, 0x263a3c, 0x2d3544][i],
        roughness: 0.58,
        metalness: 0.32,
        emissive: coreColors[i],
        emissiveIntensity: 0,
      }),
    );
    box(group, [2.24, 0.075, 1.86], [0, 0, 0], faceMaterial);
    for (const x of [-1.07, 1.07]) box(group, [0.045, 0.09, 1.82], [x, 0.02, 0], copper);
    box(group, [1.8, 0.035, 0.035], [0, 0.07, 0.92], accents[i]);
    const bolts = keep(new THREE.InstancedMesh(screwGeo, metal, 8));
    for (let j = 0; j < 8; j++) {
      dummy.position.set(j % 2 ? 1 : -1, 0.1, -0.76 + Math.floor(j / 2) * 0.5);
      dummy.rotation.set(0, 0, 0);
      dummy.updateMatrix();
      bolts.setMatrixAt(j, dummy.matrix);
    }
    group.add(bolts);
    const standoffs = keep(
      new THREE.InstancedMesh(keep(new THREE.CylinderGeometry(0.035, 0.035, 0.34, 8)), copper, 4),
    );
    for (let j = 0; j < 4; j++) {
      dummy.position.set(j % 2 ? 0.96 : -0.96, -0.19, j < 2 ? 0.73 : -0.73);
      dummy.updateMatrix();
      standoffs.setMatrixAt(j, dummy.matrix);
    }
    group.add(standoffs);
    const tracks = keep(new THREE.InstancedMesh(unit, copper, 20));
    for (let j = 0; j < 20; j++) {
      dummy.position.set(-0.85 + (j % 10) * 0.18, 0.046, j < 10 ? -0.6 : 0.6);
      dummy.scale.set(0.012, 0.009, 0.3 + (j % 3) * 0.1);
      dummy.updateMatrix();
      tracks.setMatrixAt(j, dummy.matrix);
    }
    group.add(tracks);
    dummy.scale.set(1, 1, 1);
    const pins = keep(new THREE.InstancedMesh(unit, metal, 24));
    for (let j = 0; j < 24; j++) {
      dummy.position.set(-0.82 + (j % 12) * 0.15, 0.12, j < 12 ? -0.84 : 0.84);
      dummy.scale.set(0.035, 0.14, 0.035);
      dummy.updateMatrix();
      pins.setMatrixAt(j, dummy.matrix);
    }
    group.add(pins);
    dummy.scale.set(1, 1, 1);
    if (i === 0) {
      for (const x of [-0.64, 0, 0.64]) {
        box(group, [0.4, 0.18, 0.44], [x, 0.14, 0], black);
        box(group, [0.26, 0.02, 0.22], [x, 0.24, 0], metal);
      }
      box(group, [0.9, 0.22, 0.22], [0, 0.13, 0.74], black);
    } else if (i === 1) {
      box(group, [1.02, 0.18, 0.9], [0, 0.14, 0], black);
      for (let j = 0; j < 11; j++)
        box(group, [0.065, 0.24, 0.82], [-0.42 + j * 0.085, 0.28, 0], metal);
    } else if (i === 3) {
      for (const x of [-0.65, 0, 0.65]) {
        cylinder(group, 0.2, 0.2, [x, 0.17, 0], copper);
        cylinder(group, 0.08, 0.23, [x, 0.18, 0], black);
      }
      for (const x of [-0.76, 0.76]) cylinder(group, 0.095, 0.3, [x, 0.21, 0.55], metal, 16);
    } else if (i === 4) {
      box(group, [0.8, 0.22, 0.64], [0, 0.16, 0], metal);
      box(group, [0.55, 0.025, 0.4], [0, 0.29, 0], black);
      for (const x of [-0.7, 0.7]) box(group, [0.27, 0.12, 0.5], [x, 0.1, 0], black);
    }
    const port = new THREE.Object3D();
    port.position.set(i % 2 ? 1.28 : -1.28, 0.12, 0);
    group.add(port);
    return { group, faceMaterial, port };
  });
  const optic = new THREE.Group();
  layers[2].group.add(optic);
  const lensRings = [0, 1, 2, 3].map((i) => {
    const ring = new THREE.Mesh(annulus(1.02 - i * 0.055, 0.61, 0.15), i % 2 ? metal : graphite);
    ring.position.y = 0.19 + i * 0.17;
    optic.add(ring);
    return ring;
  });
  const teeth = keep(new THREE.InstancedMesh(unit, black, 64));
  for (let j = 0; j < 64; j++) {
    const a = (j * Math.PI) / 32;
    dummy.position.set(Math.cos(a) * 0.97, 0.53, Math.sin(a) * 0.97);
    dummy.rotation.set(0, -a, 0);
    dummy.scale.set(0.048, 0.14, 0.075);
    dummy.updateMatrix();
    teeth.setMatrixAt(j, dummy.matrix);
  }
  optic.add(teeth);
  dummy.scale.set(1, 1, 1);
  dummy.rotation.set(0, 0, 0);
  const lens = cylinder(optic, 0.6, 0.05, [0, 0.56, 0], glass, 64);
  const retainer = new THREE.Mesh(keep(new THREE.TorusGeometry(0.65, 0.024, 8, 64)), accents[3]);
  retainer.rotation.x = Math.PI / 2;
  retainer.position.y = 0.73;
  optic.add(retainer);
  const bladeShape = new THREE.Shape();
  bladeShape.moveTo(-0.12, -0.55);
  bladeShape.quadraticCurveTo(0.65, -0.48, 0.7, 0.15);
  bladeShape.lineTo(0.05, 0.33);
  bladeShape.quadraticCurveTo(0.15, 0, -0.12, -0.55);
  const bladeGeometry = keep(
    new THREE.ExtrudeGeometry(bladeShape, { depth: 0.018, bevelEnabled: false, curveSegments: 12 }),
  );
  bladeGeometry.rotateX(Math.PI / 2);
  const iris = Array.from({ length: 8 }, (_, i) => {
    const pivot = new THREE.Group();
    pivot.rotation.y = (i * Math.PI) / 4;
    optic.add(pivot);
    const blade = new THREE.Mesh(bladeGeometry, graphite);
    blade.position.set(0.15, 0.77, 0.05);
    pivot.add(blade);
    return pivot;
  });
  const wings = [-1, 1].map((side) => {
    const hinge = new THREE.Group();
    hinge.position.set(side * 1.32, 0.2, 0);
    root.add(hinge);
    const panel = new THREE.Group();
    panel.position.x = side * 0.96;
    hinge.add(panel);
    box(panel, [1.8, 0.08, 2.48], [0, 0, 0], metal);
    const cellMat = keep(
      new THREE.MeshStandardMaterial({ color: 0x233f57, metalness: 0.55, roughness: 0.24 }),
    );
    const cells = keep(new THREE.InstancedMesh(unit, cellMat, 24));
    for (let j = 0; j < 24; j++) {
      dummy.position.set(-0.66 + (j % 4) * 0.44, 0.06, -0.99 + Math.floor(j / 4) * 0.396);
      dummy.rotation.set(0, 0, 0);
      dummy.scale.set(0.405, 0.03, 0.35);
      dummy.updateMatrix();
      cells.setMatrixAt(j, dummy.matrix);
    }
    panel.add(cells);
    dummy.scale.set(1, 1, 1);
    for (const x of [-0.44, 0, 0.44]) box(panel, [0.012, 0.018, 2.28], [x, 0.087, 0], copper);
    for (const z of [-0.86, 0.86])
      cylinder(hinge, 0.09, 0.38, [0, 0, z], graphite, 16).rotation.z = Math.PI / 2;
    return hinge;
  });
  const antenna = new THREE.Group();
  root.add(antenna);
  cylinder(antenna, 0.16, 0.24, [0, 1.8, 0], copper);
  const aerials = [-1, 1].map((side) => {
    const boom = box(antenna, [2.65, 0.025, 0.06], [side * 1.4, 1.94, 0], copper);
    boom.rotation.y = side * 0.3;
    return boom;
  });
  const covers = [-1, 1].map((side) => {
    const cover = new THREE.Group();
    root.add(cover);
    box(cover, [2.4, 0.09, 1.94], [0, side * 1.55, 0], graphite);
    for (const x of [-1, 1])
      for (const z of [-0.76, 0.76]) cylinder(cover, 0.05, 0.06, [x, side * 1.62, z], metal, 6);
    return cover;
  });
  const busMaterial = keep(
    new THREE.ShaderMaterial({
      transparent: true,
      toneMapped: false,
      uniforms: { uSignal: { value: 0 }, uOpacity: { value: 0 } },
      vertexShader: `varying float vY; void main(){vY=position.y+.5;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
      fragmentShader: `varying float vY;uniform float uSignal;uniform float uOpacity;void main(){float p=1.-smoothstep(.02,.17,abs(vY-uSignal));gl_FragColor=vec4(mix(vec3(.16,.2,.22),vec3(.7,1.,.33),p),uOpacity);
    #include <colorspace_fragment>
    }`,
    }),
  );
  const bus = box(root, [0.035, 5.2, 0.035], [-1.02, 0, 1], busMaterial);
  const packet = box(root, [0.13, 0.13, 0.13], [-1.02, 0, 1.1], accents[2]);
  const sensor = box(layers[2].group, [0.62, 0.025, 0.62], [0, 0.1, 0], accents[3]);
  return {
    root,
    layers,
    optic,
    update(
      state: {
        assembly: number;
        spread: number;
        deploy: number;
        inspect: number;
        signal: number;
        aperture: number;
      },
      focus: number,
    ) {
      const { assembly, spread, deploy, inspect, signal, aperture } = state;
      frame.visible = assembly > 0.001;
      frame.scale.y = 1 + spread * 0.7;
      frame.scale.x = frame.scale.z = Math.max(0.001, assembly);
      fasteners.position.y = spread * 0.15;
      covers.forEach((cover, i) => {
        cover.visible = assembly > 0.001;
        cover.scale.setScalar(assembly);
        cover.position.y = (i ? 1 : -1) * spread * 1.5;
      });
      wings.forEach((wing, i) => {
        wing.visible = assembly > 0.3;
        wing.scale.setScalar(Math.max(0.001, (assembly - 0.3) / 0.7));
        wing.rotation.z = ((i ? 1 : -1) * (1 - deploy) * Math.PI) / 2;
      });
      antenna.visible = assembly > 0.8;
      antenna.scale.setScalar(Math.max(0.001, (assembly - 0.8) / 0.2));
      antenna.position.y = spread * 1.5;
      aerials.forEach((boom, i) => {
        boom.rotation.z = (i ? 1 : -1) * (1 - deploy) * 1.2;
      });
      lensRings.forEach((ring, i) => {
        ring.position.y = 0.19 + i * (0.17 + inspect * 0.19);
      });
      retainer.position.y = 0.73 + inspect * 0.6;
      lens.position.y = 0.56 + inspect * 0.25;
      iris.forEach((pivot, i) => {
        pivot.rotation.y = (i * Math.PI) / 4 + aperture * 0.72;
        pivot.position.set(
          Math.cos((i * Math.PI) / 4) * aperture * 0.2,
          inspect * 0.6,
          -Math.sin((i * Math.PI) / 4) * aperture * 0.2,
        );
      });
      sensor.position.y = 0.1 + inspect * 0.1;
      bus.visible = assembly > 0.2;
      bus.scale.y = 2.4 + spread * 3.1;
      busMaterial.uniforms.uOpacity.value = assembly * 0.85;
      busMaterial.uniforms.uSignal.value = signal;
      packet.visible = assembly > 0.2;
      packet.position.y = (signal - 0.5) * bus.scale.y;
      layers.forEach((layer, i) => {
        layer.faceMaterial.emissiveIntensity = focus === i ? 0.16 : 0;
      });
    },
    dispose: () => resources.forEach((resource) => resource.dispose()),
  };
}
