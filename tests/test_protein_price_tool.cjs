const test = require('node:test');
const assert = require('node:assert/strict');
const tool = require('../assets/tools/protein-price/calculator.js');

const base = {price:'899', mass:'900', protein:'75', delivery:''};
const other = {price:'849', mass:'750', protein:'82', delivery:''};
const empty = {price:'', mass:'', protein:'', delivery:''};

test('label example and Czech display use actual protein, not powder mass', () => {
  const result = tool.compare(base, other);
  assert.equal(result.error, undefined);
  assert.equal(tool.asCzk(result.first.per100Cents), '133,19 Kč');
  assert.equal(tool.asCzk(result.first.per25Cents), '33,30 Kč');
  assert.equal(tool.asGrams(result.first.proteinHundredths), '675,00 g');
  assert.equal(tool.asCzk(result.second.per100Cents), '138,05 Kč');
  assert.equal(tool.asGrams(result.second.proteinHundredths), '615,00 g');
});

test('one-pack mode is meaningful without asking for B', () => {
  const result = tool.compare(base, empty);
  assert.equal(result.error, undefined);
  assert.equal(result.second, null);
  assert.equal(result.shippingComparison, 'single');
});

test('only comparable shipping data permits a two-pack price verdict', () => {
  const noShipping = tool.compare(base, other);
  assert.equal(noShipping.shippingComparison, 'excluded');
  assert.match(tool.priceVerdict(noShipping), /Porovnání nezahrnuje dopravu/);
  assert.match(tool.priceVerdict(noShipping), /balení A/);

  const bothShipping = tool.compare({...base, delivery:'0'}, {...other, delivery:'99'});
  assert.equal(bothShipping.shippingComparison, 'included');
  assert.match(tool.priceVerdict(bothShipping), /Doprava je zahrnuta u obou/);

  for(const result of [
    tool.compare({...base, delivery:'99'}, other),
    tool.compare(base, {...other, delivery:'0'})
  ]){
    assert.equal(result.shippingComparison, 'incomplete');
    assert.match(tool.priceVerdict(result), /Nelze férově určit levnější balení/);
    assert.doesNotMatch(tool.priceVerdict(result), /Nižší cenu.*balení [AB]/);
  }
  assert.equal(tool.priceVerdict(tool.compare(base, empty)), '');
});

test('optional delivery adds to exactly one whole-pack purchase', () => {
  const price = tool.parsePack({...base, delivery:'99,50'});
  assert.equal(price.totalCents, 99850n);
  assert.equal(tool.asCzk(price.per100Cents), '147,93 Kč');
  assert.equal(price.deliveryIncluded, true);
  assert.equal(tool.parsePack(base).deliveryIncluded, false);
});

test('strict decimals accept Czech or English punctuation without loose parseFloat', () => {
  assert.equal(tool.parseHundredths('75,25', 100, false), 7525n);
  assert.equal(tool.parseHundredths('75.25', 100, false), 7525n);
  assert.equal(tool.parseHundredths(' 75 ', 100, false), 7500n);
  for(const value of ['75,255', '1e6', '-5', '99abc', '0', '100,01', 'Infinity', '1 000']){
    assert.equal(tool.parseHundredths(value, 100, false), null, value);
  }
  assert.equal(tool.parseHundredths('0', 100000, true), 0n);
});

test('incomplete B fails without inventing its nutrition label', () => {
  const result = tool.compare(base, {...empty, price:'849'});
  assert.match(result.error, /Balení B|balení B/);
});

test('invalid product fields do not produce a misleading price', () => {
  for(const bad of [
    {...base, mass:'0'}, {...base, mass:'1.5'}, {...base, mass:'10001'},
    {...base, price:'0'}, {...base, protein:'0'}, {...base, protein:'101'},
    {...base, delivery:'-1'}, {...base, price:'1,234'},
    {...base, protein:'75%'}
  ]) assert.equal(tool.parsePack(bad), null);
});

test('rounds in integer cents exactly, including half-up threshold', () => {
  const r = tool.parsePack({price:'1',mass:'8',protein:'100',delivery:''});
  assert.equal(tool.asCzk(r.per100Cents), '12,50 Kč');
  // 100 g protein costs exactly 0.125 CZK => 0.13 CZK.
  const tie = tool.parsePack({price:'0,01', mass:'8', protein:'100', delivery:''});
  assert.equal(tool.asCzk(tie.per100Cents), '0,13 Kč');
});

test('does not depend on browser globals for auditable calculations', () => {
  assert.equal(typeof global.document, 'undefined');
  assert.equal(tool.compare(base, empty).first.totalCents, 89900n);
});
