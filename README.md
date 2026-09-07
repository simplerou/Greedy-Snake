# 🐍 Greedy Snake · 经典贪吃蛇

一个基于原生 HTML / CSS / JavaScript 的经典贪吃蛇网页游戏，无需任何框架依赖。

## ✨ 功能特性

- **三档难度**：低等（EASY）· 中等（MEDIUM）· 高等（HARD）
- **障碍物系统**：中等难度 10 个固定障碍物，高等难度 15 个障碍物且每 25 步自动换位
- **动态加速**：随分数提升，蛇的移动速度逐渐加快
- **计时器**：游戏内实时显示存活时间（MM:SS）
- **本局统计**：游戏结束后展示存活时间、食物数量、移动步数、最高速度、平均步速
- **本机排行榜**：每个难度独立 Top 10 排名，数据保存在浏览器 localStorage
- **玩家昵称**：支持输入自定义昵称，自动保存
- **开局倒计时**：3-2-1-GO! 倒计时，预留操作准备时间
- **移动端适配**：触摸滑动 + 虚拟方向键，完整支持手机游玩
- **暂停 / 重开**：Space 暂停，R 重新开始，Esc 返回菜单
- **GitHub Pages 部署**：通过 GitHub Actions 自动构建和部署

## 🎮 难度说明

| 参数 | 低等 EASY | 中等 MEDIUM | 高等 HARD |
|------|-----------|-------------|-----------|
| 初始速度 | 220ms | 150ms | 125ms |
| 加速间隔 | 每 100 分 | 每 50 分 | 每 40 分 |
| 最高速度 | 120ms | 50ms | 45ms |
| 障碍物数 | 0 | 10 | 15 |
| 障碍换位 | 无 | 无 | 每 25 步 |

## 📁 项目结构

```
Greedy-Snake/
├── web_game/                  # 游戏源码
│   ├── index.html             # 主页面
│   ├── snake.js               # 游戏逻辑
│   └── style.css              # 样式文件
├── .github/workflows/         # GitHub Pages 部署配置
│   └── deploy-pages.yml
├── .gitignore
└── README.md
```

## 🚀 本地运行

确保已安装 Python 3，然后执行：

```bash
cd web_game
python -m http.server 8080
```

浏览器打开 http://127.0.0.1:8080 即可开始游戏。

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
- **FastAPI + MySQL** — 全球排行榜后端（可选）

## 🧩 后端：全球排行榜（可选）

开启后端后，排行榜面板可切换"本机 / 全球"：成绩提交到 MySQL，所有玩家共享一个榜单。不启动后端时游戏自动降级为纯本机模式。

### 1. 准备数据库

```sql
CREATE DATABASE greedy_snake CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 安装依赖并启动

```bash
pip install -r backend/requirements.txt

# MySQL 有密码时先设置环境变量（PowerShell）
$env:DATABASE_URL = "mysql+pymysql://root:你的密码@localhost:3306/greedy_snake?charset=utf8mb4"

# 在项目根目录启动（同时托管前端页面）
uvicorn backend.main:app --reload
```

### 3. 访问

| 地址 | 说明 |
|------|------|
| http://127.0.0.1:8000/ | 游戏首页（FastAPI 托管） |
| http://127.0.0.1:8000/docs | API 交互式文档 |
| `GET /api/leaderboard/{difficulty}` | 全球 Top 10 |
| `POST /api/scores` | 提交成绩 |

## 📄 License

本项目仅供学习和个人使用。
