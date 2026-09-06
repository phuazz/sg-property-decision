#!/usr/bin/env node
/* Project score tests.
 *
 * The Score is the mean of four percentile ranks; the five-deal floor decides who is in the
 * ranking pool at all. Under test: the floor on both sides (4 is out, 5 is in), that a thin row
 * cannot move anyone else's rank, that stale scores are cleared on re-score, that the extremes
 * land on 0 and 100, that the floor constant itself is pinned, and - on the live feed - that
 * every unscored row is unscored for a reason and every scored row clears the floor.
 *
 * Regression under test: before the floor (2026-09-06) the top of the table was old freehold
 * stock on two or three cheap sales - 21 of the top 40 had fewer than five deals.
 *
 * The scorer is sliced out of template.html rather than duplicated, so the test cannot drift
 * away from what the page actually runs.
 *
 * Usage: node scripts/test_project_score.js
 * Exit 0 = pass. Exit 1 = failure, with every failing case printed.
 */
'use strict';
const fs = require('fs'), path = require('path');

const ROOT = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(ROOT, 'template.html'), 'utf8');

// Slice the scorer out of the template between two stable markers.
const START = 'const SCORE_MIN_DEALS=';
const END = 'function pfReset()';
const s = html.indexOf(START), e = html.indexOf(END);
if (s < 0 || e < 0 || e < s) {
  console.error(`FAIL: could not locate the scorer in template.html (start=${s}, end=${e}).`);
  console.error('If the template was restructured, update START/END in this test.');
  process.exit(1);
}
let S;
try {
  S = new Function(html.slice(s, e) + '\nreturn {SCORE_MIN_DEALS, _scoreProjects};')();
} catch (err) {
  console.error('FAIL: could not evaluate the scorer slice:', err.message);
  process.exit(1);
}
const FLOOR = S.SCORE_MIN_DEALS, score = S._scoreProjects;

const fails = [];
const ok = (label, cond) => { if (!cond) fails.push(label); };
const eq = (label, got, want) => { if (!Object.is(got, want)) fails.push(`${label}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`); };

/* ---- the floor is a published parameter: the same 5 as the studies' MIN_CELL_N ---- */
eq('SCORE_MIN_DEALS', FLOOR, 5);

/* ---- synthetic rows: one district, median $psf 1,500 ---- */
const DMED = { 1: 1500 };
const mk = (o) => Object.assign({ d: 1, district: 'D1', median_psf: 1500, vol_12m: 10, lease: 80, mrt_m: 500 }, o);

// both sides of the floor
{
  const rows = [mk({ project: 'four', vol_12m: 4 }), mk({ project: 'five', vol_12m: 5 }), mk({ project: 'six', vol_12m: 6 })];
  const scored = score(rows, DMED, FLOOR);
  eq('4 deals is not scored', rows[0].score, null);
  eq('4 deals has no factor breakdown', rows[0]._sc, null);
  ok('5 deals is scored', typeof rows[1].score === 'number');
  ok('6 deals is scored', typeof rows[2].score === 'number');
  eq('scored subset returned', scored.length, 2);
}

// no deals field, no $psf: out, and out for a reason
{
  const rows = [mk({ project: 'novol', vol_12m: undefined }), mk({ project: 'nopsf', median_psf: null }), mk({ project: 'fine' })];
  score(rows, DMED, FLOOR);
  eq('missing vol_12m is not scored', rows[0].score, null);
  eq('missing median_psf is not scored', rows[1].score, null);
  ok('the ordinary row is scored', typeof rows[2].score === 'number');
}

// a stale score from an earlier render is cleared, not carried
{
  const rows = [mk({ project: 'stale', vol_12m: 2, score: 99, _sc: [1, 2, 3, 4] })];
  score(rows, DMED, FLOOR);
  eq('stale score cleared', rows[0].score, null);
  eq('stale breakdown cleared', rows[0]._sc, null);
}

// a thin row cannot move anyone else's rank: identical scores with and without it in the file
{
  const pool = () => [
    mk({ project: 'a', median_psf: 1200, vol_12m: 30, lease: 95, mrt_m: 200 }),
    mk({ project: 'b', median_psf: 1400, vol_12m: 12, lease: 70, mrt_m: 600 }),
    mk({ project: 'c', median_psf: 1600, vol_12m: 8, lease: 'FH', mrt_m: 900 }),
    mk({ project: 'd', median_psf: 1900, vol_12m: 5, lease: 60, mrt_m: 1400 }),
  ];
  const thin = () => mk({ project: 'thin', median_psf: 400, vol_12m: 2, lease: 'FH', mrt_m: 50 });
  const clean = pool(); score(clean, DMED, FLOOR);
  const withThin = pool().concat([thin()]); score(withThin, DMED, FLOOR);
  clean.forEach((r, i) => eq(`rank unmoved by a thin outlier (${r.project})`, withThin[i].score, r.score));
  eq('the thin outlier is unscored', withThin[4].score, null);
  // lowering the floor to 2 lets it in and DOES move the others: the guard is the floor, not luck
  const low = pool().concat([thin()]); score(low, DMED, 2);
  ok('a floor of 2 admits the outlier', typeof low[4].score === 'number');
  ok('and the others move', low.some((r, i) => i < 4 && r.score !== clean[i].score));
}

// extremes: best on every factor is 100, worst is 0, the middle is 50, all integers 0..100
{
  const rows = [
    mk({ project: 'best', median_psf: 1000, vol_12m: 100, lease: 'FH', mrt_m: 100 }),
    mk({ project: 'mid', median_psf: 1500, vol_12m: 20, lease: 70, mrt_m: 800 }),
    mk({ project: 'worst', median_psf: 2000, vol_12m: 5, lease: 40, mrt_m: 2000 }),
  ];
  score(rows, DMED, FLOOR);
  eq('best on all four = 100', rows[0].score, 100);
  eq('middle on all four = 50', rows[1].score, 50);
  eq('worst on all four = 0', rows[2].score, 0);
  rows.forEach(r => ok(`integer score 0..100 (${r.project})`, Number.isInteger(r.score) && r.score >= 0 && r.score <= 100));
  rows.forEach(r => ok(`four factor ranks (${r.project})`, Array.isArray(r._sc) && r._sc.length === 4));
}

/* ---- the live feed: every unscored row is unscored for a reason, every scored row clears the floor ---- */
const livePath = path.join(ROOT, 'data', 'live.json');
if (fs.existsSync(livePath)) {
  const live = JSON.parse(fs.readFileSync(livePath, 'utf8'));
  const P = live.projects && (live.projects.rows || live.projects);
  const drows = (live.districts && live.districts.rows) || [];
  if (Array.isArray(P) && P.length) {
    const dmed = {}; drows.forEach(r => { dmed[r.d] = r.median_psf; });
    const rows = P.map(r => Object.assign({}, r));
    const scored = score(rows, dmed, FLOOR);
    const expect = rows.filter(r => r.median_psf && (r.vol_12m || 0) >= FLOOR).length;
    eq('live: scored count equals the rows clearing the floor', scored.length, expect);
    rows.forEach(r => {
      const clears = !!r.median_psf && (r.vol_12m || 0) >= FLOOR;
      if (clears !== (r.score != null)) fails.push(`live: ${r.project} (${r.district}, ${r.vol_12m} deals) scored=${r.score != null} but clears the floor=${clears}`);
    });
    const top = scored.slice().sort((a, b) => b.score - a.score).slice(0, 40);
    eq('live: no thin project in the top 40', top.filter(r => (r.vol_12m || 0) < FLOOR).length, 0);
    console.log(`Live feed: ${rows.length} projects, ${scored.length} scored, ${rows.length - scored.length} below the ${FLOOR}-deal floor.`);
  }
}

if (fails.length) {
  console.error(`FAIL: ${fails.length} case(s)`);
  fails.forEach(f => console.error('  ' + f));
  process.exit(1);
}
console.log('PASS: project score - floor on both sides, thin rows out of the ranking pool, stale scores cleared, extremes at 0 and 100, live feed consistent.');
