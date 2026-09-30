# フロントの静的ファイルだけを作るイメージ。nginx（設定・受保護メディアの規則）はこのイメージに含めない。
# docker-compose の frontend サービス（nginx 実行環境）が、リポジトリの nginx/default.conf を読み取り専用で
# マウントし、このイメージが frontend_dist ボリュームへ書き出した静的ファイルを配信する。
# → 静的ファイルを古い版へ戻しても、nginx の安全設定（/media/ 404・/_protected_media/ internal）は変わらない。
FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_BASE_PATH
ARG VITE_API_BASE_URL
ENV VITE_BASE_PATH=$VITE_BASE_PATH
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM alpine:3.20 AS assets

COPY --from=build /app/dist /opt/frontend-dist

# 起動するとボリューム /dist を空にしてから静的ファイルを書き出して終了する（一回限り）。
CMD ["sh", "-c", "test -f /opt/frontend-dist/index.html && find /dist -mindepth 1 -delete && cp -a /opt/frontend-dist/. /dist/ && mkdir -p /dist/static && echo 'frontend assets published'"]
