const locationChoice = document.querySelector('#location');
const delay = document.querySelector('#delay');
const clock = __CLOCK__;
function compare() {
  const travel = clock.loadedTravel + Number(delay.value);
  const ready = locationChoice.value === 'source'
    ? clock.stockReadyAtSource + travel + clock.settle
    : Math.max(clock.stockReadyAtSource, travel + clock.settle);
  const available = Math.max(0, clock.seconds - ready);
  const count = Math.min(clock.stock, Math.floor(available / clock.periodPerDelivery));
  document.querySelector('#answer').textContent = available + ' s to feed · ' +
    (clock.stock / available).toFixed(2) + ' FUEL/s required · ' + count + ' of ' + clock.stock + ' opportunities';
}
locationChoice.addEventListener('change', compare);
delay.addEventListener('change', compare);
compare();
