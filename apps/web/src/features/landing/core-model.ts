import * as THREE from "three";

/** Machined geometry shared by all five independently animated assemblies. */
export function createCore() {
  const root = new THREE.Group();
  const resources: { dispose(): void }[] = [];
  const keep = <T extends { dispose(): void }>(resource: T) => {
    resources.push(resource);
    return resource;
  };
  const graphite = keep(
    new THREE.MeshStandardMaterial({ color: 0x202020, metalness: 0.78, roughness: 0.29 }),
  );
  const silver = keep(
    new THREE.MeshStandardMaterial({ color: 0xc9c9c9, metalness: 0.82, roughness: 0.24 }),
  );
  const ceramic = keep(
    new THREE.MeshStandardMaterial({ color: 0xf4f4f4, metalness: 0.25, roughness: 0.3 }),
  );
  const recess = keep(
    new THREE.MeshStandardMaterial({ color: 0x090909, metalness: 0.45, roughness: 0.5 }),
  );

  const annulus = (outer: number, inner: number, depth: number) => {
    const shape = new THREE.Shape();
    shape.absarc(0, 0, outer, 0, Math.PI * 2, false);
    const hole = new THREE.Path();
    hole.absarc(0, 0, inner, 0, Math.PI * 2, true);
    shape.holes.push(hole);
    const geometry = keep(
      new THREE.ExtrudeGeometry(shape, {
        depth,
        bevelEnabled: true,
        bevelSegments: 2,
        steps: 1,
        bevelSize: 0.025,
        bevelThickness: 0.025,
        curveSegments: 64,
      }),
    );
    geometry.rotateX(Math.PI / 2);
    geometry.translate(0, depth / 2, 0);
    return geometry;
  };
  const bodyGeometry = annulus(1.55, 0.8, 0.2);
  const faceGeometry = annulus(1.49, 0.89, 0.035);
  const innerGeometry = annulus(0.84, 0.62, 0.28);
  const rimGeometry = keep(new THREE.TorusGeometry(1.55, 0.032, 8, 96));
  rimGeometry.rotateX(Math.PI / 2);
  const toothGeometry = keep(new THREE.BoxGeometry(0.065, 0.16, 0.11));
  const boltGeometry = keep(new THREE.CylinderGeometry(0.037, 0.037, 0.027, 6));
  const notchGeometry = keep(new THREE.BoxGeometry(0.016, 0.008, 0.15));
  const matrix = new THREE.Object3D();
  const layers = Array.from({ length: 5 }, (_, i) => {
    const layer = new THREE.Group();
    const shell = new THREE.Mesh(bodyGeometry, i % 2 ? graphite : silver);
    layer.add(shell);
    const face = new THREE.Mesh(faceGeometry, i % 2 ? silver : ceramic);
    face.position.y = 0.125;
    layer.add(face);
    const rotor = new THREE.Group();
    rotor.add(new THREE.Mesh(innerGeometry, graphite));
    layer.add(rotor);
    const rim = new THREE.Mesh(rimGeometry, graphite);
    rim.position.y = 0.08;
    layer.add(rim);
    const teeth = new THREE.InstancedMesh(toothGeometry, i % 2 ? silver : graphite, 64);
    const notches = new THREE.InstancedMesh(notchGeometry, recess, 64);
    for (let j = 0; j < 64; j++) {
      const angle = (j / 64) * Math.PI * 2;
      matrix.position.set(Math.cos(angle) * 1.565, 0, Math.sin(angle) * 1.565);
      matrix.rotation.set(0, -angle + Math.PI / 2, 0);
      matrix.updateMatrix();
      teeth.setMatrixAt(j, matrix.matrix);
      matrix.position.set(Math.cos(angle) * 1.34, 0.153, Math.sin(angle) * 1.34);
      matrix.updateMatrix();
      notches.setMatrixAt(j, matrix.matrix);
    }
    layer.add(teeth, notches);
    keep(teeth);
    keep(notches);
    const bolts = new THREE.InstancedMesh(boltGeometry, graphite, 8);
    for (let j = 0; j < 8; j++) {
      const angle = (j / 8) * Math.PI * 2;
      matrix.position.set(Math.cos(angle) * 1.12, 0.162, Math.sin(angle) * 1.12);
      matrix.rotation.set(0, angle, 0);
      matrix.updateMatrix();
      bolts.setMatrixAt(j, matrix.matrix);
    }
    layer.add(bolts);
    keep(bolts);
    if (i === 0 || i === 4) {
      const fittingGeometry = keep(new THREE.BoxGeometry(i === 0 ? 0.19 : 0.13, 0.24, 0.23));
      const fittings = keep(new THREE.InstancedMesh(fittingGeometry, graphite, 4));
      for (let j = 0; j < 4; j++) {
        const angle = (j * Math.PI) / 2;
        matrix.position.set(Math.cos(angle) * 1.57, 0, Math.sin(angle) * 1.57);
        matrix.rotation.set(0, -angle, 0);
        matrix.updateMatrix();
        fittings.setMatrixAt(j, matrix.matrix);
      }
      layer.add(fittings);
    }
    if (i === 1) {
      const bladeGeometry = keep(new THREE.BoxGeometry(0.11, 0.025, 0.2));
      const blades = keep(new THREE.InstancedMesh(bladeGeometry, silver, 24));
      for (let j = 0; j < 24; j++) {
        const angle = (j * Math.PI) / 12;
        matrix.position.set(Math.cos(angle) * 0.78, 0.165, Math.sin(angle) * 0.78);
        matrix.rotation.set(0, -angle + 0.45, 0);
        matrix.updateMatrix();
        blades.setMatrixAt(j, matrix.matrix);
      }
      rotor.add(blades);
    }
    if (i === 2 || i === 3) {
      const arcGeometry = keep(
        new THREE.TorusGeometry(
          i === 2 ? 1.04 : 1.61,
          i === 2 ? 0.012 : 0.04,
          6,
          72,
          Math.PI * 1.75,
        ),
      );
      arcGeometry.rotateX(Math.PI / 2);
      const arc = new THREE.Mesh(arcGeometry, graphite);
      arc.position.y = 0.17;
      rotor.add(arc);
    }
    layer.position.y = (i - 2) * 0.36;
    root.add(layer);
    return { group: layer, rotor, face };
  });

  const shaft = new THREE.Mesh(keep(new THREE.CylinderGeometry(0.37, 0.37, 2.2, 48)), graphite);
  root.add(shaft);
  const capGeometry = annulus(1.65, 0.52, 0.12);
  const caps = [-1, 1].map((direction) => {
    const cap = new THREE.Group();
    cap.add(new THREE.Mesh(capGeometry, direction === 1 ? silver : graphite));
    for (const radius of [0.59, 1.38, 1.5, 1.61]) {
      const engravingGeometry = keep(new THREE.TorusGeometry(radius, 0.009, 4, 96));
      engravingGeometry.rotateX(Math.PI / 2);
      const engraving = new THREE.Mesh(engravingGeometry, graphite);
      engraving.position.y = 0.095;
      cap.add(engraving);
    }
    const screws = keep(new THREE.InstancedMesh(boltGeometry, recess, 12));
    for (let j = 0; j < 12; j++) {
      const angle = (j * Math.PI) / 6;
      matrix.position.set(Math.cos(angle) * 1.22, 0.097, Math.sin(angle) * 1.22);
      matrix.rotation.set(0, angle, 0);
      matrix.updateMatrix();
      screws.setMatrixAt(j, matrix.matrix);
    }
    cap.add(screws);
    root.add(cap);
    return cap;
  });
  const signalMaterial = keep(
    new THREE.ShaderMaterial({
      uniforms: { uTravel: { value: 0 }, uIntensity: { value: 0.3 } },
      vertexShader: `varying vec3 vPosition; varying vec3 vNormal;
      void main() { vPosition = position; vNormal = normalize(normalMatrix * normal);
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }`,
      fragmentShader: `varying vec3 vPosition; varying vec3 vNormal;
      uniform float uTravel; uniform float uIntensity;
      void main() {
        float angle = atan(vPosition.z, vPosition.x);
        float beam = pow(max(0., cos(angle - uTravel)), 24.);
        float rim = pow(1. - abs(vNormal.z), 2.);
        float value = .15 + beam * .8 * uIntensity + rim * .15;
        gl_FragColor = vec4(vec3(value), 1.);
      }`,
    }),
  );
  const signalGeometry = keep(new THREE.TorusGeometry(1.595, 0.018, 6, 100));
  signalGeometry.rotateX(Math.PI / 2);
  layers.forEach(({ group }) => {
    const signal = new THREE.Mesh(signalGeometry, signalMaterial);
    signal.position.y = -0.04;
    group.add(signal);
  });
  return {
    root,
    layers,
    caps,
    shaft,
    signalMaterial,
    dispose: () => resources.forEach((r) => r.dispose()),
  };
}
