# 🐍 Greedy Snake · 经典贪吃蛇

一个基于原生 HTML / CSS / JavaScript 的经典贪吃蛇网页游戏（前端零框架依赖），并附带 FastAPI 后端提供账号系统与全球排行榜。默认使用 SQLite，克隆下来不需要任何数据库服务就能直接跑；也可切换到 MySQL，并支持 Render 一键云部署。

## ✨ 功能特性

- **三档难度**：低等（EASY）· 中等（MEDIUM）· 高等（HARD）
- **障碍物系统**：障碍物支持单格与长条（最长 3 格）两种形态——低等 16 个单格，中等单格与长条混合，高等长度随机且每 25 步自动换位
- **动态加速**：随分数提升，蛇的移动速度逐渐加快
- **计时器**：游戏内实时显示存活时间（MM:SS）
- **本局统计**：游戏结束后展示存活时间、食物数量、移动步数、最高速度、平均步速
- **本机排行榜**：每个难度独立 Top 10 排名，数据保存在浏览器 localStorage
- **玩家账号**：注册 / 登录（密码哈希存储），登录后成绩可提交到全球排行榜
- **全球排行榜**：每个难度独立云端 Top 10，所有玩家共享；排行榜面板可切换"本机 / 全球"
- **玩家昵称**：支持输入自定义昵称，自动保存
- **开局倒计时**：3-2-1-GO! 倒计时，预留操作准备时间
- **移动端适配**：触摸滑动 + 虚拟方向键，完整支持手机游玩
- **暂停 / 重开**：Space 暂停，R 重新开始，Esc 返回菜单
- **Render 云部署**：通过 `render.yaml` 蓝图一键部署前后端一体的完整服务

## 🎮 难度说明

| 参数 | 低等 EASY | 中等 MEDIUM | 高等 HARD |
|------|-----------|-------------|-----------|
| 初始速度 | 220ms | 150ms | 125ms |
| 加速间隔 | 每 100 分 | 每 50 分 | 每 40 分 |
| 最高速度 | 120ms | 50ms | 45ms |
| 障碍物数 | 16 个单格 | 10 格（单格 + 长条混合） | 15 格（长度随机） |
| 障碍形状 | 全部长度 1 | 长度 1、2、3 并存 | 长度 1 ~ 3 随机 |
| 障碍换位 | 无 | 无 | 每 25 步 |

## 📁 项目结构

```
Greedy-Snake/
├── index.html                # 落地页：难度选择 + 注册 / 登录
├── terms.html                # 用户协议（注册时需勾选同意）
├── privacy.html              # 隐私政策（注册时需勾选同意）
├── web_game/                 # 游戏源码（纯静态）
│   ├── page/
│   │   └── home.html         # 游戏页面
│   ├── snake.js              # 游戏逻辑（含排行榜 / 账号 API 对接）
│   └── style.css             # 样式文件
├── backend/                  # FastAPI 后端
│   ├── main.py               # 路由：健康检查、认证、成绩提交、全球排行榜
│   ├── models.py             # 数据模型（SQLAlchemy）
│   ├── database.py           # 数据库连接（默认 SQLite，可切 MySQL）
│   ├── setup_db.py           # 数据库一键初始化脚本
│   └── requirements.txt      # Python 依赖
├── greedy_snake.db           # SQLite 数据库文件（首次启动自动生成，已 gitignore）
├── render.yaml               # Render 云部署蓝图
├── .env.example              # 环境变量模板（改用 MySQL 时复制为 .env）
├── .gitignore
└── README.md
```

> 后端同时托管静态资源：`/` 返回落地页，`/web_game/` 挂载游戏页面，因此单个 FastAPI 服务即可运行完整应用。

## 🚀 运行方式

**线上游玩（推荐，无需任何本地配置）**

直接打开 Render 部署的地址即可注册、登录、游玩，成绩进入全球榜单：

```
https://<你的服务名>.onrender.com
```

> Render 免费实例 15 分钟无访问会休眠，冷启动约需 30–60 秒，期间登录失败属正常现象，稍等重试即可。

**本地运行（改代码调试时使用）**

游戏必须登录才能进入，所以本地也要启动后端。**不需要任何数据库服务**——默认使用 SQLite，数据库文件会在首次启动时自动创建为项目根目录的 `greedy_snake.db`：

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

浏览器打开 http://127.0.0.1:8000/ ，注册一个账号即可开玩。

> **改用 MySQL**：把 `.env.example` 复制为 `.env` 并填入连接串（`DATABASE_URL`），就会从 SQLite 切换到 MySQL。填入与 Render 部署相同的云数据库连接串时，本地与线上共享同一份全球榜单；连接本机 MySQL 时两份数据相互独立。不创建 `.env`（或把其中 `DATABASE_URL` 注释掉）时使用 SQLite。
>
> 注意：纯静态方式（`python -m http.server`）因缺少后端登录接口无法进入游戏，仅适合调试静态样式。

## 🕹️ 操作方式

| 平台 | 操作 |
|------|------|
| 桌面端 | `↑` `↓` `←` `→` 移动 · `Space` 暂停 · `R` 重新开始 · `Esc` 返回菜单 |
| 移动端 | 滑动画布 / 点击虚拟方向键移动 · 点击暂停键暂停 |

## 🛠️ 技术栈

- **HTML5 Canvas** — 游戏画面渲染
- **原生 JavaScript** — 游戏逻辑（无框架依赖）
- **CSS3** — 暗色主题 UI + 响应式布局
- **localStorage** — 本地数据持久化（排行榜 / 玩家昵称）
- **FastAPI + SQLAlchemy** — 账号系统与全球排行榜后端
- **SQLite（默认）/ MySQL（可选）** — 数据存储；SQLite 零配置开箱即用，MySQL 用于云端多玩家共享榜单

## 🧩 后端：账号与全球排行榜

排行榜面板可切换"本机 / 全球"：成绩提交到数据库，所有玩家共享一个榜单。本机榜存在浏览器 localStorage 里，与后端无关。

### 1. 准备数据库

**SQLite（默认）**：什么都不用做，首次启动会自动创建 `greedy_snake.db`。

**MySQL（可选）**：需要先手动建库，并在 `.env` 里配好连接串。

```sql
CREATE DATABASE greedy_snake CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```bash
# 在项目根目录的 .env 里写入（密码含特殊字符需 URL 编码）
# DATABASE_URL=mysql+pymysql://root:你的密码@localhost:3306/greedy_snake?charset=utf8mb4

# 一键初始化：先测连接，再建库，最后建表
python backend/setup_db.py
```

### 2. 安装依赖并启动

```bash
pip install -r backend/requirements.txt

# 在项目根目录启动（同时托管前端页面）
uvicorn backend.main:app --reload
```

> **依赖版本已用 `==` 钉死**，避免重新部署时被静默升级到不兼容的大版本。升级流程：改版本号 → 重新安装 → 跑一遍测试再提交。
>
> 想把间接依赖也一起冻住（真正的可复现构建），用 `pip-compile`：
>
> ```bash
> pip install pip-tools
> pip-compile -o backend/requirements.lock.txt backend/requirements.txt
> ```
>
> **不要用 `pip freeze` 生成 lock 文件**——在 Windows 上 freeze 会漏掉 Linux 专属的 `uvloop`，还会带上 Windows 专属的 `colorama`，这份文件拿到 Linux 上是错的。

### 3. 访问

| 地址 | 说明 |
|------|------|
| http://127.0.0.1:8000/ | 游戏首页（FastAPI 托管） |
| http://127.0.0.1:8000/docs | API 交互式文档 |
| `POST /api/auth/register` | 注册账号 |
| `POST /api/auth/login` / `POST /api/auth/logout` | 登录 / 退出 |
| `GET /api/auth/me` | 查询当前登录用户 |
| `GET /api/leaderboard/{difficulty}` | 全球 Top 10 |
| `POST /api/scores` | 提交成绩（需登录） |
| `GET /api/health` | 健康检查 |

## ☁️ 云部署（Render）

仓库根目录的 `render.yaml` 是 Render Blueprint 部署配置：单个 Python Web 服务同时运行后端 API 并托管前端页面，数据库连接串通过环境变量 `DATABASE_URL` 注入（当前使用阿里云 RDS MySQL，任何 MySQL 兼容的云数据库均可）。

在 Render 控制台选择 "New → Blueprint" 并导入本仓库即可一键部署；部署时在控制台填入你的 `DATABASE_URL`。三点注意：

- **线上务必配置 `DATABASE_URL`**：不配置时会回落到默认的 SQLite，而 Render 的容器文件系统是临时的——每次重新部署或实例重启数据都会丢失，也无法多实例共享榜单。SQLite 只适合本地开发。
- **密码中的特殊字符必须 URL 编码**：例如密码以 `@` 结尾时写成 `%40`，否则 `@` 会被当作连接串的分隔符导致域名解析失败。
- **阿里云 RDS 需要配置白名单**：Render 的出口 IP 是动态的，无法逐个放通，只能在 RDS 白名单中添加 `0.0.0.0/0`。请务必使用高强度密码，并确保 `.env`、连接串不会进入版本库。

## 📄 License

本项目仅供学习和个人使用。
