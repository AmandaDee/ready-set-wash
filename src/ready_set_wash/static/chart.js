import {clock, fullDate} from './time.js';

export function renderChart(container, prices, plan) {
  container.replaceChildren();
  const start = Date.now();
  const visible = prices.filter(r => Date.parse(r.end) > start && Date.parse(r.start) < Math.max(start + 12 * 3600000, Date.parse(plan.end))).slice(0, 96);
  if (!visible.length) return;
  const maximum = Math.max(10, ...visible.map(r => Math.abs(r.pencePerKwh)));
  const axis = document.createElement('div');
  axis.className = 'axis';
  for (const fraction of [1, .75, .5, .25, 0]) {
    const tick = document.createElement('span');
    tick.textContent = `${Math.round(maximum * fraction)}p`;
    axis.append(tick);
  }
  container.append(axis);
  const plot = document.createElement('div');
  plot.className = 'plot';
  const negative = visible.some(r => r.pencePerKwh < 0);
  container.setAttribute('aria-label', `Electricity prices in pence per kWh. ${negative ? 'Bar heights show absolute prices; orange bars are negative.' : ''} Green bars overlap the recommended wash.`);
  visible.forEach((rate, index) => {
    const slot = document.createElement('div');
    slot.className = 'bar-slot';
    const bar = document.createElement('button');
    bar.type = 'button';
    bar.className = 'bar';
    const selected = Date.parse(rate.start) < Date.parse(plan.end) && Date.parse(rate.end) > Date.parse(plan.start);
    if (selected) bar.classList.add('chosen'); else if (rate.pencePerKwh < 0) bar.classList.add('negative');
    bar.style.height = `${Math.max(2, Math.abs(rate.pencePerKwh) / maximum * 100)}%`;
    bar.title = `${fullDate(rate.start)}: ${rate.pencePerKwh.toFixed(2)}p/kWh${selected ? ' · Your wash' : ''}`;
    bar.setAttribute('aria-label', bar.title);
    slot.append(bar);
    const stride = Math.max(1, Math.ceil(visible.length / (innerWidth < 720 ? 5 : 10)));
    if (index % stride === 0) {
      const tick = document.createElement('span');
      tick.className = 'tick';
      tick.textContent = clock(rate.start);
      slot.append(tick);
    }
    if (selected && (index === 0 || Date.parse(visible[index - 1].end) <= Date.parse(plan.start))) {
      const marker = document.createElement('span');
      marker.className = 'wash-marker';
      marker.textContent = '↔ Your wash';
      slot.append(marker);
    }
    plot.append(slot);
  });
  container.append(plot);
}
