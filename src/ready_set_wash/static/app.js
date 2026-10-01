import {fetchPlan} from './api.js';
import {renderChart} from './chart.js';
import {clearHistory, readHistory, savePlan} from './history.js';
import {calendar, clock, fullDate, londonInput, londonToISO, pence} from './time.js';

const $ = id => document.getElementById(id);
let activePlan = null;
let activePrices = [];

function showError(message) {
  $('error').textContent = message;
  $('error').hidden = false;
}

function display(data) {
  activePlan = data.plan;
  activePrices = data.prices;
  $('mode').textContent = data.mode === 'demo' ? '● Demo data' : '● Live Octopus prices';
  $('chart-label').textContent = data.mode === 'demo' ? 'Illustrative prices · p/kWh' : 'Octopus prices, incl. VAT · p/kWh';
  $('start-time').textContent = clock(activePlan.start);
  $('finish').textContent = `Finished by ${fullDate(activePlan.end)}`;
  $('explanation').textContent = data.mode === 'demo' ? 'A sample price window to explore clever timing. Switch to live mode for real rates.' : 'The cheapest complete window before your deadline, using available published prices.';
  $('now-cost').textContent = pence(activePlan.nowCostPence);
  $('best-cost').textContent = pence(activePlan.costPence);
  $('savings').textContent = pence(activePlan.savingsPence);
  $('reminder').disabled = false;
  renderChart($('chart'), activePrices, activePlan);
}

async function calculate(event) {
  event?.preventDefault();
  $('error').hidden = true;
  $('calculate').disabled = true;
  $('calculate').textContent = 'Finding your window…';
  $('result').setAttribute('aria-busy', 'true');
  activePlan = null;
  $('reminder').disabled = true;
  try {
    const data = await fetchPlan({
      deadline: londonToISO($('deadline').value), duration: Number($('duration').value)
    });
    display(data);
    savePlan({...data.plan, mode: data.mode});
  } catch (error) {
    $('start-time').textContent = '—';
    $('finish').textContent = 'No plan available';
    $('explanation').textContent = 'Update your settings and try again.';
    for (const id of ['now-cost', 'best-cost', 'savings']) $(id).textContent = '—';
    $('chart').replaceChildren();
    showError(error.name === 'TimeoutError' ? 'The request timed out. Please try again.' : error.message);
  } finally {
    $('calculate').disabled = false;
    $('calculate').textContent = '↗  Find my wash window';
    $('result').setAttribute('aria-busy', 'false');
  }
}

function historyView() {
  const list = $('history-list');
  list.replaceChildren();
  const rows = readHistory();
  if (!rows.length) {
    list.textContent = 'No washes planned yet. Plan your first wash to get started.';
    return;
  }
  for (const plan of rows) {
    const row = document.createElement('div');
    row.className = 'history-row';
    const title = document.createElement('strong');
    title.textContent = fullDate(plan.start);
    const info = document.createElement('span');
    info.textContent = `${pence(plan.costPence)} estimated · ${plan.mode === 'live' ? 'Live prices' : 'Demo data'}`;
    row.append(title, info);
    list.append(row);
  }
}

for (const view of ['plan', 'history']) $(view + '-tab').addEventListener('click', () => {
  $('planner').hidden = view !== 'plan';
  $('history').hidden = view !== 'history';
  for (const item of ['plan', 'history']) {
    $(item + '-tab').classList.toggle('active', item === view);
    $(item + '-tab').setAttribute('aria-selected', String(item === view));
  }
  if (view === 'history') historyView();
});
$('clear-history').addEventListener('click', () => {
  clearHistory();
  historyView();
});
$('reminder').addEventListener('click', () => {
  if (!activePlan) return;
  const url = URL.createObjectURL(new Blob([calendar(activePlan)], {type: 'text/calendar'}));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'ready-set-wash.ics';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$('wash-form').addEventListener('submit', calculate);
window.addEventListener('resize', () => {
  if (activePlan) renderChart($('chart'), activePrices, activePlan);
});
const deadline = new Date(Date.now() + 8 * 3600000);
$('deadline').value = londonInput(deadline);
calculate();
