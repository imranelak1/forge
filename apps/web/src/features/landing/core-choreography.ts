/** Persistent delivery records reorganize into a trace, test report and investigation. */
export function createChoreography() {
  const motion = { lift: -2.1, scale: 1, reveal: 0, links: 0, route: 0, signal: 0 };
  const parts = Array.from({ length: 5 }, (_, i) => ({
    x: 0,
    y: 0,
    width: i ? 2 : 4.2,
    height: i ? 1 : 3.2,
    opacity: i ? 0 : 1,
  }));
  const layouts = [
    [
      [-1.45, 1.65, 2.55, 1.5],
      [1.45, 1.65, 2.55, 1.5],
      [-1.45, -1.65, 2.55, 1.5],
      [1.45, -1.65, 2.55, 1.5],
      [0, 0, 2.5, 0.95],
    ],
    [
      [0, 2.65, 3.7, 1.02],
      [0, 1.35, 3.7, 1.02],
      [0, 0.05, 3.7, 1.02],
      [0, -1.25, 3.7, 1.02],
      [0, -2.55, 3.7, 0.72],
    ],
    [
      [-1.4, 2.65, 2.5, 0.8],
      [1.4, 2.65, 2.5, 0.8],
      [0, 0.1, 5.3, 3.55],
      [-1.4, -2.5, 2.5, 0.8],
      [1.4, -2.5, 2.5, 0.8],
    ],
    [
      [1.4, 0, 2.6, 3.6],
      [-1.4, 2.5, 2.5, 0.8],
      [1.4, 2.5, 2.5, 0.8],
      [-1.4, 0, 2.6, 3.6],
      [0, -2.5, 5.4, 0.8],
    ],
    [
      [-2.06, 2.2, 1.26, 0.8],
      [-0.69, 2.2, 1.26, 0.8],
      [0.69, 2.2, 1.26, 0.8],
      [2.06, 2.2, 1.26, 0.8],
      [0, -0.25, 5.4, 3.6],
    ],
  ];
  return { motion, parts, layouts };
}

export type DeliveryPart = ReturnType<typeof createChoreography>["parts"][number];
