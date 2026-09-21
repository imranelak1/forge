/** One continuous journey: delivery, reproduction, investigation, then human review. */
export function createChoreography() {
  return {
    motion: {
      lift: -2.45,
      reveal: 0,
      track: 0.48,
      inspection: 0,
      investigation: 0,
      review: 0,
      switch: 0,
      journey: 0.035,
      labels: 0,
    },
  };
}

export type TrackMotion = ReturnType<typeof createChoreography>["motion"];
