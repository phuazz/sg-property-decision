#!/usr/bin/env node
/* Lease label / tenure filter tests.
 *
 * `lease` in the projects feed is years REMAINING, not the original term. The label has to name
 * the term, and the tenure filter has to agree with the label — a row shown as 999-yr must pass
 * the Freehold filter, a row shown as 70yr must pass Leasehold, and no row may pass both.
 *
 * Regression under test: every remaining span above 200 used to render as '999-yr', which
 * mislabelled the two longest leases in the file. ROXY SQUARE is a 9,999-year lease commencing
 * 1995 (public record), so 9,968 years remain — a 999-year lease cannot leave that much.
 *
 * The helpers are sliced out of template.html rather than duplicated, so the test cannot drift
 * away from what the page actually runs.
 *
 * Usage: node scripts/test_lease_labels.js
 * Exit 0 = pass. Exit 1 = failure, with every failing case printed.
 */
'use strict';
const fs = require('fs'), path = require('path');

const ROOT = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(ROOT, 'template.html'), 'utf8');

// Slice the helpers out of the template between two stable markers.
const START = 'const _leaseNum=';
const END = 'function pfReset()';
const s = html.indexOf(START), e = html.indexOf(END);
if (s < 0 || e < 0 || e < s) {
  console.error(`FAIL: could not locate the lease helpers in template.html (start=${s}, end=${e}).`);
  console.error('If the template was restructured, update START/END in this test.');
  process.exit(1);
}
let H;
try {
  H = new Function(html.slice(s, e) + '\nreturn {_leaseNum, _leaseTxt, _fhLike, _lhOnly};')();
} catch (err) {
  console.error('FAIL: could not evaluate the lease helper slice:', err.message);
  process.exit(1);
}

const fails = [];
const eq = (label, got, want) => { if (!Object.is(got, want)) fails.push(`${label}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`); };
const ok = (label, cond) => { if (!cond) fails.push(label); };

/* ---- labels, with the boundary on both sides of every cut ---- */
[
  ['FH', 'Freehold'],
  [41, '41yr'],        // shortest remaining lease in the live data
  [60, '60yr'],        // the financing/CPF cliff the table colours red
  [101, '101yr'],      // longest true leasehold in the live data
  [200, '200yr'],      // last value below the quasi-freehold cut
  [201, '999-yr'],     // first value above it
  [800, '999-yr'],     // shortest quasi-freehold in the live data
  [968, '999-yr'],
  [999, '999-yr'],     // a 999-yr lease granted this year
  [1000, '9999-yr'],   // only a 9,999-year term can leave this much
  [9968, '9999-yr'],   // ROXY SQUARE — the regression
  [9999, '9999-yr'],
  [10000, '999-yr+'],  // beyond what a buyer transacts: stays generic
  [999963, '999-yr+'], // RESIDENTIAL APARTMENTS (D19)
  [null, '—'],
  [undefined, '—'],
].forEach(([input, want]) => eq(`_leaseTxt(${JSON.stringify(input)})`, H._leaseTxt(input), want));

/* ---- the filter must never contradict the label ----
   Freehold-like iff the label is not a plain "Nyr"; exactly one bucket per known tenure. */
const QUASI = new Set(['Freehold', '999-yr', '9999-yr', '999-yr+']);
const span = [];
for (let y = 0; y <= 1200; y++) span.push(y);
span.push(9968, 9999, 10000, 99999, 999963, 1e6);
span.forEach(y => {
  const label = H._leaseTxt(y), fh = H._fhLike(y), lh = H._lhOnly(y);
  ok(`label/filter disagree at ${y}: label ${label}, _fhLike ${fh}`, QUASI.has(label) === fh);
  ok(`${y} lands in both buckets or neither`, fh !== lh);
});
ok('FH is freehold-like', H._fhLike('FH') && !H._lhOnly('FH'));
ok('unknown tenure joins neither bucket', !H._fhLike(null) && !H._lhOnly(null));

/* ---- sort key: freehold outranks every lease, including the 999,999-year outlier ---- */
ok('FH sorts above 999963', H._leaseNum('FH') > H._leaseNum(999963));
ok('FH sorts above 9968', H._leaseNum('FH') > H._leaseNum(9968));
ok('9968 sorts above 101', H._leaseNum(9968) > H._leaseNum(101));
ok('unknown tenure sorts below every real lease', H._leaseNum(null) < H._leaseNum(0));

/* ---- the live data must not contain a lease the label rules cannot name ---- */
const livePath = path.join(ROOT, 'data', 'live.json');
if (fs.existsSync(livePath)) {
  const rows = ((JSON.parse(fs.readFileSync(livePath, 'utf8')).projects || {}).rows) || [];
  rows.forEach(r => {
    const l = r.lease;
    if (l == null) return;
    ok(`${r.project}: lease ${l} yields no label`, H._leaseTxt(l) !== '—');
    if (typeof l === 'number') ok(`${r.project}: negative lease ${l}`, l >= 0);
  });
  const named = rows.filter(r => typeof r.lease === 'number' && r.lease > 999).map(r => `${r.project} (${r.lease}y → ${H._leaseTxt(r.lease)})`);
  console.log(`Checked ${rows.length} live project rows. Leases over 999 years: ${named.length ? named.join(', ') : 'none'}.`);
}

if (fails.length) {
  console.error(`FAIL: ${fails.length} case(s)\n  ` + fails.join('\n  '));
  process.exit(1);
}
console.log('PASS: lease labels, tenure buckets and sort order are consistent.');
