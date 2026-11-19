// Four finite paired carriers in R2C. Return to pickup requires a full belt circuit.
export function liftCircuit(low, high, carriers = 4, uniform = false) {
  const turnRadius = .0525;
  const span = high - low;
  const length = 2 * span + 2 * Math.PI * turnRadius;
  const pitch = uniform ? length / carriers : .159;
  const offsets = Array.from({length: carriers}, (_, i) => i * pitch);
  return {
    low,
    high,
    carriers,
    length,
    pitch,
    topHeights(t, speed, firstTop) {
      const heights = [];
      for (const offset of offsets) {
        const phase = (firstTop - low + offset + t * speed) % length;
        if (phase <= span) heights.push(low + phase);
      }
      return heights;
    }
  };
}
