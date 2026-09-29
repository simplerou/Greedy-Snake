const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");

const scoreElement = document.querySelector("#score strong");
const bestElement = document.querySelector("#best strong");
const speedElement = document.querySelector("#speed strong");
const timerElement = document.querySelector("#timer strong");
const mainMenuElement = document.getElementById("mainMenu");
const gameScreenElement = document.getElementById("gameScreen");
const currentDifficultyElement = document.getElementById("currentDifficulty");
const backToMenuElement = document.getElementById("backToMenu");
const currentUserNameElement = document.getElementById("currentUserName");
const userAvatarElement = document.getElementById("userAvatar");
const userAvatarImageElement = document.getElementById("userAvatarImage");
const userAvatarLetterElement = document.getElementById("userAvatarLetter");
const leaderboardListElement = document.getElementById("leaderboardList");
const resultOverlayElement = document.getElementById("resultOverlay");
const resultScoreElement = document.getElementById("resultScore");
const resultRecordElement = document.getElementById("resultRecord");
const resultRankElement = document.getElementById("resultRank");
const resultSyncElement = document.getElementById("resultSync");
const resultSyncTextElement = document.getElementById("resultSyncText");
const retrySubmitButton = document.getElementById("retrySubmit");
const playAgainElement = document.getElementById("playAgain");
const viewLeaderboardElement = document.getElementById("viewLeaderboard");
const resultToMenuElement = document.getElementById("resultToMenu");
const touchPauseElement = document.getElementById("touchPause");
const touchRestartElement = document.getElementById("touchRestart");

// 统计面板元素
const statTimeElement = document.getElementById("statTime");
const statFoodElement = document.getElementById("statFood");
const statMovesElement = document.getElementById("statMoves");
const statSpeedElement = document.getElementById("statSpeed");
const statMaxSpeedElement = document.getElementById("statMaxSpeed");

const difficultyButtons = document.querySelectorAll("[data-difficulty]");
const directionButtons = document.querySelectorAll("[data-direction]");
const leaderboardTabs = document.querySelectorAll("[data-leaderboard-difficulty]");
const scopeButtons = document.querySelectorAll("[data-scope]");

const WIDTH = 1000;
const HEIGHT = 800;
const BLOCK = 20;
const START_SAFE_RADIUS = 5;
const COUNTDOWN_DURATION = 4000;
const LEADERBOARD_KEY = "greedySnakeLeaderboardV1";
const MAX_LEADERBOARD_SIZE = 10;
const API_BASE = ""; // FastAPI 同源托管时留空；前后端分离部署时改为后端地址，如 "http://127.0.0.1:8000"
const AUTH_TOKEN_KEY = "greedySnakeAuthToken";

function getAuthToken() {
    try {
        return localStorage.getItem(AUTH_TOKEN_KEY) || "";
    } catch (error) {
        return "";
    }
}

async function requireAuthentication() {
    const token = getAuthToken();
    if (!token) {
        window.location.replace("../../?login=required");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/auth/me`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!response.ok) throw new Error("unauthorized");

        const user = await response.json();
        currentPlayerName = normalizePlayerName(user.nickname);
        currentUserNameElement.textContent = currentPlayerName;
        // 整张卡片是指向用户中心的链接，头像也在那里上传
        applyUserAvatar(user.avatar_url, currentPlayerName);
        document.body.classList.remove("authPending");
    } catch (error) {
        try {
            localStorage.removeItem(AUTH_TOKEN_KEY);
        } catch (storageError) {
            // 即使浏览器拒绝存储操作，也返回登录页面。
        }
        window.location.replace("../../?login=required");
    }
}

/* 用户卡片上的头像徽章：取昵称的首个字符。
 * 用 Array.from 而不是 [0]，这样 emoji 之类的代理对不会被截成半个字符。
 *
 * 注销账号、改昵称、改密码这些账号操作都收在用户中心（profile.html）里，
 * 游戏页只保留一个入口，不再自己处理。 */
function avatarLetter(nickname) {
    const text = (nickname || "").trim();
    if (!text) return "·";
    return Array.from(text)[0].toUpperCase();
}

/* 有头像就显示图片，没有就回到首字。
 * 图片取不到（被移除、网络问题）也要退回首字，不能在卡片上留个破图图标。 */
function applyUserAvatar(avatarUrl, nickname) {
    userAvatarLetterElement.textContent = avatarLetter(nickname);
    userAvatarImageElement.hidden = !avatarUrl;
    userAvatarElement.dataset.hasImage = avatarUrl ? "true" : "false";

    if (avatarUrl) {
        userAvatarImageElement.src = avatarUrl;
    } else {
        userAvatarImageElement.removeAttribute("src");
    }
}

userAvatarImageElement.addEventListener("error", () => {
    userAvatarImageElement.hidden = true;
    userAvatarElement.dataset.hasImage = "false";
});


const DIFFICULTIES = {
    easy: {
        name: "低等难度",
        englishName: "EASY",
        color: "#69f49a",
        startSpeed: 220,
        speedUpEvery: 100,
        speedStep: 10,
        minSpeed: 120,
        // 固定配方：16 段长度 1 的障碍物（数字为格数）
        obstacleLengths: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        obstacleMoveEvery: 0
    },
    medium: {
        name: "中等难度",
        englishName: "MEDIUM",
        color: "#f2c94c",
        startSpeed: 150,
        speedUpEvery: 50,
        speedStep: 15,
        minSpeed: 50,
        // 固定配方：单格与长条并存，16 段合计 30 格（数字为格数）
        obstacleLengths: [1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3],
        obstacleMoveEvery: 0
    },
    hard: {
        name: "高等难度",
        englishName: "HARD",
        color: "#ff6969",
        startSpeed: 125,
        speedUpEvery: 40,
        speedStep: 10,
        minSpeed: 45,
        // 长度随机（1 ~ obstacleMaxLength），总格数由 obstacleTotal 控制
        obstacleTotal: 45,
        obstacleMaxLength: 3,
        obstacleMoveEvery: 25
    }
};

let difficulty = "easy";
let leaderboardDifficulty = "easy";
let state = "MENU";
let countdownStartTime = 0;
let gameStartTime = 0;
let snake = [];
let food = {};
let obstacles = [];
let direction = "RIGHT";
let nextDirection = "RIGHT";
let score = 0;
let moveCount = 0;
let foodEaten = 0;
let maxSpeedLevel = 1;
let obstacleMoveNotice = 0;
let speed = DIFFICULTIES[difficulty].startSpeed;
let bestScore = 0;
/* 本局开始前的历史最佳。bestScore 会随着进食实时更新，到结算时它已经等于
 * 本局得分了，光看它判断不出有没有破纪录，所以另存一份开局时的值。 */
let bestScoreAtStart = 0;
let currentPlayerName = "匿名玩家";
let leaderboards = loadLeaderboards();
let timerInterval = null;
let pausedAt = 0;                 // 进入暂停的时刻；恢复时把这段时长从计时起点里扣掉
let leaderboardScope = "local";   // "local" = 本机榜单，"global" = 全球榜单
let globalCache = {};             // 按难度缓存全球榜单数据

function createEmptyLeaderboards() {
    return { easy: [], medium: [], hard: [] };
}

function loadLeaderboards() {
    try {
        const saved = JSON.parse(localStorage.getItem(LEADERBOARD_KEY));
        const result = createEmptyLeaderboards();

        Object.keys(result).forEach(level => {
            if (!Array.isArray(saved?.[level])) return;

            result[level] = saved[level]
                .filter(item => item && Number.isFinite(Number(item.score)))
                .map(item => ({
                    id: String(item.id || ""),
                    name: normalizePlayerName(item.name),
                    score: Math.max(0, Number(item.score)),
                    timestamp: Number(item.timestamp) || Date.now()
                }))
                .sort(compareScores)
                .slice(0, MAX_LEADERBOARD_SIZE);
        });

        return result;
    } catch (error) {
        return createEmptyLeaderboards();
    }
}

function compareScores(a, b) {
    return b.score - a.score || a.timestamp - b.timestamp;
}

function normalizePlayerName(value) {
    const cleaned = String(value || "")
        .replace(/<[^>]*>/g, "")
        .replace(/[<>]/g, "")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 12);

    return cleaned || "匿名玩家";
}

function persistLeaderboards() {
    try {
        localStorage.setItem(LEADERBOARD_KEY, JSON.stringify(leaderboards));
    } catch (error) {
        // 隐私浏览模式或存储空间不足时，榜单仍会在当前页面会话中工作。
    }
}

function getLegacyBestScore(level) {
    const storageKey = level === "medium" ? "bestScore" : `bestScore_${level}`;
    return Number(localStorage.getItem(storageKey)) || 0;
}

function saveLegacyBestScore() {
    const storageKey = difficulty === "medium" ? "bestScore" : `bestScore_${difficulty}`;

    try {
        localStorage.setItem(storageKey, String(bestScore));
    } catch (error) {
        // 游戏本身不应因浏览器拒绝存储而中断。
    }
}

function getBestScore(level) {
    const rankingBest = leaderboards[level][0]?.score || 0;
    return Math.max(rankingBest, getLegacyBestScore(level));
}

function migrateLegacyBestScores() {
    let changed = false;

    Object.keys(DIFFICULTIES).forEach(level => {
        const legacyScore = getLegacyBestScore(level);
        const legacyId = `legacy-${level}`;

        if (legacyScore <= 0 || leaderboards[level].some(item => item.id === legacyId)) return;

        leaderboards[level].push({
            id: legacyId,
            name: "历史最佳",
            score: legacyScore,
            timestamp: 1
        });
        leaderboards[level].sort(compareScores);
        leaderboards[level] = leaderboards[level].slice(0, MAX_LEADERBOARD_SIZE);
        changed = true;
    });

    if (changed) persistLeaderboards();
}

function recordScore() {
    if (score <= 0) return null;

    const entry = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: currentPlayerName,
        score,
        timestamp: Date.now()
    };

    const allEntries = [...leaderboards[difficulty], entry].sort(compareScores);
    const rank = allEntries.findIndex(item => item.id === entry.id) + 1;
    const placed = rank > 0 && rank <= MAX_LEADERBOARD_SIZE;

    leaderboards[difficulty] = allEntries.slice(0, MAX_LEADERBOARD_SIZE);
    persistLeaderboards();
    renderLeaderboard();

    // 传的是一份快照：上传是异步的，而且失败后还能在结算面板上重试，
    // 那时这局早已结束、现场变量已经变了
    submitScoreToCloud({
        name: entry.name,
        difficulty,
        score: entry.score,
        duration_seconds: Math.round(getGameDuration() / 1000),
        food_eaten: foodEaten,
        moves: moveCount
    });

    return { rank, placed };
}

function formatScore(value) {
    return String(value).padStart(4, "0");
}

/* ── 全球排行榜 API ─────────────────────────────── */

/* 返回 { ok, status }；status 为 0 表示请求压根没发出去（断网、后端没起）。
 *
 * 特意保留状态码而不是一律 null：401 要重新登录、422 是服务端校验拒绝、
 * 5xx 是后端故障——这几种情况该对用户说的话不一样，混在一起就只能说"失败了"。
 */
async function apiSubmitScore(payload) {
    try {
        const res = await fetch(`${API_BASE}/api/scores`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${getAuthToken()}`
            },
            body: JSON.stringify(payload)
        });
        return { ok: res.ok, status: res.status };
    } catch (error) {
        return { ok: false, status: 0 };
    }
}

async function apiFetchLeaderboard(level) {
    try {
        const res = await fetch(`${API_BASE}/api/leaderboard/${level}?limit=10`);
        return res.ok ? await res.json() : null;
    } catch (error) {
        return null;
    }
}

/* 上传失败时把这份成绩原样留着，供结算面板上的「重试上传」用。
 * 留的是快照而不是引用现场变量：重试可能发生在下一局已经开始之后，
 * 那时的 difficulty / foodEaten / moves 早就不是这一局的了。 */
let pendingScore = null;

function setSyncStatus(text, tone) {
    resultSyncTextElement.textContent = text;
    resultSyncElement.hidden = !text;

    if (tone) resultSyncElement.dataset.tone = tone;
    else delete resultSyncElement.dataset.tone;

    retrySubmitButton.hidden = !pendingScore;
}

function describeSyncFailure(status) {
    if (status === 0) return "没能连上服务器，这局只记在了本机榜上。";
    if (status === 401) return "登录状态已失效，这局只记在了本机榜上。";
    if (status === 422) return "这局成绩未通过服务端校验，没有计入全球榜。";
    if (status === 429) return "提交太频繁，稍等一会儿重试就能上榜。";
    if (status >= 500) return "服务器暂时不可用，这局只记在了本机榜上。";
    return "成绩上传失败，这局只记在了本机榜上。";
}

async function submitScoreToCloud(payload) {
    pendingScore = payload;
    setSyncStatus("正在同步到全球榜…");

    const result = await apiSubmitScore(payload);

    if (result.ok) {
        pendingScore = null;
        globalCache = {};   // 有新成绩入库，下次查看全球榜单时重新拉取
        setSyncStatus("已同步到全球榜。", "ok");
        if (leaderboardScope === "global") renderLeaderboard();
        return;
    }

    setSyncStatus(describeSyncFailure(result.status), "warn");
}

function renderLeaderboardRows(items, emptyTitle, emptyHint) {
    leaderboardListElement.replaceChildren();

    if (!items || items.length === 0) {
        const empty = document.createElement("li");
        empty.className = "emptyLeaderboard";

        const title = document.createElement("strong");
        title.textContent = emptyTitle;

        const hint = document.createElement("span");
        hint.textContent = emptyHint;

        empty.append(title, hint);
        leaderboardListElement.append(empty);
        return;
    }

    items.forEach((entry, index) => {
        const row = document.createElement("li");
        row.className = "leaderboardRow";

        const rank = document.createElement("span");
        rank.className = "rankNumber";
        rank.textContent = `#${String(index + 1).padStart(2, "0")}`;

        const name = document.createElement("span");
        name.className = "rankName";
        name.textContent = entry.name;
        name.title = entry.name;

        const points = document.createElement("span");
        points.className = "rankScore";
        points.textContent = formatScore(entry.score);

        row.append(rank, name, points);
        leaderboardListElement.append(row);
    });
}

async function renderLeaderboard() {
    leaderboardTabs.forEach(tab => {
        const selected = tab.dataset.leaderboardDifficulty === leaderboardDifficulty;
        tab.classList.toggle("active", selected);
        tab.setAttribute("aria-selected", String(selected));
    });

    scopeButtons.forEach(button => {
        button.classList.toggle("active", button.dataset.scope === leaderboardScope);
    });

    if (leaderboardScope === "local") {
        renderLeaderboardRows(
            leaderboards[leaderboardDifficulty],
            "等待首位挑战者",
            "完成一局游戏即可留下成绩"
        );
        return;
    }

    const level = leaderboardDifficulty;
    renderLeaderboardRows(null, "全球榜单加载中…", "正在连接服务器");

    if (!(level in globalCache)) {
        globalCache[level] = await apiFetchLeaderboard(level);
    }

    const rows = globalCache[level];

    if (rows === null) {
        delete globalCache[level];
        renderLeaderboardRows([], "无法连接榜单服务器", "请确认后端已启动，切换标签后重试");
        return;
    }

    renderLeaderboardRows(rows, "云端还没有成绩", "完成一局游戏，抢占全球第一！");
}

function selectLeaderboard(level) {
    leaderboardDifficulty = level;
    renderLeaderboard();
}

function resetGame() {
    const settings = DIFFICULTIES[difficulty];

    snake = [
        { x: 400, y: 400 },
        { x: 380, y: 400 },
        { x: 360, y: 400 }
    ];

    direction = "RIGHT";
    nextDirection = "RIGHT";
    score = 0;
    moveCount = 0;
    foodEaten = 0;
    maxSpeedLevel = 1;
    obstacleMoveNotice = 0;
    speed = settings.startSpeed;
    bestScore = getBestScore(difficulty);
    bestScoreAtStart = bestScore;

    scoreElement.textContent = "0";
    bestElement.textContent = String(bestScore);
    speedElement.textContent = "1";
    timerElement.textContent = "00:00";
    touchPauseElement.textContent = "暂停";
    resultOverlayElement.hidden = true;
    pausedAt = 0;

    // 上一局的上传结果与待重试成绩都不再适用
    pendingScore = null;
    setSyncStatus("");

    // 清除之前的计时器
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }

    food = {};
    obstacles = createObstacles();
    food = createFood();
    countdownStartTime = Date.now();
    state = "COUNTDOWN";
}

function updateSpeed() {
    const settings = DIFFICULTIES[difficulty];

    speed = settings.startSpeed
        - Math.floor(score / settings.speedUpEvery) * settings.speedStep;
    speed = Math.max(speed, settings.minSpeed);

    const level = Math.floor((settings.startSpeed - speed) / settings.speedStep) + 1;
    speedElement.textContent = String(level);
    maxSpeedLevel = Math.max(maxSpeedLevel, level);
}

function createFood() {
    while (true) {
        const candidate = {
            x: Math.floor(Math.random() * (WIDTH / BLOCK)) * BLOCK,
            y: Math.floor(Math.random() * (HEIGHT / BLOCK)) * BLOCK
        };

        const overlapsSnake = snake.some(part => part.x === candidate.x && part.y === candidate.y);

        if (!overlapsSnake && !isObstacleCell(candidate.x, candidate.y)) return candidate;
    }
}

/* ── 障碍物：以线段为单位（长度 + 方向），长度 1 即单格障碍 ── */

// 本局要生成的各段长度：低等/中等用固定配方，高等每次随机
function buildObstacleLengths() {
    const settings = DIFFICULTIES[difficulty];
    if (settings.obstacleLengths) return settings.obstacleLengths.slice();

    const lengths = [];
    let remaining = settings.obstacleTotal;

    while (remaining > 0) {
        const length = Math.min(remaining, 1 + Math.floor(Math.random() * settings.obstacleMaxLength));
        lengths.push(length);
        remaining -= length;
    }

    return lengths;
}

// 展开成占据的所有格子，供碰撞、食物避让与占位判断复用
function segmentCells(segment) {
    const cells = [];
    for (let index = 0; index < segment.length; index += 1) {
        cells.push({
            x: segment.x + (segment.direction === "H" ? index * BLOCK : 0),
            y: segment.y + (segment.direction === "H" ? 0 : index * BLOCK)
        });
    }
    return cells;
}

function isObstacleCell(x, y) {
    return obstacles.some(segment => (
        segment.direction === "H"
            ? y === segment.y && x >= segment.x && x < segment.x + segment.length * BLOCK
            : x === segment.x && y >= segment.y && y < segment.y + segment.length * BLOCK
    ));
}

function createObstacles() {
    const placed = [];
    const occupied = [];   // 已占用格子；线段必须按格子比对，否则长条之间会重叠

    buildObstacleLengths().forEach(length => {
        // 随机落点，最多尝试 200 次；极端拥挤时放弃该段，避免死循环
        for (let attempt = 0; attempt < 200; attempt += 1) {
            const direction = length === 1 || Math.random() < 0.5 ? "H" : "V";
            const horizontal = direction === "H";
            // 起点取值上限要减去自身长度，保证整段落在画布内
            const maxColumn = WIDTH / BLOCK - (horizontal ? length : 1);
            const maxRow = HEIGHT / BLOCK - (horizontal ? 1 : length);

            const segment = {
                x: Math.floor(Math.random() * (maxColumn + 1)) * BLOCK,
                y: Math.floor(Math.random() * (maxRow + 1)) * BLOCK,
                length,
                direction
            };

            const cells = segmentCells(segment);
            const inStartSafeArea = cells.some(cell =>
                Math.abs(cell.x - snake[0].x) <= START_SAFE_RADIUS * BLOCK
                && Math.abs(cell.y - snake[0].y) <= START_SAFE_RADIUS * BLOCK);
            const overlapsSnake = cells.some(cell =>
                snake.some(part => part.x === cell.x && part.y === cell.y));
            const overlapsFood = cells.some(cell => cell.x === food.x && cell.y === food.y);
            const overlapsPlaced = cells.some(cell =>
                occupied.some(item => item.x === cell.x && item.y === cell.y));

            if (!inStartSafeArea && !overlapsSnake && !overlapsFood && !overlapsPlaced) {
                placed.push(segment);
                occupied.push(...cells);
                break;
            }
        }
    });

    return placed;
}

function startGame(selectedDifficulty) {
    difficulty = selectedDifficulty;

    const settings = DIFFICULTIES[difficulty];
    currentDifficultyElement.textContent = `${settings.name} · ${settings.englishName}`;
    currentDifficultyElement.style.color = settings.color;
    mainMenuElement.hidden = true;
    gameScreenElement.hidden = false;
    // 得等页面真正显示出来才量得到尺寸，所以必须在取消 hidden 之后
    fitCanvasToDisplay();
    resetGame();
    canvas.focus();
}

function showMainMenu() {
    state = "MENU";
    resultOverlayElement.hidden = true;
    gameScreenElement.hidden = true;
    mainMenuElement.hidden = false;
    renderLeaderboard();
}

function finishGame() {
    if (state === "GAMEOVER") return;

    state = "GAMEOVER";
    stopTimer();

    // 更新最终计时
    const duration = getGameDuration();
    timerElement.textContent = formatTime(duration);

    // 更新统计面板
    updateStatsPanel();

    const result = recordScore();
    resultScoreElement.textContent = String(score);
    showRecordBadge();

    if (!result) {
        resultRankElement.textContent = "再吃到一颗食物，就能留下榜单成绩。";
    } else if (result.placed) {
        resultRankElement.innerHTML = `恭喜进入 ${DIFFICULTIES[difficulty].name} <strong>第 ${result.rank} 名</strong>`;
    } else {
        const cutoff = leaderboards[difficulty][MAX_LEADERBOARD_SIZE - 1]?.score || 0;
        resultRankElement.textContent = `本局排名第 ${result.rank}，Top 10 当前门槛为 ${cutoff} 分。`;
    }

    resultOverlayElement.hidden = false;
    playAgainElement.focus();
}

/* 破个人纪录时在结算面板上给一句提示。
 *
 * 比的基准是"本局开始前"的最佳分（bestScoreAtStart），不是当前的 bestScore——
 * 后者在吃下食物的那一刻就被顶上去了（见 update 里那段），到结算时它已经等于
 * 本局得分，拿它来比永远不成立。 */
function showRecordBadge() {
    if (score <= bestScoreAtStart) {
        resultRecordElement.hidden = true;
        return;
    }

    resultRecordElement.textContent = bestScoreAtStart > 0
        ? `新纪录！比之前的 ${bestScoreAtStart} 分高出 ${score - bestScoreAtStart} 分`
        : "新纪录！这是你在本难度的第一份成绩";
    resultRecordElement.hidden = false;
}

function changeDirection(newDirection) {
    if (gameScreenElement.hidden) return;

    const oppositeDirections = {
        UP: "DOWN",
        DOWN: "UP",
        LEFT: "RIGHT",
        RIGHT: "LEFT"
    };

    if (newDirection !== oppositeDirections[direction]) {
        nextDirection = newDirection;
    }
}

function togglePause() {
    if (state === "PLAYING") {
        pauseGame();
    } else if (state === "PAUSE") {
        resumeGame();
    }
}

function pauseGame() {
    state = "PAUSE";
    pausedAt = Date.now();
    stopTimer();
    touchPauseElement.textContent = "继续";
}

function resumeGame() {
    // 把暂停的这段时长从计时起点里减掉，让 TIME 只统计真正在玩的时间。
    // 不补偿的话，暂停十分钟再回来会凭空多出十分钟——显示的计时是错的，
    // 提交给服务端的用时也是错的。
    if (pausedAt) {
        gameStartTime += Date.now() - pausedAt;
        pausedAt = 0;
    }
    state = "PLAYING";
    startTimer();
    touchPauseElement.textContent = "暂停";
}

/* ── 计时器 & 统计 ─────────────────────────────── */

function formatTime(ms) {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function startTimer() {
    stopTimer(); // 先清除旧的，防止重复
    timerInterval = setInterval(() => {
        if (state !== "PLAYING") return;
        const elapsed = Date.now() - gameStartTime;
        timerElement.textContent = formatTime(elapsed);
    }, 200);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

function getGameDuration() {
    return Date.now() - gameStartTime;
}

function updateStatsPanel() {
    const duration = getGameDuration();
    statTimeElement.textContent = formatTime(duration);
    statFoodElement.textContent = String(foodEaten);
    statMovesElement.textContent = String(moveCount);
    statSpeedElement.textContent = String(maxSpeedLevel);

    const avgSpeed = moveCount > 0
        ? (duration / 1000 / moveCount).toFixed(2)
        : "0.00";
    statMaxSpeedElement.textContent = `${avgSpeed}s`;
}

difficultyButtons.forEach(button => {
    button.addEventListener("click", () => startGame(button.dataset.difficulty));
});

leaderboardTabs.forEach(tab => {
    tab.addEventListener("click", () => selectLeaderboard(tab.dataset.leaderboardDifficulty));
});

scopeButtons.forEach(button => {
    button.addEventListener("click", () => {
        if (leaderboardScope === button.dataset.scope) return;
        leaderboardScope = button.dataset.scope;
        renderLeaderboard();
    });
});

directionButtons.forEach(button => {
    button.addEventListener("pointerdown", event => {
        event.preventDefault();
        changeDirection(button.dataset.direction);
    });
});

backToMenuElement.addEventListener("click", showMainMenu);
resultToMenuElement.addEventListener("click", showMainMenu);

viewLeaderboardElement.addEventListener("click", () => {
    selectLeaderboard(difficulty);
    showMainMenu();
    document.querySelector(".leaderboardPanel").scrollIntoView({ behavior: "smooth", block: "start" });
});

playAgainElement.addEventListener("click", () => {
    resetGame();
    canvas.focus();
});

// 重试上传：把留着的那份成绩重新提交一次，成功与否都会刷新状态文案
retrySubmitButton.addEventListener("click", async () => {
    if (!pendingScore) return;
    retrySubmitButton.disabled = true;
    try {
        await submitScoreToCloud(pendingScore);
    } finally {
        retrySubmitButton.disabled = false;
    }
});

touchPauseElement.addEventListener("click", togglePause);
touchRestartElement.addEventListener("click", resetGame);

canvas.addEventListener("click", () => canvas.focus());

// 窗口尺寸变了（转屏、拉窗口、挪到另一块显示器）就按新尺寸重算像素，
// 否则画面会被拉伸或发虚。下一帧 draw() 会重绘，不用额外处理。
window.addEventListener("resize", fitCanvasToDisplay);

let touchStartX = 0;
let touchStartY = 0;

canvas.addEventListener("touchstart", event => {
    touchStartX = event.touches[0].clientX;
    touchStartY = event.touches[0].clientY;
}, { passive: true });

canvas.addEventListener("touchend", event => {
    const deltaX = event.changedTouches[0].clientX - touchStartX;
    const deltaY = event.changedTouches[0].clientY - touchStartY;

    if (Math.max(Math.abs(deltaX), Math.abs(deltaY)) < 20) return;

    if (Math.abs(deltaX) > Math.abs(deltaY)) {
        changeDirection(deltaX > 0 ? "RIGHT" : "LEFT");
    } else {
        changeDirection(deltaY > 0 ? "DOWN" : "UP");
    }
}, { passive: true });

/* 页面被切到后台时自动暂停。
 *
 * 不处理会有两个后果：浏览器把后台页面的定时器节流到约一秒一次，蛇于是在同一个
 * 方向上一格一格地挪、计时器却照涨；而且方向不会自己变，待久了一定撞墙。切回来
 * 看到的是"莫名其妙就死了"，用户完全不知道中间发生了什么。
 *
 * 倒计时那次也要管：它按墙上时钟算，切走几秒再回来会直接跳到 GO!，玩家连开局
 * 方向都没来得及选，所以重新计一次。 */
document.addEventListener("visibilitychange", () => {
    if (!document.hidden) return;
    if (state === "PLAYING") pauseGame();
    else if (state === "COUNTDOWN") countdownStartTime = Date.now();
});

document.addEventListener("keydown", event => {
    if (gameScreenElement.hidden) return;

    if (event.key === "Escape") {
        showMainMenu();
        return;
    }

    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", " "].includes(event.key)) {
        event.preventDefault();
    }

    if (event.code === "Space") {
        togglePause();
        return;
    }

    if (event.key.toLowerCase() === "r") {
        resetGame();
        canvas.focus();
        return;
    }

    if (state === "GAMEOVER") {
        return;
    }

    if (event.key === "ArrowUp") changeDirection("UP");
    else if (event.key === "ArrowDown") changeDirection("DOWN");
    else if (event.key === "ArrowLeft") changeDirection("LEFT");
    else if (event.key === "ArrowRight") changeDirection("RIGHT");
});

function update() {
    if (state === "COUNTDOWN") {
        if (Date.now() - countdownStartTime >= COUNTDOWN_DURATION) {
            state = "PLAYING";
            gameStartTime = Date.now();
            startTimer();
        } else {
            return;
        }
    }

    if (state !== "PLAYING") return;

    direction = nextDirection;
    if (obstacleMoveNotice > 0) obstacleMoveNotice -= 1;

    const head = { ...snake[0] };
    if (direction === "UP") head.y -= BLOCK;
    if (direction === "DOWN") head.y += BLOCK;
    if (direction === "LEFT") head.x -= BLOCK;
    if (direction === "RIGHT") head.x += BLOCK;
    snake.unshift(head);

    if (head.x === food.x && head.y === food.y) {
        score += 10;
        foodEaten += 1;
        scoreElement.textContent = String(score);
        updateSpeed();

        if (score > bestScore) {
            bestScore = score;
            bestElement.textContent = String(bestScore);
            saveLegacyBestScore();
        }

        food = createFood();
    } else {
        snake.pop();
    }

    const hitWall = head.x < 0 || head.x >= WIDTH || head.y < 0 || head.y >= HEIGHT;
    const hitSelf = snake.slice(1).some(part => part.x === head.x && part.y === head.y);
    const hitObstacle = isObstacleCell(head.x, head.y);

    if (hitWall || hitSelf || hitObstacle) {
        finishGame();
        return;
    }

    moveCount += 1;
    const moveEvery = DIFFICULTIES[difficulty].obstacleMoveEvery;

    if (moveEvery > 0 && moveCount % moveEvery === 0) {
        obstacles = createObstacles();
        obstacleMoveNotice = 6;
    }
}

function drawGrid() {
    ctx.strokeStyle = "rgba(255,255,255,.035)";
    ctx.lineWidth = 1;
    ctx.beginPath();

    for (let x = BLOCK; x < WIDTH; x += BLOCK) {
        ctx.moveTo(x + .5, 0);
        ctx.lineTo(x + .5, HEIGHT);
    }

    for (let y = BLOCK; y < HEIGHT; y += BLOCK) {
        ctx.moveTo(0, y + .5);
        ctx.lineTo(WIDTH, y + .5);
    }

    ctx.stroke();
}

function drawCenteredOverlay(title, subtitle, color = "#ffffff") {
    ctx.fillStyle = "rgba(2,5,3,.72)";
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
    ctx.fillStyle = color;
    ctx.font = "bold 72px Arial";
    ctx.textAlign = "center";
    ctx.fillText(title, WIDTH / 2, HEIGHT / 2 - 10);
    ctx.fillStyle = "#9ba79f";
    ctx.font = "22px Arial";
    ctx.fillText(subtitle, WIDTH / 2, HEIGHT / 2 + 50);
}

/* 按「实际显示尺寸 × 设备像素比」重建画布像素，再用 setTransform 一次性缩放，
 * 绘制代码里的坐标仍按 1000×800 这套逻辑坐标写，一行都不用改。
 *
 * 不这么做的话：MacBook 这类 DPR=2 的屏幕上，canvas 只有 1000 个物理像素，却要铺满
 * 约 2000 个物理像素的位置，浏览器只能把画面硬拉两倍，糊得很明显。
 * 反过来在小屏手机上不浪费像素——算的是实际显示尺寸，不是无脑乘 dpr。 */
function fitCanvasToDisplay() {
    const rect = canvas.getBoundingClientRect();
    // 游戏页还没显示时量不到尺寸（rect 全为 0），直接跳过
    if (!rect.width || !rect.height) return;

    const dpr = window.devicePixelRatio || 1;
    const targetWidth = Math.round(rect.width * dpr);
    const targetHeight = Math.round(rect.height * dpr);

    // 尺寸没变就别动：给 canvas.width 赋值会清空画布并重置变换
    if (canvas.width === targetWidth && canvas.height === targetHeight) return;

    canvas.width = targetWidth;
    canvas.height = targetHeight;
}

function draw() {
    // 每帧重设一次变换：canvas 尺寸变化时浏览器会顺手把它重置掉
    ctx.setTransform(canvas.width / WIDTH, 0, 0, canvas.height / HEIGHT, 0, 0);

    ctx.fillStyle = "#020403";
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
    drawGrid();

    if (food.x !== undefined) {
        ctx.fillStyle = "#ff5f5f";
        ctx.shadowColor = "rgba(255,95,95,.75)";
        ctx.shadowBlur = 12;
        ctx.fillRect(food.x + 3, food.y + 3, BLOCK - 6, BLOCK - 6);
        ctx.shadowBlur = 0;
    }

    ctx.fillStyle = "#667169";
    obstacles.forEach(segment => {
        // 整段画成一个矩形，长条与单格在视觉上是连续的一条
        const width = segment.direction === "H" ? segment.length * BLOCK - 4 : BLOCK - 4;
        const height = segment.direction === "H" ? BLOCK - 4 : segment.length * BLOCK - 4;
        ctx.fillRect(segment.x + 2, segment.y + 2, width, height);
    });

    snake.forEach((part, index) => {
        ctx.fillStyle = index === 0 ? "#8affad" : "#2ca75a";
        ctx.fillRect(part.x + 1, part.y + 1, BLOCK - 2, BLOCK - 2);
    });

    if (obstacleMoveNotice > 0) {
        ctx.fillStyle = "#f2c94c";
        ctx.font = "bold 22px Arial";
        ctx.textAlign = "center";
        ctx.fillText("障碍物已换位", WIDTH / 2, 42);
    }

    if (state === "PAUSE") {
        drawCenteredOverlay("PAUSE", "按空格键或暂停键继续");
    }

    if (state === "COUNTDOWN") {
        const elapsed = Date.now() - countdownStartTime;
        let countdownText = "3";

        if (elapsed >= 3000) countdownText = "GO!";
        else if (elapsed >= 2000) countdownText = "1";
        else if (elapsed >= 1000) countdownText = "2";

        const hint = window.matchMedia("(max-width: 680px)").matches
            ? "滑动或点击方向键选择起步方向"
            : "按方向键选择起步方向";
        drawCenteredOverlay(countdownText, hint, DIFFICULTIES[difficulty].color);
    }
}

function gameLoop() {
    update();
    draw();
    setTimeout(gameLoop, speed);
}

migrateLegacyBestScores();
requireAuthentication();

renderLeaderboard();
gameLoop();
