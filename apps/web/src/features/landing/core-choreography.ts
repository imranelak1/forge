/** The same parts become a source map, a delivery path, and an opened evidence module. */
export function createChoreography() {
  const motion = {
    lift: -2.12,
    scale: 0.9,
    open: 0,
    inspect: 0,
    chain: 0,
    reveal: 0,
    signal: 0,
    links: 0,
  };
  const parts = Array.from({ length: 5 }, (_, i) => ({
    x: 0,
    y: (i - 2) * 0.36,
    z: 0,
    size: 1,
    tilt: 0,
  }));
  const map = [
    [-1.15, 1.4, 0.52],
    [1.15, 1.4, 0.52],
    [-1.15, -1.4, 0.52],
    [1.15, -1.4, 0.52],
    [0, 0, 0.45],
  ];
  const path = [
    [-0.65, 2.5, 0.43],
    [0.65, 0.84, 0.43],
    [-0.65, -0.84, 0.43],
    [0.65, -2.5, 0.43],
    [1.45, 0, 0.24],
  ];
  const inspection = [
    [-1.1, 2.75, 0.28],
    [1.1, 2.75, 0.28],
    [-1.1, -2.75, 0.28],
    [1.1, -2.75, 0.28],
    [0, 0, 0.8],
  ];
  return { motion, parts, map, path, inspection };
}
