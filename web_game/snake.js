const canvas =
document.getElementById("game");


const ctx =
canvas.getContext("2d");


const scoreElement =
document.getElementById("score");


const bestElement =
document.getElementById("best");


const speedElement =
document.getElementById("speed");


const mainMenuElement =
document.getElementById("mainMenu");


const gameScreenElement =
document.getElementById("gameScreen");


const currentDifficultyElement =
document.getElementById("currentDifficulty");


const backToMenuElement =
document.getElementById("backToMenu");


const difficultyButtons =
document.querySelectorAll("[data-difficulty]");


// 点击画布获得键盘焦点

canvas.onclick=function(){

    canvas.focus();

};



const WIDTH = 1000;

const HEIGHT = 800;


const BLOCK=20;


// 蛇头周围预留安全区，避免障碍物堵住开局路线
const START_SAFE_RADIUS=5;


const DIFFICULTIES={

    easy:{
        startSpeed:220,
        speedUpEvery:100,
        speedStep:10,
        minSpeed:120,
        obstacleCount:0,
        obstacleMoveEvery:0,
        hint:"新手模式：速度较慢，没有障碍物"
    },

    medium:{
        startSpeed:150,
        speedUpEvery:50,
        speedStep:15,
        minSpeed:50,
        obstacleCount:10,
        obstacleMoveEvery:0,
        hint:"中等模式：速度较快，有 10 个障碍物"
    },

    hard:{
        startSpeed:125,
        speedUpEvery:40,
        speedStep:10,
        minSpeed:45,
        obstacleCount:15,
        obstacleMoveEvery:25,
        hint:"高等模式：速度更快，15 个障碍物每 25 步变换位置"
    }

};


let difficulty="easy";



// 游戏状态

let state="MENU";


// 蛇

let snake=[];


// 食物

let food={};


// 障碍物

let obstacles=[];


// 当前方向与下一步方向

let direction="RIGHT";


let nextDirection="RIGHT";


// 分数

let score=0;


// 已移动步数与障碍物变换提示
let moveCount=0;


let obstacleMoveNotice=0;


// 游戏速度(ms)

let speed = DIFFICULTIES[difficulty].startSpeed;


// 最高分

let bestScore=0;


function getBestScore(){

    const storageKey =
    difficulty==="medium"
    ? "bestScore"
    : "bestScore_" + difficulty;

    return Number(
        localStorage.getItem(storageKey)
    ) || 0;

}


function saveBestScore(){

    const storageKey =
    difficulty==="medium"
    ? "bestScore"
    : "bestScore_" + difficulty;

    localStorage.setItem(
        storageKey,
        bestScore
    );

}


// ======================
// 初始化
// ======================

function resetGame(){


    const settings=DIFFICULTIES[difficulty];


    snake=[

        {x:400,y:400},

        {x:380,y:400},

        {x:360,y:400}

    ];


    direction="RIGHT";


    nextDirection="RIGHT";


    score=0;


    moveCount=0;


    obstacleMoveNotice=0;


    speed=settings.startSpeed;


    bestScore=getBestScore();


    speedElement.innerHTML = "Speed: 1";


    scoreElement.innerHTML = "Score: 0";


    bestElement.innerHTML = "Best: " + bestScore;


    obstacles=createObstacles();


    food=createFood();


    state="START";

}



// ======================
// 根据分数调整速度
// ======================

function updateSpeed(){


    const settings=DIFFICULTIES[difficulty];


    speed =
    settings.startSpeed
    - Math.floor(score / settings.speedUpEvery)
    * settings.speedStep;



    if(speed < settings.minSpeed){

        speed = settings.minSpeed;

    }



    // 计算速度等级

    let level =
    Math.floor(
        (settings.startSpeed-speed)
        / settings.speedStep
    )+1;



    speedElement.innerHTML =
    "Speed: " + level;


}



// ======================
// 创建食物
// ======================

function createFood(){


    while(true){


        let f={

            x:
            Math.floor(
                Math.random()*50
            )*BLOCK,


            y:
            Math.floor(
                Math.random()*40
            )*BLOCK

        };



        if(
            !snake.some(
                s =>
                s.x===f.x &&
                s.y===f.y
            )
            &&
            !obstacles.some(
                o =>
                o.x===f.x &&
                o.y===f.y
            )
        ){

            return f;

        }

    }

}



// ======================
// 创建障碍物
// ======================

function createObstacles(){


    let list=[];


    const obstacleCount=
    DIFFICULTIES[difficulty].obstacleCount;


    while(list.length<obstacleCount){


        let o={

            x:
            Math.floor(
                Math.random()*50
            )*BLOCK,


            y:
            Math.floor(
                Math.random()*40
            )*BLOCK

        };



        const inStartSafeArea =
            Math.abs(o.x-snake[0].x) <= START_SAFE_RADIUS*BLOCK
            &&
            Math.abs(o.y-snake[0].y) <= START_SAFE_RADIUS*BLOCK;


        if(
            !snake.some(
                s =>
                s.x===o.x &&
                s.y===o.y
            )
            &&
            !inStartSafeArea
            &&
            !(
                food.x===o.x &&
                food.y===o.y
            )
            &&
            !list.some(
                item =>
                item.x===o.x &&
                item.y===o.y
            )
        ){

            list.push(o);

        }


    }


    return list;

}


const DIFFICULTY_NAMES={
    easy:"低等难度 · EASY",
    medium:"中等难度 · MEDIUM",
    hard:"高等难度 · HARD"
};


function startGame(selectedDifficulty){

    difficulty=selectedDifficulty;

    currentDifficultyElement.innerHTML =
    DIFFICULTY_NAMES[difficulty];

    mainMenuElement.hidden=true;

    gameScreenElement.hidden=false;

    resetGame();

    canvas.focus();

}


function showMainMenu(){

    state="MENU";

    gameScreenElement.hidden=true;

    mainMenuElement.hidden=false;

    difficultyButtons[0].focus();

}


difficultyButtons.forEach(button=>{

    button.addEventListener(
    "click",
    function(){

        startGame(button.dataset.difficulty);

    });

});


backToMenuElement.addEventListener(
"click",
showMainMenu
);



// ======================
// 键盘
// ======================

document.addEventListener(
"keydown",
function(e){


    if(e.key==="Escape" && !gameScreenElement.hidden){

        showMainMenu();

        return;

    }


    if(gameScreenElement.hidden){

        return;

    }



    // 阻止方向键滚动网页

    if(
        e.key === "ArrowUp" ||
        e.key === "ArrowDown" ||
        e.key === "ArrowLeft" ||
        e.key === "ArrowRight"
    ){

        e.preventDefault();

    }



    // 空格暂停

    if(e.code==="Space"){


        if(state==="PLAYING"){

            state="PAUSE";

        }

        else if(state==="PAUSE"){

            state="PLAYING";

        }


        return;

    }



    // 游戏结束

    if(state==="GAMEOVER"){


        if(
            e.key==="r"
            ||
            e.key==="R"
        ){

            resetGame();

        }


        return;

    }



    if(e.key==="ArrowUp"
    &&
    direction!=="DOWN"){


        nextDirection="UP";

        state="PLAYING";

    }



    else if(
        e.key==="ArrowDown"
        &&
        direction!=="UP"
    ){


        nextDirection="DOWN";

        state="PLAYING";

    }



    else if(
        e.key==="ArrowLeft"
        &&
        direction!=="RIGHT"
    ){


        nextDirection="LEFT";

        state="PLAYING";

    }



    else if(
        e.key==="ArrowRight"
        &&
        direction!=="LEFT"
    ){


        nextDirection="RIGHT";

        state="PLAYING";

    }


});



// ======================
// 更新游戏
// ======================

function update(){


    if(state!=="PLAYING"){

        return;

    }


    direction=nextDirection;


    if(obstacleMoveNotice>0){

        obstacleMoveNotice--;

    }



    let head={

        x:snake[0].x,

        y:snake[0].y

    };



    if(direction==="UP")
        head.y-=BLOCK;


    if(direction==="DOWN")
        head.y+=BLOCK;


    if(direction==="LEFT")
        head.x-=BLOCK;


    if(direction==="RIGHT")
        head.x+=BLOCK;




    snake.unshift(head);



    // 吃食物

    if(
        head.x===food.x
        &&
        head.y===food.y
    ){

        score += 10;


        // 更新速度

        updateSpeed();


        scoreElement.innerHTML =
        "Score: " + score;


        if(score > bestScore){


            bestScore = score;


            saveBestScore();


            bestElement.innerHTML =
            "Best: " + bestScore;


        }


        food=createFood();


    }
    else{

        // 没吃到食物，删除尾巴

        snake.pop();

    }



    // 撞墙

    if(
        head.x<0
        ||
        head.x>=WIDTH
        ||
        head.y<0
        ||
        head.y>=HEIGHT
    ){

        state="GAMEOVER";

    }



    // 撞自己

    for(
        let i=1;
        i<snake.length;
        i++
    ){

        if(
            head.x===snake[i].x
            &&
            head.y===snake[i].y
        ){

            state="GAMEOVER";

        }

    }



    // 撞障碍


    obstacles.forEach(o=>{


        if(
            head.x===o.x
            &&
            head.y===o.y
        ){

            state="GAMEOVER";

        }


    });


    if(state==="PLAYING"){

        moveCount++;

        const moveEvery =
        DIFFICULTIES[difficulty].obstacleMoveEvery;

        if(
            moveEvery>0
            &&
            moveCount%moveEvery===0
        ){

            obstacles=createObstacles();

            obstacleMoveNotice=6;

        }

    }


}



// ======================
// 绘制
// ======================

function draw(){


    ctx.fillStyle="black";


    ctx.fillRect(
        0,
        0,
        WIDTH,
        HEIGHT
    );



    // 食物

    ctx.fillStyle="red";


    ctx.fillRect(

        food.x,

        food.y,

        BLOCK,

        BLOCK

    );



    // 障碍物

    ctx.fillStyle="gray";


    obstacles.forEach(o=>{


        ctx.fillRect(

            o.x,

            o.y,

            BLOCK,

            BLOCK

        );


    });



    // 蛇


    snake.forEach(
    (s,index)=>{


        ctx.fillStyle =
        index===0
        ?
        "lightgreen"
        :
        "green";


        ctx.fillRect(

            s.x,

            s.y,

            BLOCK,

            BLOCK

        );


    });


    if(obstacleMoveNotice>0){

        ctx.fillStyle="yellow";

        ctx.font="32px Arial";

        ctx.textAlign="center";

        ctx.fillText(
            "OBSTACLES MOVED!",
            WIDTH/2,
            50
        );

    }



    // 暂停界面

    if(state==="PAUSE"){


        ctx.fillStyle="white";

        ctx.font="70px Arial";

        ctx.textAlign="center";


        ctx.fillText(

            "PAUSE",

            WIDTH/2,

            HEIGHT/2

        );


    }



    // 开始


    if(state==="START"){


        ctx.font="40px Arial";


        ctx.textAlign="center";


        ctx.fillText(

            "Press Arrow Key To Start",

            WIDTH/2,

            HEIGHT/2

        );

    }




    // 结束


    if(state==="GAMEOVER"){


        ctx.textAlign="center";


        ctx.fillStyle="red";


        ctx.font="70px Arial";


        ctx.fillText(

            "GAME OVER",

            WIDTH/2,

            HEIGHT/2-80

        );



        ctx.fillStyle="white";


        ctx.font="30px Arial";


        ctx.fillText(

            "Score: "+score,

            WIDTH/2,

            HEIGHT/2

        );



        ctx.fillText(

            "Press R To Restart",

            WIDTH/2,

            HEIGHT/2+80

        );


    }


}



// ======================
// 游戏循环
// ======================

function loop(){


    update();


    draw();


}



function gameLoop(){


    loop();


    setTimeout(
        gameLoop,
        speed
    );


}


gameLoop();


