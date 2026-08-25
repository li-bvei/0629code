# Frontend

Vue 3 + TypeScript + Vite + Element Plus。详细项目背景见根目录 `AI_CONTEXT.md` / `docs/PROJECT.md`。

## 本地启动

```bash
npm install
npm run dev -- --port 5174
```

或直接执行 `./dev.sh`（先把 `/opt/homebrew/bin` 补进 `PATH` 再执行同样的命令，沙盒/受限 shell 环境下 `npm`/`node` 可能不在默认 `PATH` 里，用这个脚本更可靠）。本地固定使用 `5174` 端口，不是 Vite 默认的 `5173`。

访问：`http://localhost:5174/`

后端 API 通过 `vite.config.ts` 的 proxy 转发 `/api` 到 `http://127.0.0.1:8000`，本地需要先按 `AI_CONTEXT.md` 说明启动 Django 后端。

## 构建

```bash
npm run build
```

## 常用检查

```bash
npm run build
```

`vue-tsc` 类型检查已包含在 `npm run build` 流程里，构建通过即代表类型检查通过。
