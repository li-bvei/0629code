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

`FIELD_ENCRYPTION_KEY` 用于加密マイナンバー（`Customer`/`FamilyMember`/`CompanyStaff` 的 `my_number` 字段），首次部署前必须生成一个真实值并写入 `.env.prod`（`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`），且之后不能再更改——改了旧数据就无法解密。

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
127.0.0.1:8081
```

公网访问应通过宝塔 / Nginx 反向代理到：

```text
http://127.0.0.1:8081
```

当前服务器端口分配（2026-08-03 已核对）：

- `8080`：服务器原有 Java / `jsvc` 服务，本项目不可占用。
- `8081`：本项目 `0629code-frontend-1`。
- `8090`：另一个项目 `sunrise-diagnosis-web`，不可停止或改作本项目端口。

宝塔 vhost 中 `/sun/` 应保留完整路径转发：

```nginx
location ^~ /sun/ {
    proxy_pass http://127.0.0.1:8081;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

`proxy_pass` 末尾不要加 `/`，否则 `/sun/admin/`、`/sun/api/` 等路径会被错误改写。

## django-axes 首次迁移兼容

如果生产数据库已经存在 `axes_accessattempt`，但 `showmigrations axes` 显示 `0001_initial` 未应用，普通 `migrate` 会报 `Table 'axes_accessattempt' already exists`。先核对迁移状态：

```bash
docker compose --env-file .env.prod exec backend python manage.py showmigrations axes
```

仅在初始迁移显示未应用且现有 axes 表来自此前安装时，执行：

```bash
docker compose --env-file .env.prod exec backend python manage.py migrate axes --fake-initial
docker compose --env-file .env.prod exec backend python manage.py migrate
```

不要删除现有 axes 表，也不要执行 `docker compose down -v`。如果 `--fake-initial` 仍报错，应先检查 axes 表是否只创建了一部分，不能直接使用普通 `--fake`。
