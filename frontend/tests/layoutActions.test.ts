import { test } from 'node:test'
import assert from 'node:assert/strict'
import { splitBarActions, splitRowActions, type ActionItem } from '../src/components/layout/actions'

const noop = () => {}
const item = (key: string, extra: Partial<ActionItem> = {}): ActionItem => ({ key, label: key, onClick: noop, ...extra })

test('splitBarActions: collapse 指定で 3 つに分け、順序を保つ', () => {
  const result = splitBarActions([
    item('a', { collapse: 'never' }),
    item('b'),
    item('c', { collapse: 'always' }),
    item('d', { collapse: 'auto' }),
    item('e', { collapse: 'never' }),
  ])
  assert.deepEqual(result.pinned.map((a) => a.key), ['a', 'e'])
  assert.deepEqual(result.collapsible.map((a) => a.key), ['b', 'd'])
  assert.deepEqual(result.overflow.map((a) => a.key), ['c'])
})

test('splitBarActions: hidden の操作はどこにも出さない', () => {
  const result = splitBarActions([item('a', { hidden: true }), item('b', { collapse: 'never', hidden: true }), item('c')])
  assert.deepEqual(result.pinned, [])
  assert.deepEqual(result.collapsible.map((a) => a.key), ['c'])
  assert.deepEqual(result.overflow, [])
})

test('splitRowActions: 先頭 inline 個をボタン、残りをメニューへ', () => {
  const result = splitRowActions([item('a'), item('b'), item('c')], 1)
  assert.deepEqual(result.inline.map((a) => a.key), ['a'])
  assert.deepEqual(result.overflow.map((a) => a.key), ['b', 'c'])
})

test('splitRowActions: 危険な操作はボタンにせず、メニューの最後へ回す', () => {
  const result = splitRowActions([item('del', { danger: true }), item('edit'), item('view'), item('pdf')], 2)
  assert.deepEqual(result.inline.map((a) => a.key), ['edit', 'view'])
  assert.deepEqual(result.overflow.map((a) => a.key), ['pdf', 'del'])
})

test('splitRowActions: collapse always はメニューへ、hidden は除外、inline 0 は全部メニュー', () => {
  const always = splitRowActions([item('a', { collapse: 'always' }), item('b'), item('c', { hidden: true })], 2)
  assert.deepEqual(always.inline.map((a) => a.key), ['b'])
  assert.deepEqual(always.overflow.map((a) => a.key), ['a'])
  const none = splitRowActions([item('a'), item('b')], 0)
  assert.deepEqual(none.inline, [])
  assert.deepEqual(none.overflow.map((a) => a.key), ['a', 'b'])
})
