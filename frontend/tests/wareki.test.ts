import assert from 'node:assert/strict'
import { test } from 'node:test'
import { formatBirthDateWithEra, formatSeireki, toWareki } from '../src/utils/wareki'

test('西暦の後に和暦を添える（表示だけ）', () => {
  assert.equal(formatBirthDateWithEra('1990-05-01'), '1990年5月1日（平成2年5月1日）')
  assert.equal(formatBirthDateWithEra('2000-12-31'), '2000年12月31日（平成12年12月31日）')
  assert.equal(formatSeireki('1990-05-01'), '1990年5月1日')
})

test('明治・大正・昭和・平成・令和と改元日・元年', () => {
  assert.equal(toWareki('1868-01-25'), '明治元年1月25日')
  assert.equal(toWareki('1912-07-29'), '明治45年7月29日')
  assert.equal(toWareki('1912-07-30'), '大正元年7月30日')
  assert.equal(toWareki('1926-12-24'), '大正15年12月24日')
  assert.equal(toWareki('1926-12-25'), '昭和元年12月25日')
  assert.equal(toWareki('1989-01-07'), '昭和64年1月7日')
  assert.equal(toWareki('1989-01-08'), '平成元年1月8日')
  assert.equal(toWareki('2019-04-30'), '平成31年4月30日')
  assert.equal(toWareki('2019-05-01'), '令和元年5月1日')
  assert.equal(toWareki('2020-02-29'), '令和2年2月29日')
})

test('空・不正な日付・明治より前', () => {
  assert.equal(formatBirthDateWithEra(null), '-')
  assert.equal(formatBirthDateWithEra(''), '-')
  assert.equal(formatBirthDateWithEra('2021-02-29'), '2021-02-29')  // 存在しない日付は元の文字列だけ
  assert.equal(formatBirthDateWithEra('abc'), 'abc')
  assert.equal(formatBirthDateWithEra('1850-01-01'), '1850年1月1日')
  assert.equal(toWareki('1868-01-24'), '')
})
