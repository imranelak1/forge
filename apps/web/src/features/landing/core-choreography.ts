/** One optical payload becomes a complete observation satellite; no unrelated stage spins. */
export function createChoreography() {
  const motion = {
    lift: -2.1,
    scale: 1.42,
    reveal: 0,
    assembly: 0,
    spread: 0,
    deploy: 0,
    inspect: 0,
    signal: 0,
    aperture: 0.25,
  };
  const parts = Array.from({ length: 5 }, (_, i) => ({
    x: 0,
    y: 0,
    z: 0,
    size: i === 2 ? 1 : 0.001,
  }));
  const stack = (gap: number) => Array.from({ length: 5 }, (_, i) => [0, (i - 2) * gap, 0, 1]);
  const connect = stack(1.15);
  const trace = stack(0.73);
  const understand = stack(1.05);
  const investigate = stack(0.9);
  investigate[2] = [0, 0.15, 1.45, 1.12];
  const complete = stack(0.48);
  return { motion, parts, connect, trace, understand, investigate, complete };
}
