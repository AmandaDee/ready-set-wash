import test from 'node:test';
import assert from 'node:assert/strict';
import {calendar, clock, londonInput, londonToISO, pence} from '../src/ready_set_wash/static/time.js';
import {clearHistory, readHistory, savePlan} from '../src/ready_set_wash/static/history.js';
import {fetchPlan} from '../src/ready_set_wash/static/api.js';

test('UK times work independently of the machine timezone', () => {
  assert.equal(londonInput(new Date('2026-07-01T12:00:00Z')), '2026-07-01T13:00');
  assert.equal(londonToISO('2026-07-01T13:00'), '2026-07-01T12:00:00.000Z');
  assert.equal(londonToISO('2026-12-01T13:00'), '2026-12-01T13:00:00.000Z');
  assert.equal(clock('2026-07-01T12:00:00Z'), '13:00');
});
test('DST gaps rejected and repeated hour uses later occurrence', () => {
  assert.throws(() => londonToISO('2026-03-29T01:30'), /does not exist/);
  assert.equal(londonToISO('2026-10-25T01:30'), '2026-10-25T01:30:00.000Z');
  assert.throws(() => londonToISO('garbage'), /valid deadline/);
});
test('costs and calendar use precise UTC instants', () => {
  assert.equal(pence(null), '—');
  assert.equal(pence(10), '10p');
  assert.equal(pence(-1.55), '-1.6p');
  const result = calendar({start: '2026-10-01T13:00:00Z', end: '2026-10-01T14:30:00Z'});
  assert.match(result, /DTSTART:20261001T130000Z/);
  assert.match(result, /BEGIN:VALARM/);
  assert.ok(result.endsWith('\r\n'));
});
test('history is bounded and resilient to denied and corrupted storage', () => {
  let value = null;
  const storage = {getItem: () => value, setItem: (_k, v) => value = v, removeItem: () => value = null};
  const plan = {start: '2026-10-01T13:00:00Z', end: '2026-10-01T14:30:00Z', costPence: 10};
  for (let i = 0; i < 25; i++) savePlan(plan, storage);
  assert.equal(readHistory(storage).length, 20);
  clearHistory(storage);
  assert.deepEqual(readHistory(storage), []);
  for (const corrupt of ['bad', '{}', '[null,{}, {"start":"bad"}]']) {
    value = corrupt;
    assert.deepEqual(readHistory(storage), []);
  }
  const denied = {
    getItem: () => {
      throw Error();
    }, setItem: () => {
      throw Error();
    }, removeItem: () => {
      throw Error();
    }
  };
  assert.deepEqual(readHistory(denied), []);
  savePlan(plan, denied);
  clearHistory(denied);
});
test('GraphQL client sends variables and rejects failures', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (_url, options) => {
      assert.equal(JSON.parse(options.body).variables.duration, 90);
      return {ok: true, json: async () => ({data: {dashboard: {mode: 'demo'}}})};
    };
    assert.equal((await fetchPlan({duration: 90})).mode, 'demo');
    globalThis.fetch = async () => ({ok: false});
    await assert.rejects(fetchPlan({}), /Could not/);
    globalThis.fetch = async () => ({ok: true, json: async () => ({errors: [{message: 'No window'}]})});
    await assert.rejects(fetchPlan({}), /No window/);
    globalThis.fetch = async () => ({ok: true, json: async () => ({data: null})});
    await assert.rejects(fetchPlan({}), /No price/);
  } finally {
    globalThis.fetch = original;
  }
});
