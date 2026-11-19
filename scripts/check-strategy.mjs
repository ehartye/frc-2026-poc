import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const load = name => JSON.parse(readFileSync(new URL('../kickoff/' + name, import.meta.url)));
const field = load('field-profile.json');
const study = load('selected-strategy.json');
const {stock, seconds, stockReadyAtSource, loadedTravel, settle, periodPerDelivery} = study.case;
const service = (stockReady, travel, active = true) => {
  const remaining = Math.max(0, seconds - stockReady - travel - settle);
  return {remaining, opportunities: Math.min(stock, Math.floor(remaining / periodPerDelivery)), active};
};
const rows = [
  service(stockReadyAtSource, loadedTravel),
  service(stockReadyAtSource, loadedTravel + 5),
  service(18, loadedTravel),
  service(stockReadyAtSource, loadedTravel, false)
];
assert.deepEqual(rows.map(row => row.opportunities), [24, 14, 0, 24]);
const diameter = field.fieldFeatures.fuelDiameter * 25.4;
const fit = (size, count) => count * diameter + (count - 1) * study.pieceSpacingMm <= size;
const slots = study.packingGrid.reduce((product, count) => product * count, 1);
assert.equal(slots, stock);
assert.ok(study.hopperInternalMm.every((size, i) => fit(size, study.packingGrid[i])));
assert.ok(!fit(study.hopperInternalMm[1] - 11, study.packingGrid[1]));
assert.ok(2 * study.frameMm.reduce((a, b) => a + b) <= field.limits.perimeter * 25.4);
assert.ok(study.startingHeightBudgetMm <= field.limits.height * 25.4);
console.log(JSON.stringify({slots, diameterMm: diameter, serviceWindows: rows}, null, 2));
