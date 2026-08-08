/* Singapore property loan + stamp-duty engine.
 *
 * Extracted verbatim from template.html so that the published dashboard and any private
 * decision model share one implementation of the MAS / IRAS / HDB arithmetic. The only change
 * from the original is that the rules object arrives as a parameter (R) instead of being read
 * from the module-level `D.rules` global. scripts/test_engine_parity.js asserts exact equality
 * against the in-template copy across an input grid; run it after touching anything here.
 *
 * Nothing in this file is advice. It computes published rules and nothing more.
 */
(function (root) {
  'use strict';

  // monthly payment
  function pmt(rateAnnual, years, principal) {
    const r = rateAnnual / 12, n = years * 12;
    if (r === 0) return principal / n;
    return principal * r / (1 - Math.pow(1 + r, -n));
  }

  // principal affordable given a monthly ceiling
  function loanFromInstalment(maxInst, rateAnnual, years) {
    const r = rateAnnual / 12, n = years * 12;
    if (maxInst <= 0) return 0;
    if (r === 0) return maxInst * n;
    return maxInst * (1 - Math.pow(1 + r, -n)) / r;
  }

  // Buyer's Stamp Duty — marginal tiers, IRAS schedule from 15 Feb 2023
  function bsd(price, brackets) {
    let tax = 0, prev = 0;
    for (const b of brackets) {
      const cap = b.up_to === null ? Infinity : b.up_to;
      if (price > prev) { tax += (Math.min(price, cap) - prev) * b.rate; prev = cap; } else break;
    }
    return tax;
  }

  /* ---------- loan engine ----------
   * inp: {age, income, incomeVar, debt, cash, price, type:'hdb'|'ec'|'private',
   *       loan:'hdb'|'bank', cz:'SC'|'PR'|'Foreigner'|'Entity', count, tenure, rate}
   * R:   the parsed rules.json object.
   *
   * NOTE on `type`: 'ec' applies MSR, which is correct only for an EC bought from a developer.
   * A resale EC past its MOP is TDSR-only and must be passed as 'private'. See rules.json
   * msr.applies_to. This mirrors the original template behaviour and is deliberately not
   * "fixed" here, so parity holds; callers are responsible for choosing the right type.
   */
  function computeLoan(inp, R) {
    const isHDB = inp.type === 'hdb', isEC = inp.type === 'ec', isPrivate = inp.type === 'private';
    const hdbLoan = isHDB && inp.loan === 'hdb';
    const msrApplies = isHDB || isEC;
    // income recognised in the debt tests: fixed + 70% of variable/rental (MAS haircut)
    const incomeEff = inp.income + 0.7 * (inp.incomeVar || 0);
    // tenure caps (EC bought from a developer is grouped with public housing at 30y)
    const absCap = hdbLoan ? R.ltv.hdb_concessionary.tenure_cap_years
                 : isHDB ? R.tenure_cap_years.hdb_bank
                 : isEC ? R.tenure_cap_years.ec_bank
                 : R.tenure_cap_years.private_bank;
    const cliffTenure = isHDB ? R.ltv.reduction_trigger.tenure_gt_years_hdb : R.ltv.reduction_trigger.tenure_gt_years_private;
    const fullLtvMaxTenure = Math.min(cliffTenure, R.ltv.reduction_trigger.age_plus_tenure_gt - inp.age); // can be <5: no slider tenure keeps full LTV
    let tenure = Math.min(inp.tenure, absCap);
    if (hdbLoan) tenure = Math.max(1, Math.min(tenure, R.ltv.reduction_trigger.age_plus_tenure_gt - inp.age)); // HDB loan must end by 65
    // LTV tier (HDB loan: flat 75%, no reduced tier, no minimum cash)
    const loanKey = inp.count == 0 ? 'loan1' : (inp.count == 1 ? 'loan2' : 'loan3plus');
    const ltvSpec = R.ltv.bank_individual[loanKey];
    const reduced = !hdbLoan && ((tenure > cliffTenure) || ((inp.age + tenure) > R.ltv.reduction_trigger.age_plus_tenure_gt));
    const ltv = hdbLoan ? R.ltv.hdb_concessionary.max : (reduced ? ltvSpec.reduced : ltvSpec.max);
    const cashMinFrac = hdbLoan ? R.ltv.hdb_concessionary.cash_min : (reduced ? (ltvSpec.cash_min_reduced || ltvSpec.cash_min) : ltvSpec.cash_min);
    // debt tests at the floor or the actual rate, whichever is higher (MAS; HDB loans use a 3% floor)
    const floor = hdbLoan ? R.ltv.hdb_concessionary.stress_floor : R.tdsr.stress_rate;
    const stress = Math.max(floor, inp.rate);
    const byLTV = inp.price * ltv;
    const tdsrCeil = R.tdsr.limit * incomeEff - inp.debt;
    const byTDSR = loanFromInstalment(tdsrCeil, stress, tenure);
    let byMSR = Infinity;
    if (msrApplies) byMSR = loanFromInstalment(R.msr.limit * incomeEff, stress, tenure);
    const maxLoan = Math.max(0, Math.min(byLTV, byTDSR, byMSR));
    const bind = maxLoan === byLTV ? 'LTV (cash)' : (maxLoan === byTDSR ? 'TDSR (income)' : 'MSR (income)');
    // apply: min cash floor = cashMinFrac x price; the rest of the downpayment can be CPF or cash
    const loan = maxLoan;
    const downpay = inp.price - loan;
    const cashMin = inp.price * cashMinFrac;
    const cpfOrCash = Math.max(0, downpay - cashMin);
    // duties
    const absdRates = R.absd.rates[inp.cz] || R.absd.rates.SC;
    const absd = inp.price * absdRates[Math.min(2, inp.count)];
    const stampBSD = bsd(inp.price, R.bsd.brackets);
    const legal = 4000;
    const upfront = downpay + stampBSD + absd + legal;
    // instalments
    const instActual = pmt(inp.rate, tenure, loan);
    const instStress = pmt(stress, tenure, loan);
    const tdsrUsed = (instStress + inp.debt) / incomeEff;
    const msrUsed = msrApplies ? instStress / incomeEff : null;
    const bufferAfter = inp.cash - upfront;
    const bufferMonths = instActual > 0 ? bufferAfter / instActual : 0;
    const bufferMonthsStress = instStress > 0 ? bufferAfter / instStress : 0;
    return {
      isHDB, isEC, isPrivate, hdbLoan, msrApplies, incomeEff, tenure, absCap, fullLtvMaxTenure, cliffTenure, reduced, ltv, cashMinFrac, stress,
      byLTV, byTDSR, byMSR, maxLoan, bind, loan, downpay, cashMin, cpfOrCash, absd, absdRate: absdRates[Math.min(2, inp.count)],
      stampBSD, legal, upfront, instActual, instStress, tdsrUsed, msrUsed, bufferAfter, bufferMonths, bufferMonthsStress
    };
  }

  /* ---------- derived helpers (new; no counterpart in template.html) ---------- */

  // Largest price supportable given income, cash and the rules — bisection on computeLoan,
  // because price enters both the LTV ceiling and the duty stack non-linearly.
  // Returns the price at which upfront cash required exactly exhausts inp.cash.
  function maxPriceForCash(inp, R, hi) {
    let lo = 0, top = hi || 20000000;
    if (computeLoan(Object.assign({}, inp, { price: 1000 }), R).upfront > inp.cash) return 0;
    for (let i = 0; i < 60; i++) {
      const mid = (lo + top) / 2;
      if (computeLoan(Object.assign({}, inp, { price: mid }), R).upfront <= inp.cash) lo = mid; else top = mid;
    }
    return lo;
  }

  // Outstanding principal after yearsPaid of a level-payment loan. Straight-line depreciation of
  // the balance understates it badly in the early years, which flatters any equity projection.
  function balanceAfter(principal, rateAnnual, years, yearsPaid) {
    const r = rateAnnual / 12, n = Math.round(years * 12), m = Math.min(n, Math.round(yearsPaid * 12));
    if (n <= 0) return 0;
    if (r === 0) return Math.max(0, principal * (1 - m / n));
    const g = Math.pow(1 + r, n), h = Math.pow(1 + r, m);
    return Math.max(0, principal * (g - h) / (g - 1));
  }

  const API = { pmt, loanFromInstalment, bsd, computeLoan, maxPriceForCash, balanceAfter };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.ENGINE = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
