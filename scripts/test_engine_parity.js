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
  orig = new Function('RULES', templateSrc + '\nD = {rules: RULES};\nreturn {pmt, loanFromInstalment, bsd, computeLoan};')(rules);
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
