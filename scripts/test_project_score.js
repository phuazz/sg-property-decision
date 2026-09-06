#!/usr/bin/env node
/* Project score tests.
 *
 * The Score is the mean of four percentile ranks over every project with a resale median. Two
 * rules make it honest with thin data and are the things under test here:
 *   1. Confidence weighting - the value factor shrinks a project's vs-area discount by n/(n+5),
 *      n being its deals in twelve months, so two sales cannot carry a project to the top on
 *      their own; fewer than five deals is labelled low confidence. Nobody is excluded.
 *   2. Ties share the average rank - 64% of the file is freehold and 26% has exactly two deals,
 *      and the previous ranker split each tie by file order, so identical inputs drew ranks up
 *      to 64 points apart and the Score depended on the order rows arrived in.
 * Also pinned: the prior constant, the weight at 0 / 5 / 20 deals, that stale scores are
 * cleared on re-score, that the extremes land on 0 and 100, and - on the live feed - that every
 * row with a median is scored, the low-confidence label matches the deal count, and a shuffled
 * file scores every project identically.
 *
 * Regression under test: before confidence weighting (2026-09-06) the top of the table was old
 * freehold stock on two or three cheap sales - 21 of the top 40 had fewer than five deals.
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
const START = 'const SCORE_PRIOR_DEALS=';
const END = 'function pfReset()';
const s = html.indexOf(START), e = html.indexOf(END);
if (s < 0 || e < 0 || e < s) {
  console.error(`FAIL: could not locate the scorer in template.html (start=${s}, end=${e}).`);
  console.error('If the template was restructured, update START/END in this test.');
  process.exit(1);
}
let S;
try {
  S = new Function(html.slice(s, e) + '\nreturn {SCORE_PRIOR_DEALS, _scoreProjects};')();
} catch (err) {
  console.error('FAIL: could not evaluate the scorer slice:', err.message);
  process.exit(1);
}
const PRIOR = S.SCORE_PRIOR_DEALS, score = S._scoreProjects;

const fails = [];
const ok = (label, cond) => { if (!cond) fails.push(label); };
const eq = (label, got, want) => { if (!Object.is(got, want)) fails.push(`${label}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`); };
const near = (label, got, want) => { if (!(Math.abs(got - want) <= 1e-9)) fails.push(`${label}: got ${got}, want ${want}`); };

/* ---- the prior is a published parameter: five deals, the same number as the studies' cell floor ---- */
eq('SCORE_PRIOR_DEALS', PRIOR, 5);

/* ---- synthetic rows: one district, median $psf 1,500 ---- */
const DMED = { 1: 1500 };
const mk = (o) => Object.assign({ d: 1, district: 'D1', median_psf: 1500, vol_12m: 10, lease: 80, mrt_m: 500 }, o);

// everyone with a median is scored; the weight follows the deal count; the label follows the prior
{
  const rows = [mk({ project: 'none', vol_12m: undefined }), mk({ project: 'two', vol_12m: 2 }), mk({ project: 'four', vol_12m: 4 }),
                mk({ project: 'five', vol_12m: 5 }), mk({ project: 'twenty', vol_12m: 20 }), mk({ project: 'nopsf', median_psf: null })];
  const scored = score(rows, DMED, PRIOR);
  eq('scored subset = every row with a median', scored.length, 5);
  eq('no median, no score', rows[5].score, null);
  rows.slice(0, 5).forEach(r => ok(`scored (${r.project})`, Number.isInteger(r.score)));
  near('weight at 0 deals', rows[0]._w, 0);
  near('weight at 2 deals', rows[1]._w, 2 / 7);
  near('weight at 5 deals = half', rows[3]._w, 0.5);
  near('weight at 20 deals', rows[4]._w, 0.8);
  eq('4 deals is low confidence', rows[2]._conf, 'low');
  eq('5 deals is not', rows[3]._conf, 'ok');
  eq('no deals field is low confidence', rows[0]._conf, 'low');
}

// shrinkage: the same observed discount counts for more when more deals stand behind it
{
  const rows = [mk({ project: 'thin', median_psf: 900, vol_12m: 2 }), mk({ project: 'solid', median_psf: 900, vol_12m: 20 }),
                mk({ project: 'par', median_psf: 1500, vol_12m: 10 })];
  score(rows, DMED, PRIOR);
  ok('20 deals at -40% outranks 2 deals at -40% on value', rows[1]._sc[0] > rows[0]._sc[0]);
  ok('2 deals at -40% still outranks par on value (shrunk, not zeroed)', rows[0]._sc[0] > rows[2]._sc[0]);
}

// a two-deal outlier cannot beat a well-traded, moderately cheap project on value
{
  const rows = [mk({ project: 'outlier', median_psf: 465, vol_12m: 2 }),      // -69% observed, -19.7% effective
                mk({ project: 'steady', median_psf: 1125, vol_12m: 20 }),     // -25% observed, -20.0% effective
                mk({ project: 'par', median_psf: 1500, vol_12m: 10 })];
  score(rows, DMED, PRIOR);
  ok('a -25% discount on 20 deals outranks a -69% discount on 2 deals', rows[1]._sc[0] > rows[0]._sc[0]);
}

// ties share the average rank, and the Score does not depend on file order
{
  const pool = () => [
    mk({ project: 'fh-a', lease: 'FH', vol_12m: 2, median_psf: 1400 }),
    mk({ project: 'lh-90', lease: 90, vol_12m: 30, median_psf: 1400 }),
    mk({ project: 'fh-b', lease: 'FH', vol_12m: 2, median_psf: 1400 }),
    mk({ project: 'lh-70', lease: 70, vol_12m: 8, median_psf: 1600 }),
    mk({ project: 'fh-c', lease: 999, vol_12m: 2, median_psf: 1400 }),   // quasi-freehold: same 105 as FH
  ];
  const rows = pool(); score(rows, DMED, PRIOR);
  const by = {}; rows.forEach(r => { by[r.project] = r; });
  eq('identical freehold rows: identical lease rank (a vs b)', by['fh-a']._sc[2], by['fh-b']._sc[2]);
  eq('999-year lease ranks with freehold', by['fh-c']._sc[2], by['fh-a']._sc[2]);
  eq('identical rows: identical score (a vs b)', by['fh-a'].score, by['fh-b'].score);
  // three of five tied at the top of lease: average of positions 2,3,4 of 0..4 = 3 -> 75
  eq('tied group takes the average position', by['fh-a']._sc[2], 75);
  ok('the leasehold rows sit below the tie', by['lh-90']._sc[2] < 75 && by['lh-70']._sc[2] < by['lh-90']._sc[2]);
  const shuffled = pool().reverse(); score(shuffled, DMED, PRIOR);
  shuffled.forEach(r => eq(`order-invariant score (${r.project})`, r.score, by[r.project].score));
}

// a stale score from an earlier render is cleared, not carried
{
  const rows = [mk({ project: 'stale', median_psf: null, score: 99, _sc: [1, 2, 3, 4], _w: 0.9, _conf: 'ok' })];
  score(rows, DMED, PRIOR);
  eq('stale score cleared', rows[0].score, null);
  eq('stale breakdown cleared', rows[0]._sc, null);
  eq('stale weight cleared', rows[0]._w, null);
  eq('stale confidence cleared', rows[0]._conf, null);
}

// extremes: best on every factor is 100, worst is 0, the middle is 50, all integers 0..100
{
  const rows = [
    mk({ project: 'best', median_psf: 1000, vol_12m: 100, lease: 'FH', mrt_m: 100 }),
    mk({ project: 'mid', median_psf: 1500, vol_12m: 20, lease: 70, mrt_m: 800 }),
    mk({ project: 'worst', median_psf: 2000, vol_12m: 5, lease: 40, mrt_m: 2000 }),
  ];
  score(rows, DMED, PRIOR);
  eq('best on all four = 100', rows[0].score, 100);
  eq('middle on all four = 50', rows[1].score, 50);
  eq('worst on all four = 0', rows[2].score, 0);
  rows.forEach(r => ok(`integer score 0..100 (${r.project})`, Number.isInteger(r.score) && r.score >= 0 && r.score <= 100));
  rows.forEach(r => ok(`four factor ranks (${r.project})`, Array.isArray(r._sc) && r._sc.length === 4));
}

/* ---- the live feed: everyone with a median scored, labels match deal counts, order does not matter ---- */
const livePath = path.join(ROOT, 'data', 'live.json');
if (fs.existsSync(livePath)) {
  const live = JSON.parse(fs.readFileSync(livePath, 'utf8'));
  const P = live.projects && (live.projects.rows || live.projects);
  const drows = (live.districts && live.districts.rows) || [];
  if (Array.isArray(P) && P.length) {
    const dmed = {}; drows.forEach(r => { dmed[r.d] = r.median_psf; });
    const rows = P.map(r => Object.assign({}, r));
    const scored = score(rows, dmed, PRIOR);
    eq('live: every row with a median is scored', scored.length, rows.filter(r => r.median_psf).length);
    rows.forEach(r => {
      if (!r.median_psf) return;
      if (!Number.isInteger(r.score) || r.score < 0 || r.score > 100) fails.push(`live: ${r.project} (${r.district}) score ${r.score}`);
      const want = (r.vol_12m || 0) < PRIOR ? 'low' : 'ok';
      if (r._conf !== want) fails.push(`live: ${r.project} (${r.district}, ${r.vol_12m} deals) labelled ${r._conf}, want ${want}`);
    });
    // a shuffled file must score every project identically (ties by average rank, not file order)
    const key = r => r.project + '|' + r.district + '|' + r.median_psf;
    const first = {}; rows.forEach(r => { first[key(r)] = r.score; });
    const shuffled = P.map(r => Object.assign({}, r));
    for (let i = shuffled.length - 1; i > 0; i--) { const j = (i * 7919 + 13) % (i + 1); [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]; }
    score(shuffled, dmed, PRIOR);
    let moved = 0; shuffled.forEach(r => { if (r.median_psf && r.score !== first[key(r)]) moved++; });
    eq('live: scores unchanged after shuffling the file', moved, 0);
    const top = scored.slice().sort((a, b) => b.score - a.score).slice(0, 40);
    const low = top.filter(r => r._conf === 'low').length;
    console.log(`Live feed: ${rows.length} projects, ${scored.length} scored, ${rows.filter(r => r._conf === 'low').length} low confidence; top 40 carries ${low} low-confidence row${low === 1 ? '' : 's'}.`);
  }
}

if (fails.length) {
  console.error(`FAIL: ${fails.length} case(s)`);
  fails.forEach(f => console.error('  ' + f));
  process.exit(1);
}
console.log('PASS: project score - everyone scored, value confidence-weighted by deal count, ties share the average rank, order-invariant, stale scores cleared, extremes at 0 and 100, live feed consistent.');
