# 🐍 Greedy Snake · 经典贪吃蛇

一个基于原生 HTML / CSS / JavaScript 的经典贪吃蛇网页游戏（前端零框架依赖），并附带 FastAPI 后端提供账号系统与全球排行榜，数据存 MySQL，支持 Render 一键云部署。

## ✨ 功能特性

- **三档难度**：低等（EASY）· 中等（MEDIUM）· 高等（HARD）
- **障碍物系统**：障碍物支持单格与长条（最长 3 格）两种形态——低等 16 格全为单格，中等 30 格单格与长条混合，高等 45 格且长度随机、每 25 步自动换位
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
| 障碍物格数 | 16 格（16 段） | 30 格（16 段） | 45 格（约 17~30 段） |
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
│   ├── database.py           # 数据库连接（MySQL）
│   ├── setup_db.py           # 数据库一键初始化脚本
│   ├── tests/                # 后端接口测试（跑在独立的 MySQL 测试库上）
│   └── requirements.txt      # Python 依赖
├── pytest.ini                # pytest 配置
├── render.yaml               # Render 云部署蓝图
├── .env.example              # 环境变量模板（复制为 .env 后填写连接串）
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

游戏必须登录才能进入，所以本地也要启动后端，并保证 **MySQL 服务正在运行**：

```bash
# 1. 装依赖
pip install -r backend/requirements.txt

# 2. 建库 + 建表（会先测连接，密码不对会给出明确提示）
python backend/setup_db.py

# 3. 启动
uvicorn backend.main:app --reload
```

浏览器打开 http://127.0.0.1:8000/ ，注册一个账号即可开玩。

> **连接串来自哪里**：优先用环境变量 `DATABASE_URL`，其次读项目根目录的 `.env`；两者都没有时回落到代码默认值 `root@localhost:3306/greedy_snake`。把 `.env` 里的连接串换成与 Render 部署相同的那一条，本地就会直接读写云端库，和线上玩家共享同一份全球榜单。
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
- **MySQL** — 账号、登录会话与全球排行榜的存储

## 🧩 后端：账号与全球排行榜

排行榜面板可切换"本机 / 全球"：成绩提交到数据库，所有玩家共享一个榜单。本机榜存在浏览器 localStorage 里，与后端无关。

### 1. 准备数据库

需要 MySQL 服务运行中。库不存在时可以用附带的脚本一键创建：

```sql
-- 手动建库的话（脚本会自动做这一步）
CREATE DATABASE greedy_snake CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```bash
# 在项目根目录的 .env 里写入连接串（密码含特殊字符需 URL 编码）
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
| `DELETE /api/auth/account` | 注销账号（进入 15 天冷静期） |
| `POST /api/auth/password-reset/request` | 申请找回密码，取验证码 |
| `POST /api/auth/password-reset/confirm` | 用验证码设置新密码 |
| `GET /api/leaderboard/{difficulty}` | 全球 Top 10 |
| `POST /api/scores` | 提交成绩（需登录） |
| `GET /api/health` | 健康检查 |

## 🧪 测试

后端接口测试基于 pytest，覆盖认证、成绩校验、榜单、限流与静态资源托管：

```bash
pip install -r backend/requirements-dev.txt
pytest                          # 全部用例
pytest -v                       # 显示每个用例的名字
pytest -k TestScoreAntiCheat    # 只跑防作弊相关
```

测试跑在**独立的 MySQL 测试库 `greedy_snake_test`** 上，不会碰开发库 `greedy_snake`：

- 库不存在时会自动创建（只创建这个 `_test` 库）
- 连接串默认把 `DATABASE_URL` 的库名换成 `greedy_snake_test`，账号密码沿用 `.env` 里的那份
- 每个用例开始前清空所有表，跑完整个会话再把数据清干净
- **安全阀**：库名不以 `_test` 结尾时直接拒绝运行——防止 `DATABASE_URL` 被误配成开发库或线上库后，测试把数据清空
- 需要指向别的测试库时，用 `TEST_DATABASE_URL` 环境变量覆盖

跑测试需要 MySQL 服务运行中，连不上会给出明确提示而不是一堆堆栈。

> **成绩防作弊**：`POST /api/scores` 会做服务端一致性校验——得分必须等于「食物数 × 10」，食物数不能超过移动步数，移动步数与存活时间要对得上。纯前端游戏没法彻底防作弊（改 JS 就能伪造数据），这一层的作用是让"随手改个数字就霸榜"不再成立。
>
> **限流**：登录每 IP 每分钟 10 次、注册每 IP 5 分钟 5 次，超限返回 429。限流计数存在进程内存里，因此只对单实例部署有效；多实例需要换成 Redis 之类的共享存储。

## 🔐 账号安全

**找回密码**：登录弹窗里的「忘记密码？」入口，两步完成——先填注册邮箱取验证码，再用验证码设置新密码。

- 验证码 6 位数字、15 分钟有效、一条只能用一次、最多试 5 次；重新申请会把上一条作废
- 重置成功后该账号的**所有登录会话立即失效**（旧密码可能已泄露，不能让它换来的令牌继续可用）
- 申请接口**无论邮箱是否注册都返回完全相同的响应**，避免被用来枚举账号

> **验证码怎么送到用户手上**：默认打印到服务端日志（本地开发够用，无需任何邮箱配置）。在 `.env` 里配好 `SMTP_*` 之后会自动改为真发邮件，配置项见 `.env.example`。
>
> ⚠️ **控制台投递意味着任何能看到服务端日志的人都能重置任意账号的密码**，只适合本地开发；公网部署务必配置 SMTP。

**注销账号**：游戏内用户卡片下的「注销账号」→ 确认后进入 **15 天冷静期**。冷静期内重新登录即自动撤销；期满仍未登录才清除账号、登录会话与历史成绩。

## ☁️ 云部署（Render）

仓库根目录的 `render.yaml` 是 Render Blueprint 部署配置：单个 Python Web 服务同时运行后端 API 并托管前端页面，数据库连接串通过环境变量 `DATABASE_URL` 注入（当前使用阿里云 RDS MySQL，任何 MySQL 兼容的云数据库均可）。

在 Render 控制台选择 "New → Blueprint" 并导入本仓库即可一键部署；部署时在控制台填入你的 `DATABASE_URL`。三点注意：

- **线上务必配置 `DATABASE_URL`**：不配置时会回落到代码默认值 `root@localhost:3306`，而 Render 容器里没有 MySQL 服务，账号与排行榜接口会一律返回 503（服务本身能启动，静态页面照常访问）。
- **密码中的特殊字符必须 URL 编码**：例如密码以 `@` 结尾时写成 `%40`，否则 `@` 会被当作连接串的分隔符导致域名解析失败。
- **阿里云 RDS 需要配置白名单**：Render 的出口 IP 是动态的，无法逐个放通，只能在 RDS 白名单中添加 `0.0.0.0/0`。请务必使用高强度密码，并确保 `.env`、连接串不会进入版本库。

## 📄 License

本项目仅供学习和个人使用。
