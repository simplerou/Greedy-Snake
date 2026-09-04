const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");

const scoreElement = document.querySelector("#score strong");
const bestElement = document.querySelector("#best strong");
const speedElement = document.querySelector("#speed strong");
const mainMenuElement = document.getElementById("mainMenu");
const gameScreenElement = document.getElementById("gameScreen");
const currentDifficultyElement = document.getElementById("currentDifficulty");
const backToMenuElement = document.getElementById("backToMenu");
const playerNameElement = document.getElementById("playerName");
const leaderboardListElement = document.getElementById("leaderboardList");
const resultOverlayElement = document.getElementById("resultOverlay");
const resultScoreElement = document.getElementById("resultScore");
const resultRankElement = document.getElementById("resultRank");
const playAgainElement = document.getElementById("playAgain");
const viewLeaderboardElement = document.getElementById("viewLeaderboard");
const resultToMenuElement = document.getElementById("resultToMenu");
const touchPauseElement = document.getElementById("touchPause");
const touchRestartElement = document.getElementById("touchRestart");

const difficultyButtons = document.querySelectorAll("[data-difficulty]");
const directionButtons = document.querySelectorAll("[data-direction]");
const leaderboardTabs = document.querySelectorAll("[data-leaderboard-difficulty]");

const WIDTH = 1000;
const HEIGHT = 800;
const BLOCK = 20;
const START_SAFE_RADIUS = 5;
const COUNTDOWN_DURATION = 4000;
const LEADERBOARD_KEY = "greedySnakeLeaderboardV1";
const PLAYER_NAME_KEY = "greedySnakePlayerName";
const MAX_LEADERBOARD_SIZE = 10;

const DIFFICULTIES = {
    easy: {
        name: "低等难度",
        englishName: "EASY",
        color: "#69f49a",
        startSpeed: 220,
        speedUpEvery: 100,
        speedStep: 10,
        minSpeed: 120,
        obstacleCount: 0,
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
        obstacleCount: 10,
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
        obstacleCount: 15,
        obstacleMoveEvery: 25
    }
};

let difficulty = "easy";
let leaderboardDifficulty = "easy";
let state = "MENU";
let countdownStartTime = 0;
let snake = [];
let food = {};
let obstacles = [];
let direction = "RIGHT";
let nextDirection = "RIGHT";
let score = 0;
let moveCount = 0;
let obstacleMoveNotice = 0;
let speed = DIFFICULTIES[difficulty].startSpeed;
let bestScore = 0;
let currentPlayerName = "匿名玩家";
let leaderboards = loadLeaderboards();

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

    return { rank, placed };
}

function formatScore(value) {
    return String(value).padStart(4, "0");
}

function renderLeaderboard() {
    const scores = leaderboards[leaderboardDifficulty];
    leaderboardListElement.replaceChildren();

    leaderboardTabs.forEach(tab => {
        const selected = tab.dataset.leaderboardDifficulty === leaderboardDifficulty;
        tab.classList.toggle("active", selected);
        tab.setAttribute("aria-selected", String(selected));
    });

    if (scores.length === 0) {
        const empty = document.createElement("li");
        empty.className = "emptyLeaderboard";

        const title = document.createElement("strong");
        title.textContent = "等待首位挑战者";

        const hint = document.createElement("span");
        hint.textContent = "完成一局游戏即可留下成绩";

        empty.append(title, hint);
        leaderboardListElement.append(empty);
        return;
    }

    scores.forEach((entry, index) => {
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
    obstacleMoveNotice = 0;
    speed = settings.startSpeed;
    bestScore = getBestScore(difficulty);

    scoreElement.textContent = "0";
    bestElement.textContent = String(bestScore);
    speedElement.textContent = "1";
    touchPauseElement.textContent = "暂停";
    resultOverlayElement.hidden = true;

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
}

function createFood() {
    while (true) {
        const candidate = {
            x: Math.floor(Math.random() * (WIDTH / BLOCK)) * BLOCK,
            y: Math.floor(Math.random() * (HEIGHT / BLOCK)) * BLOCK
        };

        const overlapsSnake = snake.some(part => part.x === candidate.x && part.y === candidate.y);
        const overlapsObstacle = obstacles.some(item => item.x === candidate.x && item.y === candidate.y);

        if (!overlapsSnake && !overlapsObstacle) return candidate;
    }
}

function createObstacles() {
    const list = [];
    const obstacleCount = DIFFICULTIES[difficulty].obstacleCount;

    while (list.length < obstacleCount) {
        const candidate = {
            x: Math.floor(Math.random() * (WIDTH / BLOCK)) * BLOCK,
            y: Math.floor(Math.random() * (HEIGHT / BLOCK)) * BLOCK
        };

        const inStartSafeArea =
            Math.abs(candidate.x - snake[0].x) <= START_SAFE_RADIUS * BLOCK
            && Math.abs(candidate.y - snake[0].y) <= START_SAFE_RADIUS * BLOCK;
        const overlapsSnake = snake.some(part => part.x === candidate.x && part.y === candidate.y);
        const overlapsFood = food.x === candidate.x && food.y === candidate.y;
        const overlapsList = list.some(item => item.x === candidate.x && item.y === candidate.y);

        if (!inStartSafeArea && !overlapsSnake && !overlapsFood && !overlapsList) {
            list.push(candidate);
        }
    }

    return list;
}

function startGame(selectedDifficulty) {
    difficulty = selectedDifficulty;
    currentPlayerName = normalizePlayerName(playerNameElement.value);
    playerNameElement.value = currentPlayerName;

    try {
        localStorage.setItem(PLAYER_NAME_KEY, currentPlayerName);
    } catch (error) {
        // 昵称仍会用于当前会话。
    }

    const settings = DIFFICULTIES[difficulty];
    currentDifficultyElement.textContent = `${settings.name} · ${settings.englishName}`;
    currentDifficultyElement.style.color = settings.color;
    mainMenuElement.hidden = true;
    gameScreenElement.hidden = false;
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
    const result = recordScore();
    resultScoreElement.textContent = String(score);

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
        state = "PAUSE";
        touchPauseElement.textContent = "继续";
    } else if (state === "PAUSE") {
        state = "PLAYING";
        touchPauseElement.textContent = "暂停";
    }
}

difficultyButtons.forEach(button => {
    button.addEventListener("click", () => startGame(button.dataset.difficulty));
});

leaderboardTabs.forEach(tab => {
    tab.addEventListener("click", () => selectLeaderboard(tab.dataset.leaderboardDifficulty));
});

directionButtons.forEach(button => {
    button.addEventListener("pointerdown", event => {
        event.preventDefault();
        changeDirection(button.dataset.direction);
    });
});

playerNameElement.addEventListener("change", () => {
    playerNameElement.value = normalizePlayerName(playerNameElement.value);
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

touchPauseElement.addEventListener("click", togglePause);
touchRestartElement.addEventListener("click", resetGame);

canvas.addEventListener("click", () => canvas.focus());

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
    const hitObstacle = obstacles.some(item => item.x === head.x && item.y === head.y);

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

function draw() {
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
    obstacles.forEach(item => {
        ctx.fillRect(item.x + 2, item.y + 2, BLOCK - 4, BLOCK - 4);
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

try {
    playerNameElement.value = localStorage.getItem(PLAYER_NAME_KEY) || "";
} catch (error) {
    playerNameElement.value = "";
}

renderLeaderboard();
gameLoop();
