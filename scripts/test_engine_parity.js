#!/usr/bin/env node
/* Parity test: engine/engine.js must be bit-identical to the loan engine still inlined in
 * template.html, across the full categorical space and a numeric grid.
 *
 * The extracted engine takes rules as a parameter; the in-template copy reads a module-level
 * `D.rules`. That is the ONLY permitted difference. Everything else — including behaviour this
 * project considers wrong, such as MSR being applied to every EC — must match exactly, so that
 * extraction is provably a no-op. Fix defects only after the swap, in one place, deliberately.
 *
 * Usage: node scripts/test_engine_parity.js
 * Exit 0 = identical. Exit 1 = mismatch, with the first failing case printed in full.
 */
'use strict';
const fs = require('fs'), path = require('path');

const ROOT = path.resolve(__dirname, '..');
const rules = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'rules.json'), 'utf8'));
const html = fs.readFileSync(path.join(ROOT, 'template.html'), 'utf8');

// Slice the engine out of the template between two stable markers.
const START = '// monthly payment';
const END = 'function readInputs()';
const s = html.indexOf(START), e = html.indexOf(END);
if (s < 0 || e < 0 || e < s) {
  console.error(`FAIL: could not locate the engine in template.html (start=${s}, end=${e}).`);
  console.error('If the template was restructured, update START/END in this test.');
  process.exit(1);
}
const templateSrc = html.slice(s, e);

// Reconstruct the in-template implementation in its own scope, supplying the `D` global it reads.
let orig;
try {
  orig = new Function('RULES', templateSrc + '\nD = {rules: RULES};\nreturn {pmt, loanFromInstalment, bsd, computeLoan, leaseRelativity, leaseRundown};')(rules);
} catch (err) {
  console.error('FAIL: could not evaluate the template engine slice:', err.message);
  process.exit(1);
}
const ENG = require(path.join(ROOT, 'engine', 'engine.js'));

const GRID = {
  age: [25, 35, 42, 50, 55, 64],
  income: [5000, 12000, 25000],
  incomeVar: [0, 8000],
  debt: [0, 2500],
  cash: [200000, 1200000],
  price: [500000, 1000000, 1500000, 2500000, 4000000],
  type: ['hdb', 'ec', 'private'],
  loan: ['hdb', 'bank'],
  cz: ['SC', 'PR', 'Foreigner'],
  count: [0, 1, 2, 3],
  tenure: [5, 20, 25, 30, 35],
  rate: [0.01, 0.016, 0.04, 0.05],
};
const keys = Object.keys(GRID);

function compare(a, b) {
  const ka = Object.keys(a), kb = Object.keys(b);
  if (ka.length !== kb.length) return `key count ${ka.length} vs ${kb.length}`;
  for (const k of ka) {
    if (!(k in b)) return `missing key ${k}`;
    if (!Object.is(a[k], b[k])) return `${k}: ${a[k]} vs ${b[k]}`;
  }
  return null;
}

let n = 0, bad = 0;
const idx = new Array(keys.length).fill(0);
outer: for (;;) {
  const inp = {};
  keys.forEach((k, i) => { inp[k] = GRID[k][idx[i]]; });

  const diff = compare(orig.computeLoan(inp), ENG.computeLoan(inp, rules));
  n++;
  if (diff) {
    bad++;
    if (bad === 1) {
      console.error('FAIL: divergence between template.html and engine/engine.js');
      console.error('  input:', JSON.stringify(inp));
      console.error('  first differing field:', diff);
    }
    if (bad > 5) break;
  }

  // odometer over the grid
  let i = keys.length - 1;
  for (;;) {
    if (++idx[i] < GRID[keys[i]].length) break;
    idx[i] = 0;
    if (--i < 0) break outer;
  }
}

// bsd and pmt directly, including boundary values of the IRAS brackets
const edges = [0, 1, 180000, 180001, 360000, 360001, 1000000, 1500000, 3000000, 3000001, 12345678];
for (const p of edges) {
  if (!Object.is(orig.bsd(p, rules.bsd.brackets), ENG.bsd(p, rules.bsd.brackets))) {
    console.error(`FAIL: bsd(${p}) diverges`); bad++;
  }
  n++;
}
for (const r of [0, 0.01, 0.04]) for (const y of [1, 25, 35]) {
  if (!Object.is(orig.pmt(r, y, 1000000), ENG.pmt(r, y, 1000000))) {
    console.error(`FAIL: pmt(${r},${y}) diverges`); bad++;
  }
  n++;
}

// Leasehold relativity (the SLA table): parity across the domain — both sides of every cut, the
// interpolation, the flat run beyond 99, quasi-freehold spans, and every kind of bad input.
const LR = (rules.lease_relativity || {}).pct_by_years_left;
// Fractions are deliberately asymmetric (0.25 / 0.75): at exactly x.5 an interpolation run the
// wrong way returns the same value, which let a mutated template copy pass this grid once.
const leases = [-5, 0, 0.25, 0.5, 1, 1.5, 29, 30, 30.25, 30.5, 59, 60, 61, 69, 69.75, 70, 85, 98, 98.5, 98.75, 99, 99.5, 100, 101, 200, 201, 999, 9968, NaN, Infinity, null, undefined, '70'];
const horizons = [0, 1, 5, 10, 25, 30, 70, 100, -1, NaN, null];
for (const L of leases) {
  if (!Object.is(orig.leaseRelativity(LR, L), ENG.leaseRelativity(LR, L))) { console.error(`FAIL: leaseRelativity(${L}) diverges`); bad++; }
  n++;
  for (const y of horizons) {
    if (!Object.is(orig.leaseRundown(LR, L, y), ENG.leaseRundown(LR, L, y))) { console.error(`FAIL: leaseRundown(${L},${y}) diverges`); bad++; }
    n++;
  }
}
// A missing or short table must read null, never NaN, in both copies.
for (const T of [undefined, null, [], [1, 2, 3]]) {
  n++;
  if (!Object.is(orig.leaseRelativity(T, 70), null) || !Object.is(ENG.leaseRelativity(T, 70), null) ||
      !Object.is(orig.leaseRundown(T, 70, 1), null) || !Object.is(ENG.leaseRundown(T, 70, 1), null)) {
    console.error('FAIL: a missing table must return null'); bad++;
  }
}

// The table itself: the published anchors, the 1948 ratios, and the run-down at every edge.
// Guards against an edit to the array — parity alone would pass a wrong table on both sides.
if (LR) {
  const near = (label, got, want) => { n++; if (!(Math.abs(got - want) <= 1e-9)) { console.error(`FAIL: ${label}: got ${got}, want ${want}`); bad++; } };
  near('table length (index 0..99)', LR.length, 100);
  n++; if (!LR.every((v, i) => i === 0 ? v === 0 : v > LR[i - 1])) { console.error('FAIL: the table must start at 0 and rise with every year of lease'); bad++; }
  for (const [yrs, want] of Object.entries(rules.lease_relativity.anchors_pct || {})) near(`anchor ${yrs} yr`, ENG.leaseRelativity(LR, +yrs), want);
  near('30-year bid vs 60-year bid (Victoria Street 2005: 0.6/0.8)', ENG.leaseRelativity(LR, 30) / ENG.leaseRelativity(LR, 60), 0.75);
  near('expired lease', ENG.leaseRelativity(LR, 0), 0);
  near('half-year interpolation', ENG.leaseRelativity(LR, 69.5), (85.4 + 86.0) / 2);
  near('quarter-year interpolation runs the right way', ENG.leaseRelativity(LR, 69.25), 85.4 + 0.25 * (86.0 - 85.4));
  near('beyond the table reads the 99-year entry', ENG.leaseRelativity(LR, 150), 96.0);
  near('run-down 70 -> 69', ENG.leaseRundown(LR, 70, 1), 1 - 85.4 / 86.0);
  near('run-down 99 -> 98 (top of the table)', ENG.leaseRundown(LR, 99, 1), 1 - 95.9 / 96.0);
  near('run-down 99 -> 89 over ten years', ENG.leaseRundown(LR, 99, 10), 1 - 94.3 / 96.0);
  near('run-down 1 -> 0 (the last year)', ENG.leaseRundown(LR, 1, 1), 1);
  near('run-down when the lease runs out inside the horizon', ENG.leaseRundown(LR, 5, 10), 1);
  near('zero horizon', ENG.leaseRundown(LR, 70, 0), 0);
  near('flat beyond the table', ENG.leaseRundown(LR, 150, 1), 0);
  n++; if (ENG.leaseRundown(LR, 0, 1) !== null) { console.error('FAIL: an expired lease has nothing to run down (null)'); bad++; }
}

// The published BSD checkpoints in rules.json must hold — guards against a bracket edit.
for (const [price, expect] of Object.entries(rules.bsd.checkpoints_sgd || {})) {
  const got = Math.round(ENG.bsd(+price, rules.bsd.brackets));
  n++;
  if (got !== expect) { console.error(`FAIL: BSD checkpoint ${price}: expected ${expect}, got ${got}`); bad++; }
}

if (bad) {
  console.error(`\n${bad} divergence(s) across ${n.toLocaleString()} cases. Extraction is NOT a no-op.`);
  process.exit(1);
}
console.log(`PASS: ${n.toLocaleString()} cases identical (engine/engine.js == template.html).`);
