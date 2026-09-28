# 2026-09-28 P2 文件管理分支（codex/p2-documents）

基于：`codex/p1-case-workspace` `dde7e4f`。不修改 accounting 模块，与会计分支、Visa 分支相互独立。未推送、未部署。不新建 materials 模块，不连接或迁移 Google Drive，不做完整版本树。

## 实现

- **分类**：`category`（8 类），一览可以按分类筛选，上传时可以选择分类。
- **元数据**：
  - 保留原始文件名，保存名改为 UUID（`case_documents/YYYY/MM/`）；
  - 大小、SHA-256；
  - MIME 按扩展名推断，不信任浏览器申报的值；
  - 上传人由后端写入，前端无法指定；
  - 已有文件的路径保持不变。
- **上传检查**（`upload_policy.py`）：
  - 扩展名白名单：PDF、图片、Office、CSV/TXT、ZIP；
  - 主要格式检查文件头签名是否与扩展名一致；
  - 拒绝可执行文件和脚本（MZ、ELF、shebang、`<script`、`<?php`）；
  - 拒绝空文件；大小上限 `DOCUMENT_MAX_UPLOAD_BYTES`，默认 20MB。
- **Case / Checklist 关联**：上传时可以关联同一案件的必要资料（写审计 `document_checklist_linked`），文件详情里显示关联的必要资料。
- **归档 / 恢复**：
  - `POST documents/{id}/archive/`（可填原因）、`restore/`；
  - 一览默认不显示已归档文件（`?archived=only|all` 可以查看）；
  - 归档后仍可通过受保护下载获取；
  - 写 Timeline（`document_archived` / `document_restored`）和审计。
- **替换历史**：
  - 替换时**不删除**替换前的文件，把原始文件名、大小、SHA-256、MIME、原因、执行人记入 `DocumentReplacement`；
  - `GET documents/{id}/history/` 查看（不返回旧文件的保存名，也不提供旧文件下载）；
  - 沿用 P1 的替换审计和 Timeline。
- **受保护下载**：原样沿用 P0 的实现，新的保存路径也通过 realpath 校验。
- **备份与恢复**：写在 `docs/DEPLOY.md`「案件文件的备份与恢复」。
- **前端**：
  - 书类一览：分类、归档筛选、元数据列、替换、历史、归档/恢复；
  - Action Bar 的文件抽屉：上传时选择分类，关联必要资料。

## Migration

`documents/0004_document_metadata_archive_replacements`（加法；把 `file.upload_to` 改为函数，不影响既有数据）。

## 验证

- 后端 `python manage.py test`：220 项全部通过（P1 的 213 项 + 本分支 7 项）。
- 前端 `npm run build` 通过，`npm run test:unit` 6 项通过；`makemigrations --check`：无差异。
- 浏览器实测：未完成。

## 行为变化（需要注意）

以前替换文件时，旧文件会被删除；现在会保留。替换频繁时媒体卷会变大，请结合备份容量一起确认。
