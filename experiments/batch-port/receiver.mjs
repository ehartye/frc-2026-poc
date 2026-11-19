// R2C paired-wheel contact law in the settled receiver frame. Applies only inside its original
// center slice.
export function createReceiver(solids, recoveryNm, axialFaceShiftM = 0) {
  const wheel = solids['left scoring wheel'];
  const nativeCenter =
      [(wheel[0] + wheel[3]) / 2, (wheel[1] + wheel[4]) / 2, (wheel[2] + wheel[5]) / 2];
  const radius = .032, width = .050, lateral = nativeCenter[1], tangentX = .5,
        tangentZ = Math.sqrt(3) / 2;
  const inertia = .5 * Math.PI * radius ** 2 * width * 1100 * radius ** 2;
  const ceiling = .7 * 5676 * 2 * Math.PI / 60;
  let spin = ceiling, load = 0, work = 0;
  return {
    begin() {
      load = 0;
    },
    contact(b, carY, t) {
      const u = (b.x - nativeCenter[0]) * tangentX + (b.z - nativeCenter[2]) * tangentZ;
      const axial = -(b.x - nativeCenter[0]) * tangentZ + (b.z - nativeCenter[2]) * tangentX;
      const radial = Math.hypot(u, lateral), penetration = .150114 / 2 + radius - radial;
      if (Math.abs(b.y - carY) > .001) return;
      if (penetration > 0 && Math.abs(axial - axialFaceShiftM) < width / 2) {
        const speed = b.vx * tangentX + b.vz * tangentZ;
        const normal = Math.max(0, 30000 * penetration - 4 * speed * u / radial);
        const slip = radius * spin - speed * lateral / radial;
        const traction = .65 * normal * Math.tanh(slip / .08);
        const force = 2 * (normal * u / radial + traction * lateral / radial);
        b.fx += force * tangentX;
        b.fz += force * tangentZ;
        load += traction * radius;
        if (!b.headTouch) b.headTouch = {timeS: t, rotorSpeedRadS: spin, axialM: axial};
        b.inWheels = true;
      } else if (b.inWheels && u > 0 && b.vx * tangentX + b.vz * tangentZ > 0) {
        b.release = {timeS: t, rotorSpeedRadS: spin, rotorEnergyJ: inertia * spin * spin};
        b.inWheels = false;
      } else
        b.inWheels = false;
    },
    advance(dt) {
      const torque =
          load === 0 && spin < ceiling ? Math.min(recoveryNm, (ceiling - spin) * inertia / dt) : 0;
      const next = spin + (torque - load) / inertia * dt;
      work += torque * (spin + next) * dt;
      spin = next;
    },
    summary() {
      return {
        recoveryNm,
        axialFaceShiftM,
        initialSpeedRadS: ceiling,
        finalSpeedRadS: spin,
        workFromRecoveryJ: work,
        pairedRotorInertiaPerRotor: inertia
      };
    }
  };
}
