import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';
import {renderChart} from '../src/ready_set_wash/static/chart.js';

const pause = () => new Promise(resolve => setTimeout(resolve, 10));

async function settled() {
  for (let i = 0; i < 100; i++) {
    if (!document.getElementById('calculate').disabled) return;
    await pause();
  }
  throw new Error('UI did not finish updating');
}

test('planner works across demo, live, history, reminders and errors', async () => {
  const dom = new JSDOM(readFileSync(new URL('../src/ready_set_wash/static/index.html', import.meta.url), 'utf8'), {url: 'http://localhost:8000'});
  Object.assign(globalThis, {
    document: dom.window.document, window: dom.window, localStorage: dom.window.localStorage, innerWidth: 1440
  });
  let state = 'demo';
  const start = new Date(Date.now() + 3600000).toISOString();
  const end = new Date(Date.now() + 9000000).toISOString();
  const data = {
    mode: 'demo',
    plan: {start, end, costPence: 10, nowCostPence: 24, savingsPence: 14},
    prices: Array.from({length: 24}, (_, i) => ({
      start: new Date(Date.now() + i * 1800000).toISOString(),
      end: new Date(Date.now() + (i + 1) * 1800000).toISOString(),
      pencePerKwh: 10 + i
    })),
  };
  globalThis.fetch = async (_url, options) => {
    const payload = JSON.parse(options.body);
    assert.equal(Object.hasOwn(payload.variables, 'energy'), false);
    assert.equal(payload.query.includes('energyKwh'), false);
    if (state === 'timeout') throw Object.assign(new Error('timeout'), {name: 'TimeoutError'});
    if (state === 'error') return {ok: true, json: async () => ({errors: [{message: 'Prices unavailable'}]})};
    return {ok: true, json: async () => ({data: {dashboard: {...data, mode: state}}})};
  };
  let downloads = 0;
  dom.window.HTMLAnchorElement.prototype.click = function () {
    downloads++;
    assert.equal(this.download, 'ready-set-wash.ics');
  };
  await import('../src/ready_set_wash/static/app.js');
  await settled();
  const $ = id => document.getElementById(id);
  assert.equal($('energy'), null);
  assert.equal(document.querySelectorAll('img[src="/mascot.svg"]').length, 2);
  assert.match(document.querySelector('h1').textContent, /The right time.*for a lighter load/);
  assert.equal(document.querySelector('.brand').textContent.replace(/\s+/g, ' ').trim(), 'Ready, Set, Wash');
  assert.equal($('best-cost').textContent, '10p');
  assert.equal($('mode').textContent, '● Demo data');
  assert.ok(document.querySelectorAll('.bar.chosen').length);
  $('reminder').click();
  assert.equal(downloads, 1);
  $('history-tab').click();
  assert.equal($('planner').hidden, true);
  assert.equal(document.querySelectorAll('.history-row').length, 1);
  $('clear-history').click();
  assert.match($('history-list').textContent, /No washes planned/);
  $('plan-tab').click();
  assert.equal($('planner').hidden, false);
  state = 'live';
  $('wash-form').dispatchEvent(new dom.window.Event('submit', {cancelable: true}));
  await settled();
  assert.equal($('mode').textContent, '● Live Octopus prices');
  $('history-tab').click();
  assert.match($('history-list').textContent, /Live prices/);
  $('plan-tab').click();
  globalThis.innerWidth = 400;
  window.dispatchEvent(new dom.window.Event('resize'));
  state = 'error';
  $('wash-form').dispatchEvent(new dom.window.Event('submit', {cancelable: true}));
  await settled();
  assert.equal($('error').textContent, 'Prices unavailable');
  assert.equal($('reminder').disabled, true);
  $('reminder').dispatchEvent(new dom.window.Event('click'));
  window.dispatchEvent(new dom.window.Event('resize'));
  state = 'timeout';
  $('wash-form').dispatchEvent(new dom.window.Event('submit', {cancelable: true}));
  await settled();
  assert.match($('error').textContent, /timed out/);
  state = 'demo';
  $('wash-form').dispatchEvent(new dom.window.Event('submit', {cancelable: true}));
  await settled();
  $('history-tab').click();
  assert.match($('history-list').textContent, /Demo data/);
  dom.window.close();
});

test('chart handles no data, negative prices and a wash starting in the first interval', () => {
  const dom = new JSDOM('<div id="chart"></div>');
  globalThis.document = dom.window.document;
  globalThis.innerWidth = 1440;
  const container = document.getElementById('chart');
  const now = Date.now();
  const plan = {start: new Date(now).toISOString(), end: new Date(now + 1800000).toISOString()};
  renderChart(container, [], plan);
  assert.equal(container.children.length, 0);
  const prices = [-5, -3, 12].map((price, i) => ({
    start: new Date(now + i * 1800000).toISOString(),
    end: new Date(now + (i + 1) * 1800000).toISOString(),
    pencePerKwh: price
  }));
  renderChart(container, prices, plan);
  assert.match(container.getAttribute('aria-label'), /absolute prices/);
  assert.equal(container.querySelectorAll('.negative').length, 1);
  assert.equal(container.querySelectorAll('.wash-marker').length, 1);
  dom.window.close();
});
