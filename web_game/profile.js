/* 用户中心（profile.html）。
 *
 * 数据全部来自后端接口，本地只负责渲染：
 *   GET    /api/auth/me                账号概览
 *   GET    /api/scores/mine            战绩
 *   GET    /api/auth/sessions          登录设备
 *   PATCH  /api/auth/me                改昵称
 *   POST   /api/auth/password          改密码
 *   DELETE /api/auth/sessions/{id}     退出某个设备
 *   DELETE /api/auth/account           注销账号
 */
(function () {
    const API_BASE = "";   // 同源托管时留空，与 snake.js 保持一致
    const AUTH_TOKEN_KEY = "greedySnakeAuthToken";
    const PASSWORD_MIN_LENGTH = 8;  // 与后端 MIN_PASSWORD_LENGTH 保持一致
    const AVATAR_SIZE = 256;        // 头像裁剪后的成品边长，在上传前就压到这么小

    const DIFFICULTY_NAMES = { easy: "低等", medium: "中等", hard: "高等" };
    const DIFFICULTY_ORDER = ["easy", "medium", "hard"];

    const avatarButton = document.getElementById("avatarButton");
    const avatarInput = document.getElementById("avatarInput");
    const avatarImageElement = document.getElementById("profileAvatarImage");
    const avatarLetterElement = document.getElementById("profileAvatarLetter");
    const avatarRemoveButton = document.getElementById("avatarRemove");
    const avatarStatusElement = document.getElementById("avatarStatus");

    const nicknameElement = document.getElementById("profileNickname");
    const emailElement = document.getElementById("profileEmail");
    const joinedElement = document.getElementById("profileJoined");
    const totalGamesElement = document.getElementById("profileTotalGames");

    const bestGridElement = document.getElementById("bestGrid");
    const statsEmptyElement = document.getElementById("statsEmpty");
    const recordWrapElement = document.getElementById("recordWrap");
    const recordBodyElement = document.getElementById("recordBody");

    const nicknameForm = document.getElementById("nicknameForm");
    const passwordForm = document.getElementById("passwordForm");
    const accountStatusElement = document.getElementById("accountStatus");

    const sessionListElement = document.getElementById("sessionList");
    const sessionStatusElement = document.getElementById("sessionStatus");
    const logoutButton = document.getElementById("logoutButton");

    const deleteAccountButton = document.getElementById("deleteAccount");
    const deleteDialog = document.getElementById("deleteDialog");
    const deleteConfirmPanel = document.getElementById("deleteConfirmPanel");
    const deleteDonePanel = document.getElementById("deleteDonePanel");
    const deleteCancelButton = document.getElementById("deleteCancel");
    const deleteConfirmButton = document.getElementById("deleteConfirm");
    const deleteDoneButton = document.getElementById("deleteDone");
    const deleteDoneTextElement = document.getElementById("deleteDoneText");
    const deleteStatusElement = document.getElementById("deleteStatus");

    let currentUser = null;

    /* ── 基础工具 ─────────────────────────────────────────── */

    function getToken() {
        try {
            return localStorage.getItem(AUTH_TOKEN_KEY) || "";
        } catch (error) {
            return "";
        }
    }

    function clearToken() {
        try {
            localStorage.removeItem(AUTH_TOKEN_KEY);
        } catch (error) {
            // 浏览器拒绝存储操作时忽略：令牌在服务端已经失效，留着也没用
        }
    }

    function toLogin() {
        window.location.replace("../../?login=required");
    }

    const FIELD_LABELS = {
        nickname: "昵称",
        email: "邮箱",
        password: "密码",
        current_password: "当前密码",
        new_password: "新密码",
    };

    // 后端校验失败时 detail 是数组，转成可读文案，否则界面会显示 [object Object]
    function readableError(body) {
        const detail = body && body.detail;
        if (typeof detail === "string") return detail;
        if (Array.isArray(detail)) {
            return detail.map(item => {
                const field = Array.isArray(item && item.loc) ? item.loc[item.loc.length - 1] : "";
                const label = FIELD_LABELS[field] || "输入内容";
                switch (item && item.type) {
                    case "missing": return `请填写${label}`;
                    case "string_too_short": return `${label}长度不足`;
                    case "string_too_long": return `${label}超出长度限制`;
                    case "value_error": return `${label}格式不正确`;
                    default: return `${label}校验未通过`;
                }
            }).join("；");
        }
        return "操作失败，请稍后再试。";
    }

    async function api(path, options = {}) {
        const token = getToken();
        const headers = Object.assign({}, options.headers || {});
        if (token) headers.Authorization = `Bearer ${token}`;

        let response;
        try {
            response = await fetch(`${API_BASE}${path}`, Object.assign({}, options, { headers }));
        } catch (error) {
            throw new Error("无法连接账号服务，请确认 FastAPI 和 MySQL 已启动。");
        }

        if (response.status === 401) {
            // 令牌失效：清掉再回登录页，别让用户停在一个点什么都没反应的页面上
            clearToken();
            toLogin();
            throw new Error("登录已失效");
        }

        let body = null;
        if (response.status !== 204) {
            try {
                body = await response.json();
            } catch (error) {
                body = null;
            }
        }

        if (!response.ok) throw new Error(readableError(body));
        return body;
    }

    /* ── 时间与展示 ───────────────────────────────────────── */

    function parseServerTime(value) {
        if (!value) return null;
        // 后端存的是 UTC 的 naive 时间，序列化出来不带时区标记。
        // 直接 new Date() 会被当成本地时间解析，显示出来会差几个小时，所以补上 Z。
        const text = /(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`;
        const date = new Date(text);
        return Number.isNaN(date.getTime()) ? null : date;
    }

    const pad = value => String(value).padStart(2, "0");

    function formatDateTime(value) {
        const date = parseServerTime(value);
        if (!date) return "--";
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
            + ` ${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }

    function formatDate(value) {
        const date = parseServerTime(value);
        if (!date) return "--";
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
    }

    function formatDuration(seconds) {
        const total = Math.max(0, Math.round(seconds || 0));
        return `${pad(Math.floor(total / 60))}:${pad(total % 60)}`;
    }

    function avatarLetter(nickname) {
        const text = (nickname || "").trim();
        if (!text) return "·";
        // 用 Array.from 取首个字符，这样 emoji 之类的代理对不会被截断
        return Array.from(text)[0].toUpperCase();
    }

    function describeDevice(userAgent) {
        if (!userAgent) return "未知设备";
        // Edge 与 Opera 的 UA 里也带着 Chrome，必须先判断它们
        const browser =
            /Edg\//.test(userAgent) ? "Edge"
            : /OPR\/|Opera/.test(userAgent) ? "Opera"
            : /Firefox\//.test(userAgent) ? "Firefox"
            : /Chrome\//.test(userAgent) ? "Chrome"
            : /Safari\//.test(userAgent) ? "Safari"
            : "浏览器";
        const system =
            /Windows NT/.test(userAgent) ? "Windows"
            : /iPhone|iPad|iPod/.test(userAgent) ? "iOS"
            : /Android/.test(userAgent) ? "Android"
            : /Mac OS X/.test(userAgent) ? "macOS"
            : /Linux/.test(userAgent) ? "Linux"
            : "";
        return system ? `${browser} · ${system}` : browser;
    }

    function setStatus(element, message, tone) {
        element.textContent = message || "";
        element.classList.toggle("is-ok", tone === "ok");
        element.classList.toggle("is-error", tone === "error");
    }

    /* ── 账号概览 ─────────────────────────────────────────── */

    function applyAvatar(avatarUrl, nickname) {
        // 首字始终写好：没有头像时它就是头像本身，有头像时被 CSS 让位
        avatarLetterElement.textContent = avatarLetter(nickname);

        avatarImageElement.hidden = !avatarUrl;
        avatarButton.dataset.hasImage = avatarUrl ? "true" : "false";
        avatarRemoveButton.hidden = !avatarUrl;

        if (avatarUrl) {
            avatarImageElement.src = avatarUrl;
        } else {
            // 把 src 也清掉，否则移除头像后浏览器还留着上一张
            avatarImageElement.removeAttribute("src");
        }
    }

    function applyUser(user) {
        currentUser = user;
        nicknameElement.textContent = user.nickname;
        emailElement.textContent = user.email;
        joinedElement.textContent = formatDate(user.created_at);
        applyAvatar(user.avatar_url, user.nickname);
        // 昵称输入框预填当前值，改起来只需补几个字
        nicknameForm.elements.nickname.value = user.nickname;
        document.title = `${user.nickname} · 用户中心`;
    }

    async function loadProfile() {
        const user = await api("/api/auth/me");
        applyUser(user);
        document.body.classList.remove("authPending");
    }

    /* ── 上传头像 ─────────────────────────────────────────── */

    /* 图片在浏览器里就裁好压好再上传：既省流量，也让后端不必依赖图像处理库
     * （Pillow 不在 requirements 里，也不打算为此加一个依赖）。 */

    function loadImageSource(file) {
        // createImageBitmap 更快，也不用经过一次 object URL；老浏览器回退到 Image
        if (typeof createImageBitmap === "function") {
            return createImageBitmap(file);
        }
        return new Promise((resolve, reject) => {
            const url = URL.createObjectURL(file);
            const image = new Image();
            image.onload = () => {
                URL.revokeObjectURL(url);
                resolve(image);
            };
            image.onerror = () => {
                URL.revokeObjectURL(url);
                reject(new Error("这张图片读不出来，换一张试试。"));
            };
            image.src = url;
        });
    }

    function canvasToBlob(canvas) {
        return new Promise((resolve, reject) => {
            const encode = type => canvas.toBlob(
                blob => (blob ? resolve(blob) : reject(new Error("图片处理失败，换一张试试。"))),
                type,
                0.86,
            );
            // WebP 体积明显更小；个别浏览器不支持时退回 JPEG
            if (canvas.toDataURL("image/webp").startsWith("data:image/webp")) {
                encode("image/webp");
            } else {
                encode("image/jpeg");
            }
        });
    }

    async function buildAvatarBlob(file) {
        if (file.type === "image/svg+xml" || /\.svg$/i.test(file.name || "")) {
            // 后端也会拒，这里先拦一道，省一趟往返
            throw new Error("不支持 SVG，请换一张 JPEG / PNG / WebP 图片。");
        }
        if (file.type && !file.type.startsWith("image/")) {
            throw new Error("请选择图片文件。");
        }

        const source = await loadImageSource(file);
        const side = Math.min(source.width, source.height);
        if (!side) {
            throw new Error("这张图片读不出来，换一张试试。");
        }

        const canvas = document.createElement("canvas");
        canvas.width = AVATAR_SIZE;
        canvas.height = AVATAR_SIZE;
        const context = canvas.getContext("2d");
        context.imageSmoothingQuality = "high";
        // 居中裁成正方形再缩放。直接拉成正方形会把头像压变形。
        context.drawImage(
            source,
            (source.width - side) / 2,
            (source.height - side) / 2,
            side,
            side,
            0,
            0,
            AVATAR_SIZE,
            AVATAR_SIZE,
        );
        // ImageBitmap 占的是显存，用完要显式释放
        if (typeof source.close === "function") source.close();

        return canvasToBlob(canvas);
    }

    function setUpAvatarBusy(busy) {
        avatarButton.disabled = busy;
        avatarRemoveButton.disabled = busy;
    }

    async function uploadAvatar(file) {
        setUpAvatarBusy(true);
        setStatus(avatarStatusElement, "正在处理图片…");

        try {
            const blob = await buildAvatarBlob(file);
            const user = await api("/api/auth/avatar", {
                method: "PUT",
                headers: { "Content-Type": blob.type },
                body: blob,
            });
            applyUser(user);
            setStatus(
                avatarStatusElement,
                `头像已更新（${Math.max(1, Math.round(blob.size / 1024))} KB）。`,
                "ok",
            );
        } catch (error) {
            setStatus(avatarStatusElement, error.message, "error");
        } finally {
            setUpAvatarBusy(false);
        }
    }

    avatarButton.addEventListener("click", () => avatarInput.click());

    avatarInput.addEventListener("change", async () => {
        const file = avatarInput.files && avatarInput.files[0];
        // 先把 input 清空：否则连着选同一个文件不会再触发 change
        avatarInput.value = "";
        if (file) await uploadAvatar(file);
    });

    // 图片取不到就退回首字，别在页面上留一个破图图标
    avatarImageElement.addEventListener("error", () => {
        avatarImageElement.hidden = true;
        avatarButton.dataset.hasImage = "false";
    });

    avatarRemoveButton.addEventListener("click", async () => {
        setUpAvatarBusy(true);
        setStatus(avatarStatusElement, "正在移除…");

        try {
            applyUser(await api("/api/auth/avatar", { method: "DELETE" }));
            setStatus(avatarStatusElement, "已恢复成默认头像。", "ok");
        } catch (error) {
            setStatus(avatarStatusElement, error.message, "error");
        } finally {
            setUpAvatarBusy(false);
        }
    });

    /* ── 我的战绩 ─────────────────────────────────────────── */

    function renderStats(stats) {
        bestGridElement.replaceChildren();
        for (const difficulty of DIFFICULTY_ORDER) {
            const best = stats.best[difficulty];

            const card = document.createElement("div");
            card.className = "bestCard";
            card.dataset.difficulty = difficulty;

            const label = document.createElement("span");
            label.textContent = `${DIFFICULTY_NAMES[difficulty]}难度最佳`;

            const value = document.createElement("strong");
            if (best === null || best === undefined) {
                value.textContent = "暂无记录";
                value.className = "is-empty";
            } else {
                value.textContent = `${best} 分`;
            }

            card.append(label, value);
            bestGridElement.append(card);
        }

        totalGamesElement.textContent = `${stats.total_games} 局`;

        const hasRecords = stats.recent.length > 0;
        statsEmptyElement.hidden = hasRecords;
        recordWrapElement.hidden = !hasRecords;
        recordBodyElement.replaceChildren();

        for (const item of stats.recent) {
            const cells = [
                DIFFICULTY_NAMES[item.difficulty] || item.difficulty,
                `${item.score}`,
                `${item.food_eaten}`,
                `${item.moves}`,
                formatDuration(item.duration_seconds),
                formatDateTime(item.created_at),
            ];

            const row = document.createElement("tr");
            cells.forEach((text, index) => {
                const cell = document.createElement("td");
                cell.textContent = text;
                if (index === 0) cell.className = "difficultyTag";
                row.append(cell);
            });
            recordBodyElement.append(row);
        }
    }

    async function loadStats() {
        try {
            renderStats(await api("/api/scores/mine"));
        } catch (error) {
            // 战绩拉不到不该挡住页面其它部分，就地说明即可
            totalGamesElement.textContent = "--";
            statsEmptyElement.hidden = false;
            statsEmptyElement.textContent = `战绩加载失败：${error.message}`;
        }
    }

    /* ── 登录设备 ─────────────────────────────────────────── */

    function renderSessions(sessions) {
        sessionListElement.replaceChildren();

        for (const item of sessions) {
            const row = document.createElement("li");
            row.className = "sessionItem";

            const info = document.createElement("div");
            info.className = "sessionInfo";

            const device = document.createElement("span");
            device.className = "sessionDevice";
            device.textContent = describeDevice(item.user_agent);
            if (item.current) {
                const badge = document.createElement("span");
                badge.className = "sessionBadge";
                badge.textContent = "当前设备";
                device.append(badge);
            }

            const meta = document.createElement("span");
            meta.className = "sessionMeta";
            const parts = [
                `登录于 ${formatDateTime(item.created_at)}`,
                `有效至 ${formatDate(item.expires_at)}`,
            ];
            if (item.ip_address) parts.push(`IP ${item.ip_address}`);
            meta.textContent = parts.join(" · ");

            info.append(device, meta);
            row.append(info);

            if (!item.current) {
                const revokeButton = document.createElement("button");
                revokeButton.type = "button";
                revokeButton.className = "sessionRevoke";
                revokeButton.textContent = "退出该设备";
                revokeButton.addEventListener("click", () => revokeSession(item.id, revokeButton));
                row.append(revokeButton);
            }

            sessionListElement.append(row);
        }
    }

    async function loadSessions() {
        try {
            renderSessions(await api("/api/auth/sessions"));
        } catch (error) {
            setStatus(sessionStatusElement, `登录设备加载失败：${error.message}`, "error");
        }
    }

    async function revokeSession(sessionId, button) {
        button.disabled = true;
        setStatus(sessionStatusElement, "正在退出该设备…");

        try {
            await api(`/api/auth/sessions/${sessionId}`, { method: "DELETE" });
            setStatus(sessionStatusElement, "已退出该设备。", "ok");
            await loadSessions();
        } catch (error) {
            button.disabled = false;
            setStatus(sessionStatusElement, error.message, "error");
        }
    }

    /* ── 改昵称 ───────────────────────────────────────────── */

    nicknameForm.addEventListener("submit", async event => {
        event.preventDefault();
        const form = event.currentTarget;
        const button = form.querySelector("button[type='submit']");
        // 页面上的表单都关了原生校验，空格之类的边界得自己查
        const nickname = (form.elements.nickname.value || "").trim();

        if (!nickname) {
            setStatus(accountStatusElement, "昵称不能为空或全是空格。", "error");
            form.elements.nickname.focus();
            return;
        }
        if (nickname === currentUser?.nickname) {
            setStatus(accountStatusElement, "昵称没有变化。", "error");
            return;
        }

        button.disabled = true;
        setStatus(accountStatusElement, "正在保存…");

        try {
            const user = await api("/api/auth/me", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ nickname }),
            });
            applyUser(user);
            setStatus(accountStatusElement, "昵称已更新，历史成绩也一并跟过来了。", "ok");
            // 榜单上显示的是昵称，改完顺手把战绩刷一遍
            await loadStats();
        } catch (error) {
            setStatus(accountStatusElement, error.message, "error");
        } finally {
            button.disabled = false;
        }
    });

    /* ── 改密码 ───────────────────────────────────────────── */

    passwordForm.addEventListener("submit", async event => {
        event.preventDefault();
        const form = event.currentTarget;
        const button = form.querySelector("button[type='submit']");
        const currentPassword = form.elements.currentPassword.value || "";
        const newPassword = form.elements.newPassword.value || "";
        const confirmPassword = form.elements.confirmPassword.value || "";

        if (!currentPassword) {
            setStatus(accountStatusElement, "请输入当前密码。", "error");
            form.elements.currentPassword.focus();
            return;
        }
        if (newPassword.trim().length < PASSWORD_MIN_LENGTH) {
            setStatus(accountStatusElement, `新密码至少 ${PASSWORD_MIN_LENGTH} 位，且不能全是空格。`, "error");
            form.elements.newPassword.focus();
            return;
        }
        if (newPassword !== confirmPassword) {
            setStatus(accountStatusElement, "两次输入的新密码不一致。", "error");
            form.elements.confirmPassword.focus();
            return;
        }

        button.disabled = true;
        setStatus(accountStatusElement, "正在修改…");

        try {
            await api("/api/auth/password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword,
                }),
            });
            form.reset();
            setStatus(accountStatusElement, "密码已修改，其他设备上的登录都已退出。", "ok");
            await loadSessions();
        } catch (error) {
            setStatus(accountStatusElement, error.message, "error");
        } finally {
            button.disabled = false;
        }
    });

    /* ── 退出登录 ─────────────────────────────────────────── */

    logoutButton.addEventListener("click", async () => {
        logoutButton.disabled = true;
        try {
            await api("/api/auth/logout", { method: "POST" });
        } catch (error) {
            // 服务端没删掉也无妨：本地令牌照样清，用户看到的就是"已退出"
        }
        clearToken();
        window.location.replace("../../");
    });

    /* ── 注销账号 ─────────────────────────────────────────── */

    function openDeleteDialog() {
        deleteConfirmPanel.hidden = false;
        deleteDonePanel.hidden = true;
        deleteCancelButton.disabled = false;
        deleteConfirmButton.disabled = false;
        deleteStatusElement.textContent = "";
        deleteDialog.showModal();
    }

    async function requestAccountDeletion() {
        deleteCancelButton.disabled = true;
        deleteConfirmButton.disabled = true;
        deleteStatusElement.textContent = "正在提交…";

        try {
            const result = await api("/api/auth/account", { method: "DELETE" });

            // 服务端提交后会让该账号的所有会话立即失效，这里同步清掉本地令牌，
            // 否则浏览器会一直拿着一个已失效的令牌
            clearToken();

            deleteDoneTextElement.textContent =
                `若 ${result.grace_days} 天内没有重新登录，账号、登录状态与全部历史成绩`
                + `将被清除。期间重新登录即可自动恢复。`;
            deleteConfirmPanel.hidden = true;
            deleteDonePanel.hidden = false;
        } catch (error) {
            deleteCancelButton.disabled = false;
            deleteConfirmButton.disabled = false;
            deleteStatusElement.textContent = error.message || "提交失败，请稍后再试。";
        }
    }

    deleteAccountButton.addEventListener("click", openDeleteDialog);
    deleteCancelButton.addEventListener("click", () => deleteDialog.close());
    deleteConfirmButton.addEventListener("click", requestAccountDeletion);
    deleteDoneButton.addEventListener("click", () => {
        deleteDialog.close();
        window.location.replace("../../");
    });

    /* ── 启动 ─────────────────────────────────────────────── */

    (async function boot() {
        if (!getToken()) {
            toLogin();
            return;
        }

        try {
            await loadProfile();
        } catch (error) {
            // 401 已由 api() 处理并跳转；其余错误（比如数据库暂时不可用）就地说明
            if (getToken()) {
                document.body.classList.remove("authPending");
                setStatus(accountStatusElement, `账号信息加载失败：${error.message}`, "error");
            }
            return;
        }

        await Promise.all([loadStats(), loadSessions()]);
    })();
})();
