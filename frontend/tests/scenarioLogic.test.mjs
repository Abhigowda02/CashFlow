import test from 'node:test';
import assert from 'node:assert/strict';
import { baselineSignature, buildDefinition, changeDescription, definitionSignature,
  eligibleCustomers, horizonEnd, runwayDays } from '../src/scenarioLogic.ts';

const business = {
  as_of: '2026-10-25',
  customers: [
    { id: 'C1', name: 'Textile buyer', segment: 'corporate' },
    { id: 'C2', name: 'Local trader', segment: 'small' },
    { id: 'C3', name: 'Settled buyer', segment: 'small' },
  ],
  invoices: [
    { id: 'I1', customer_id: 'C1', amount: 10000, received_amount: 4000, status: 'open', due_date: '2026-10-20' },
    { id: 'I2', customer_id: 'C1', amount: 2000, status: 'open', due_date: '2026-11-01' },
    { id: 'I3', customer_id: 'C2', amount: 5000, status: 'open', due_date: '2026-11-05' },
    { id: 'I4', customer_id: 'C3', amount: 9000, status: 'paid', due_date: '2026-10-20' },
    { id: 'I5', customer_id: 'C3', amount: 1000, received_amount: 1000, status: 'open', due_date: '2026-10-20' },
  ],
  supplier_bills: [{ id: 'B1', amount: 1000, status: 'open', is_msme: false }],
  sales_plan: { monthly_amount: 50000 },
};
const delay = (customer_id, extra_days) => ({ key: customer_id, type: 'delay_customer', customer_id, extra_days });
const draft = (...changes) => ({ name: 'Customer stress', changes });

test('eligible customer totals use remaining balances and exclude settled invoices', () => {
  assert.deepEqual(eligibleCustomers(business).map(({ id, outstanding, invoice_count }) => ({ id, outstanding, invoice_count })), [
    { id: 'C1', outstanding: 8000, invoice_count: 2 },
    { id: 'C2', outstanding: 5000, invoice_count: 1 },
  ]);
});

test('customer choices generate only explicit delays, including different delays for multiple customers', () => {
  const input = draft(delay('C2', '30'), delay('C1', '10'));
  const snapshot = structuredClone(input);
  const { errors, definition } = buildDefinition(input, business);
  assert.deepEqual(errors, []);
  assert.deepEqual(definition.changes, [
    { type: 'delay_customer', customer_id: 'C2', extra_days: 30 },
    { type: 'delay_customer', customer_id: 'C1', extra_days: 10 },
  ]);
  assert.deepEqual(input, snapshot);
  assert.deepEqual(buildDefinition(draft(), business).definition.changes, []);
});

test('missing, settled, repeated customer choices and invalid day values cannot be submitted', () => {
  for (const row of [delay('', '20'), delay('C3', '20'), delay('unknown', '20'),
    delay('C1', ''), delay('C1', '0'), delay('C1', '-1'), delay('C1', '181'), delay('C1', '1.5')]) {
    assert.ok(buildDefinition(draft(row), business).errors.length > 0);
  }
  assert.ok(buildDefinition(draft(delay('C1', '10'), delay('C1', '20')), business).errors.length > 0);
});

test('expense dates stay in the inclusive 90-day horizon and amounts are safe integer INR', () => {
  assert.equal(horizonEnd(business.as_of), '2027-01-22');
  const expense = (amount, date) => ({ key: 'expense', type: 'extra_expense', amount, date });
  for (const date of [business.as_of, horizonEnd(business.as_of)]) {
    assert.deepEqual(buildDefinition(draft(expense('25000', date)), business).errors, []);
  }
  for (const date of ['2026-10-24', '2027-01-23', '2026-11-31', '', 'not-a-date']) {
    assert.ok(buildDefinition(draft(expense('25000', date)), business).errors.length > 0);
  }
  for (const amount of ['', '0', '-1', '1.5', '9007199254740992', 'Infinity']) {
    assert.ok(buildDefinition(draft(expense(amount, business.as_of)), business).errors.length > 0);
  }
});

test('inactive sales and supplier assumptions require actionable business inputs', () => {
  const sales = { key: 'sales', type: 'sales_change', pct: '-20' };
  const terms = { key: 'terms', type: 'supplier_terms', extra_days: '15' };
  assert.deepEqual(buildDefinition(draft(sales, terms), business).errors, []);
  assert.ok(buildDefinition(draft({ ...sales, pct: '0' }), business).errors.length > 0);
  assert.ok(buildDefinition(draft(sales), { ...business, sales_plan: { monthly_amount: 0 } }).errors.length > 0);
  assert.ok(buildDefinition(draft(terms), { ...business, supplier_bills: [] }).errors.length > 0);
  assert.ok(buildDefinition(draft(sales, { ...sales, key: 'second' }), business).errors.length > 0);
});

test('stale-result signatures distinguish edited assumptions and selected models', () => {
  const original = buildDefinition(draft(delay('C1', '20')), business).definition;
  const changed = buildDefinition(draft(delay('C2', '20')), business).definition;
  assert.notEqual(definitionSignature(original, 'survival'), definitionSignature(changed, 'survival'));
  assert.notEqual(definitionSignature(original, 'survival'), definitionSignature(original, 'empirical'));
  assert.equal(definitionSignature(original, 'survival'), definitionSignature(structuredClone(original), 'survival'));
});

test('median runway is computed from the P50 balance rather than the simulated shortage date', () => {
  const forecast = { dates: ['2026-10-25', '2026-10-26', '2026-10-27'], p10: [0, 0, 0], p50: [1000, 500, 99], p90: [2000, 2000, 2000],
    safety_floor: 100, shortage_prob: 0.4, first_shortage_date: '2026-10-25', min_balance_p50: 99 };
  assert.equal(runwayDays(forecast), 2);
  assert.equal(runwayDays({ ...forecast, p50: [1000, 500, 100] }), null);
  assert.notEqual(baselineSignature(forecast), baselineSignature({ ...forecast, p50: [1000, 500, 98] }));
});

test('assumption review names the selected customer and its outstanding exposure', () => {
  const text = changeDescription({ type: 'delay_customer', customer_id: 'C1', extra_days: 20 }, business);
  assert.match(text, /Textile buyer pays 20 days later/);
  assert.match(text, /2 unpaid invoices/);
  assert.match(text, /8,000/);
});
