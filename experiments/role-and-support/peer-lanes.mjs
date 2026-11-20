/** Keep the historical kickoff profile intact while varying the reserve robot's exit. */
export function peerLaneProfile(source) {
  const profile = structuredClone(source);
  const rehearsal = profile.rehearsal;
  const baseline = rehearsal.series.matches.find(match => match.id === 'Own-zone supply');
  if (!baseline) throw Error('The own-zone baseline is missing');
  const matches = [baseline];
  for (const [id, label, at] of [
    ['short-reserve', 'Near reserve', [111, 247]],
    ['deep-reserve', 'Deep reserve', [109, 268]],
  ]) {
    rehearsal.programs[id] = {
      label: label + ' beyond the depot approach',
      loop: false,
      steps: [{at, label: 'Park and leave room for the depot robot', dwell: 0}],
    };
    for (const sides of [['blue'], ['red'], ['blue', 'red']]) {
      const match = structuredClone(baseline);
      match.id = label + ' · ' + sides.join(' + ');
      match.basis = 'Same kickoff stock, starts, scoring assumptions and climb commitments as Own-zone supply. ' +
        'Only the named alliance reserve robot changes its parking destination after AUTO.';
      for (const robot of match.roster) {
        if (robot.slot !== 3 || !sides.includes(robot.side)) continue;
        for (const phase of Object.keys(robot.plans)) {
          if (phase !== 'AUTO') robot.plans[phase] = id;
        }
      }
      matches.push(match);
    }
  }
  rehearsal.series.matches = matches;
  return profile;
}
