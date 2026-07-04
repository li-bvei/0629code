# DEPLOY

## 服务器目录

生产服务器项目目录：

```bash
/www/wwwroot/0629code
```

进入项目目录：

```bash
cd /www/wwwroot/0629code
```

## 生产环境变量文件

生产环境使用：

```bash
.env.prod
```

不要使用 `.env.production` 作为部署环境文件名。

可以参考根目录的 `.env.prod.example` 创建 `.env.prod`，但不要提交真实密码。

## Docker Compose 命令

所有生产部署命令统一使用：

```bash
docker compose --env-file .env.prod build
docker compose --env-file .env.prod up -d
```

后端启动时会执行 `collectstatic`，Django Admin / SimpleUI 静态文件会写入 Docker 共享卷 `static_volume`。
前端 Nginx 直接从该共享卷提供 `/static/` 和 `/sun/static/`。

上传文件使用共享卷 `media_volume`，前端 Nginx 直接提供 `/media/` 和 `/sun/media/`。

查看服务：

```bash
docker compose --env-file .env.prod ps
```

查看日志：

```bash
docker compose --env-file .env.prod logs -f
```

重启服务：

```bash
docker compose --env-file .env.prod restart
```

停止服务：

```bash
docker compose --env-file .env.prod down
```

## 更新上线流程

```bash
cd /www/wwwroot/0629code
git pull
docker compose --env-file .env.prod build
docker compose --env-file .env.prod up -d
```

## 访问地址

前端：

```text
http://43.139.37.150/sun/
```

Django Admin：

```text
http://43.139.37.150/sun/admin/
```

API：

```text
http://43.139.37.150/sun/api/
```

## 宝塔反向代理

Docker 前端服务只绑定服务器本机：

```text
127.0.0.1:8080
```

公网访问应通过宝塔 / Nginx 反向代理到：

```text
http://127.0.0.1:8080
```
