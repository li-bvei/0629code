// フロント単体テストの実行：既存の esbuild（vite 依存）で TypeScript をまとめ、Node 標準の node:test で走らせる。
// 追加の依存パッケージは使わない。
import { build } from 'esbuild'
import { readdirSync, rmSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { spawnSync } from 'node:child_process'

const root = new URL('..', import.meta.url).pathname
const outDir = join(root, 'node_modules', '.cache', 'unit-tests')
rmSync(outDir, { recursive: true, force: true })
mkdirSync(outDir, { recursive: true })

const entries = readdirSync(join(root, 'tests')).filter((name) => name.endsWith('.test.ts'))
await build({
  entryPoints: entries.map((name) => join(root, 'tests', name)),
  outdir: outDir,
  bundle: true,
  platform: 'node',
  format: 'esm',
  outExtension: { '.js': '.mjs' },
  external: ['vue'],
  logLevel: 'error',
})
const files = readdirSync(outDir).filter((name) => name.endsWith('.mjs')).map((name) => join(outDir, name))
const result = spawnSync(process.execPath, ['--test', ...files], { stdio: 'inherit', cwd: root })
process.exit(result.status ?? 1)
