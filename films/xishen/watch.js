"use strict";
(() => {
  const episodes = [
    {title:"01 · 戏鬼回家", id:"ep01", duration:"03:30", chapters:[[0,"序幕"],[10,"雨夜迷失"],[52,"两份记忆"],[102,"回家"],[132,"水桶与异声"],[182,"不可能的重逢"]]},
    {title:"02 · 我们在看着你", id:"ep02", duration:"03:30", chapters:[[0,"同一夜"],[37,"没有出口的舞台"],[76,"观众"],[133,"现实中的字"],[152,"白昼极光"],[162,"乱葬岗"],[192,"灾厄指针"]]},
    {title:"03 · 陈氏编导法则", id:"ep03", duration:"04:00", chapters:[[0,"同一清晨"],[12,"撒盐少年"],[42,"诊所"],[82,"灰界"],[112,"转介信"],[142,"早餐铺"],[172,"第九条"],[212,"另一位演员"]]},
    {title:"开篇三集 · 连续版", id:"xishen_complete", duration:"11:00", poster:"ep01", chapters:[[0,"第一集 · 戏鬼回家"],[210,"第二集 · 我们在看着你"],[420,"第三集 · 陈氏编导法则"]]}
  ];
  const player=document.getElementById("player"), status=document.getElementById("playback-status");
  const cards=[...document.querySelectorAll("[data-episode]")];
  const next=document.getElementById("autonext"), complete=document.getElementById("complete");
  const mediaVersion=document.documentElement.dataset.mediaVersion;
  function filmUrl(id){return `assets/film/${id}.mp4`+(mediaVersion?`?v=${mediaVersion}`:"");}
  let selected=0, pendingSeek=null;
  function time(seconds){return `${String(Math.floor(seconds/60)).padStart(2,"0")}:${String(seconds%60).padStart(2,"0")}`;}
  function chapters(episode){
    const list=document.getElementById("chapters"); list.replaceChildren();
    for(const [at,label] of episode.chapters){
      const button=document.createElement("button"); button.type="button"; button.className="chapter";
      const clock=document.createElement("time"); clock.textContent=time(at);
      button.append(clock,document.createTextNode(label));
      button.addEventListener("click",()=>{
        if(player.readyState<1) pendingSeek=at; else player.currentTime=at;
        player.play().catch(()=>{status.textContent="点击播放器继续观看。";});
      });
      list.append(button);
    }
  }
  function select(index,play=false){
    selected=index; pendingSeek=null; status.textContent="";
    const episode=episodes[index];
    cards.forEach((card,i)=>{card.classList.toggle("active",i===index);card.setAttribute("aria-pressed",String(i===index));});
    complete.setAttribute("aria-pressed",String(index===3));
    next.disabled=index===3;
    player.pause(); player.src=filmUrl(episode.id);
    player.poster=`assets/images/${episode.poster||episode.id}.jpg`;
    player.setAttribute("aria-label",episode.title); player.load();
    document.getElementById("episode-title").textContent=episode.title;
    document.getElementById("duration").textContent=episode.duration;
    const download=document.getElementById("download");
    download.href=filmUrl(episode.id); download.textContent=index===3?"下载连续版 ↓":"下载本集 ↓";
    chapters(episode);
    if(play)player.play().catch(()=>{status.textContent="点击播放器继续观看。";});
  }
  cards.forEach((card,index)=>card.addEventListener("click",()=>select(index,!player.paused)));
  complete.addEventListener("click",()=>select(3,!player.paused));
  player.addEventListener("loadedmetadata",()=>{if(pendingSeek!==null){player.currentTime=pendingSeek;pendingSeek=null;}});
  player.addEventListener("playing",()=>{status.textContent="";});
  player.addEventListener("error",()=>{status.textContent="暂时无法播放这集，请确认本地成片文件可用。";});
  player.addEventListener("ended",()=>{if(next.checked&&selected<2)select(selected+1,true);});
  chapters(episodes[0]);
})();
