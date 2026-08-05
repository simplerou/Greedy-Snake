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


// 点击画布获得键盘焦点

canvas.focus();

canvas.onclick=function(){

    canvas.focus();

};



const WIDTH = 1000;

const HEIGHT = 800;


const BLOCK=20;



// 游戏状态

let state="START";


// 蛇

let snake=[];


// 食物

let food={};


// 障碍物

let obstacles=[];


// 方向

let direction="STOP";


// 分数

let score=0;


// 游戏速度(ms)

let speed = 100;


// 最高分

let bestScore =
Number(
    localStorage.getItem("bestScore")
) || 0;


// ======================
// 初始化
// ======================

function resetGame(){


    snake=[

        {x:400,y:400},

        {x:380,y:400},

        {x:360,y:400}

    ];


    direction="STOP";


    score=0;


    speed=150;


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


    speed =
    150 - Math.floor(score / 50) * 15;



    if(speed < 50){

        speed = 50;

    }



    // 计算速度等级

    let level =
    Math.floor((150-speed)/15)+1;



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


    while(list.length<10){


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



        if(
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



// ======================
// 键盘
// ======================

document.addEventListener(
"keydown",
function(e){



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


        direction="UP";

        state="PLAYING";

    }



    else if(
        e.key==="ArrowDown"
        &&
        direction!=="UP"
    ){


        direction="DOWN";

        state="PLAYING";

    }



    else if(
        e.key==="ArrowLeft"
        &&
        direction!=="RIGHT"
    ){


        direction="LEFT";

        state="PLAYING";

    }



    else if(
        e.key==="ArrowRight"
        &&
        direction!=="LEFT"
    ){


        direction="RIGHT";

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


            localStorage.setItem(
                "bestScore",
                bestScore
            );


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



resetGame();



function gameLoop(){


    loop();


    setTimeout(
        gameLoop,
        speed
    );


}


gameLoop();


