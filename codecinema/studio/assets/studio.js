"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const copy = value => JSON.parse(JSON.stringify(value));
  let language = navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
  let state, story, selected = "aurora", existing = false, busy = false;
  const words = {
    en: {blendFile:"Blender scene (optional)", blendHelp:"Relative path in this film, such as assets/scenes/world.blend. Leave blank for the built-in world. Use packed assets for portability.", blendCamera:"Camera name (optional)", renderer:"Render with", rendererHelp:"Skia is fast. Blender creates 3D scenes and needs Blender 5.2+. Thumbnails illustrate the 2D looks.", eyebrow:"YOUR NEXT LITTLE FILM", heading:"Pick a world. Make it yours.", intro:"Eight looks, your words, an original soundtrack. Your first film starts here.", choose:"1. Choose a world", looksNote:"Change the look any time", personalize:"2. Make it personal", project:"My films", newFilm:"+ Create a new film", id:"Film ID", idHelp:"A folder name, such as my-trip", format:"Frame", landscape:"Landscape · 16:9", portrait:"Portrait · 9:16", square:"Square · 1:1", title:"Film title", subtitle:"Opening caption", duration:"Length in seconds", quality:"Picture quality", standard:"720p · Fast", high:"1080p · Detailed", low:"360p · Small file", accent:"Choose an accent color", renderTitle:"3. Bring it to life", local:"Made on your computer", render:"Render my film →", preview:"Quick preview", previewHelp:"Quick preview makes a separate 360p video. Your finished master stays available.", ready:"Ready when you are.", download:"Download MP4 ↓", details:"Production details", sceneHeading:"Personalize every scene", sceneNote:"Optional · add, reorder or mix looks", sceneHelp:"Every card is one scene. Change the words and timing, or mix different worlds in one film.", addScene:"+ Add a scene", saved:"Your project and MP4 are saved in films/<film-id>/. Come back here to edit and render again.", scene:"Scene", look:"Look", camera:"Camera", wide:"Wide", drift:"Drift", close:"Close", caption:"Caption", remove:"Remove", working:"Making your film…", done:"Your film is ready. Watch it here, or download the MP4.", previewDone:"Your preview is ready. Make changes or press Render my film for the finished version.", failed:"Something needs fixing. See the production details below.", defaultTitle:"A Little Wonder", voiceTitle:"Add a voice (optional)", voiceText:"Words to speak", voice:"Voice", voiceLanguage:"Spoken language", direction:"Mood / acting direction", voiceHelp:"Leave blank for music only. The speech pack adds expressive local voices on Apple Silicon; macOS also has a basic system voice. Increase the scene length for longer lines."},
    zh: {blendFile:"Blender 场景（可选）", blendHelp:"填写影片内的相对路径，如 assets/scenes/world.blend。留空使用内置场景。建议在 Blender 中打包外部素材。", blendCamera:"摄像机名称（可选）", renderer:"渲染技术", rendererHelp:"Skia 快速生成二维画面。Blender 生成三维场景，需安装 Blender 5.2+。缩略图展示二维风格。", eyebrow:"从这里开始你的下一部短片", heading:"选一个世界，拍你的故事。", intro:"八种风格、你的文字、原创配乐。选好风格与渲染技术，点击生成即可出片。", choose:"1. 选择场景", looksNote:"随时可以更换风格", personalize:"2. 加入你的想法", project:"我的影片", newFilm:"+ 新建影片", id:"影片 ID", idHelp:"用作文件夹名称，例如 my-trip", format:"画幅", landscape:"横屏 · 16:9", portrait:"竖屏 · 9:16", square:"方形 · 1:1", title:"影片标题", subtitle:"开场字幕", duration:"总时长（秒）", quality:"画质", standard:"720p · 快速成片", high:"1080p · 精细画面", low:"360p · 小文件", accent:"自选点缀色", renderTitle:"3. 让画面动起来", local:"在你的电脑上制作", render:"生成我的影片 →", preview:"快速预览", previewHelp:"预览单独输出 360p 视频，已经生成的正式成片仍会保留。", ready:"准备好了，随时开始。", download:"下载 MP4 ↓", details:"制作详情", sceneHeading:"逐个定制分镜", sceneNote:"可选 · 加镜头、调整顺序、混搭风格", sceneHelp:"每张卡片就是一个镜头。可以逐个改文字、时长和场景，也可以让不同的风格出现在同一部影片里。", addScene:"+ 添加镜头", saved:"项目与 MP4 保存在 films/<影片 ID>/。下次从“我的影片”打开，继续修改并重新生成。", scene:"镜头", look:"场景", camera:"镜头运动", wide:"全景", drift:"缓慢移动", close:"推进", caption:"字幕", remove:"移除", working:"正在制作你的影片…", done:"影片已完成，可以直接观看或下载 MP4。", previewDone:"预览已完成。可以继续调整，或点击“生成我的影片”制作正式版本。", failed:"有一项需要修正，请展开下方制作详情。", defaultTitle:"一点奇遇", voiceTitle:"添加配音（可选）", voiceText:"配音台词", voice:"声音", voiceLanguage:"配音语言", direction:"情绪 / 表演提示", voiceHelp:"留空只播放配乐。Apple Silicon 安装语音包后可用情绪配音；Mac 也可用基础系统声音。较长台词请增加镜头时长。"}
  };
  const looks = {
    moonrise:["Moonrise","月夜山峦","Stars & layered mountains","星光与层叠山峦"],
    sunset:["Sunset","金色落日","Warm light & still water","暖光与粼粼水面"],
    aurora:["Aurora","极光之境","Northern lights & a forest lake","北极光与森林湖泊"],
    neon:["Neon City","霓虹城市","City lights & reflections","城市灯光与夜色倒影"],
    ocean:["Ocean","碧海潮汐","Turquoise waves & open skies","碧蓝海浪与开阔天空"],
    ink:["Ink Mountains","水墨远山","Paper, mist & quiet birds","纸上山水、薄雾与飞鸟"],
    cosmos:["Cosmos","漫游宇宙","A ringed planet & distant stars","星环行星与遥远星辰"],
    ember:["Firefly Forest","萤火森林","Small lights & amber warmth","点点萤火与温暖暮色"]
  };
  const chineseCaptions = {
    moonrise:["静夜里的一点光。","夜晚有自己的节奏。","把这一晚留在心里。"], sunset:["再看一眼最后的光。","每一道涟漪都藏着金色。","让黄昏多停留片刻。"],
    aurora:["天空也有故事要讲。","光悄悄经过水面。","带一点奇遇回家。"], neon:["日落之后，城市醒来。","一千扇窗，一千个故事。","找到属于你的那束光。"],
    ocean:["给大海留一点时间。","跟着潮汐，慢慢呼吸。","前方总有新的地平线。"], ink:["一座山，从安静的一笔开始。","让留白自在呼吸。","在纸上，留住一个瞬间。"],
    cosmos:["无尽星空里，一个小小的故事。","每条轨道，都是一次旅行。","别忘了抬头看。"], ember:["跟随最小的光。","森林有自己的韵律。","带一份温暖踏上归途。"]
  };
  const t = key => words[language][key] || key;
  const lookName = key => looks[key][language === "zh" ? 1 : 0];
  const captionsFor = key => language === "zh" ? chineseCaptions[key] : state.presets[key].captions;
  function node(tag, text, className) {const element=document.createElement(tag); if(text!==undefined)element.textContent=text; if(className)element.className=className; return element;}
  function option(value, label) {const element=node("option",label);element.value=value;return element;}
  function translate() {
    document.documentElement.lang=language==="zh"?"zh-CN":"en";
    document.querySelectorAll("[data-text]").forEach(element=>element.textContent=t(element.dataset.text));
    $("language").textContent=language==="zh"?"English":"中文";
    if(state){renderLooks();renderScenes();refreshProjects();}
  }
  function renderLooks() {
    $("presets").replaceChildren();
    for(const key of Object.keys(state.presets)) {
      const button=node("button",undefined,"preset");button.type="button";button.dataset.preset=key;button.setAttribute("aria-pressed",String(key===selected));
      const image=node("img");image.src=`presets/${key}.jpg`;image.alt=lookName(key);image.width=480;image.height=270;
      button.append(image,node("strong",lookName(key)),node("p",looks[key][language==="zh"?3:2]));
      button.addEventListener("click",()=>chooseLook(key));$("presets").append(button);
    }
  }
  function chooseLook(key) {
    selected=key;
    const defaults=new Set(Object.values(state.presets).flatMap(p=>p.captions).concat(Object.values(chineseCaptions).flat()));
    story.scenes.forEach((scene,i)=>{scene.preset=key;if(defaults.has(scene.subtitle))scene.subtitle=captionsFor(key)[i%3];});
    $("subtitle").value=story.scenes[0].subtitle;
    renderLooks();renderScenes();cover();
  }
  function cover() {
    $("poster").src=`presets/${selected}.jpg`;
    $("cover-title").textContent=$("title").value;
    $("cover-subtitle").textContent=$("subtitle").value;
    $("cover-copy").style.color=selected==="ink"?"#253b37":"#f4ece0";
  }
  function refreshProjects() {
    const value=$("projects").value;$("projects").replaceChildren(option("",t("newFilm")));
    state.projects.forEach(project=>$("projects").append(option(project.id,project.story.title)));
    $("projects").value=value;
  }
  function newStory() {
    const title=t("defaultTitle");
    return {version:1,title,seed:7,scenes:["wide","drift","close"].map((camera,i)=>({name:`Scene ${i+1}`,preset:selected,duration_s:4,camera,title:i===1?"":title,subtitle:captionsFor(selected)[i]}))};
  }
  function loadProject(id) {
    const project=state.projects.find(p=>p.id===id);existing=Boolean(project);
    if(project){story=copy(project.story);selected=story.scenes[0].preset;}
    else {story=newStory();let id="myfilm",n=2;while(state.projects.some(p=>p.id===id))id=`myfilm-${n++}`;$("film-id").value=id;}
    if(project)$("film-id").value=project.id;
    $("film-id").readOnly=existing;
    $("title").value=story.title;$("subtitle").value=story.scenes[0].subtitle||"";
    $("duration").value=Number(story.scenes.reduce((sum,s)=>sum+s.duration_s,0).toFixed(3));
    $("renderer").value=project?project.renderer:"skia";
    $("format").value=project?project.format:"landscape";$("quality").value=project?project.quality:"standard";
    $("custom-accent").checked=Boolean(story.scenes[0].accent);$("accent").disabled=!$("custom-accent").checked;
    if(story.scenes[0].accent)$("accent").value=story.scenes[0].accent;
    $("poster").hidden=false;$("video").hidden=true;$("video").pause();$("cover-copy").hidden=false;
    $("download").hidden=true;$("status").textContent=t("ready");
    renderLooks();renderScenes();cover();
    if(project&&project.video)showVideo(project.video);
  }
  function field(label, value, onChange, choices=null, kind="text") {
    const wrapper=node("label");wrapper.append(node("span",label));
    const input=node(choices?"select":kind==="textarea"?"textarea":"input");
    if(choices)choices.forEach(([value,label])=>input.append(option(value,label)));
    else if(kind!=="textarea")input.type=kind;
    if(kind==="number"){input.min="0.5";input.max="600";input.step="any";input.required=true;}
    input.value=value;input.addEventListener("input",()=>onChange(kind==="number"?Number(input.value):input.value));wrapper.append(input);return wrapper;
  }
  function renderScenes() {
    if(!story)return;$("scenes").replaceChildren();
    story.scenes.forEach((scene,i)=>{
      const card=node("article",undefined,"scene-card");const top=node("div",undefined,"scene-top");top.append(node("strong",`${t("scene")} ${i+1}`));
      const controls=node("div");
      for(const [symbol,offset] of [["↑",-1],["↓",1]]){
        const button=node("button",symbol);button.type="button";button.disabled=i+offset<0||i+offset>=story.scenes.length;button.setAttribute("aria-label",`${t("scene")} ${i+1} ${symbol}`);
        button.addEventListener("click",()=>{[story.scenes[i],story.scenes[i+offset]]=[story.scenes[i+offset],story.scenes[i]];renderScenes();});controls.append(button);
      }
      const remove=node("button","×");remove.type="button";remove.disabled=story.scenes.length===1;remove.setAttribute("aria-label",`${t("remove")} ${t("scene")} ${i+1}`);
      remove.addEventListener("click",()=>{story.scenes.splice(i,1);syncDuration();renderScenes();});controls.append(remove);top.append(controls);card.append(top);
      card.append(field(t("look"),scene.preset,value=>{scene.preset=value;},Object.keys(state.presets).map(key=>[key,lookName(key)])));
      card.append(field(t("title"),scene.title||"",value=>{scene.title=value;}));
      card.append(field(t("caption"),scene.subtitle||"",value=>{scene.subtitle=value;if(i===0){$("subtitle").value=value;cover();}},null,"textarea"));
      const row=node("div",undefined,"two-fields");row.append(field(t("duration"),Number(scene.duration_s.toFixed(3)),value=>{scene.duration_s=value;syncDuration();},null,"number"));
      row.append(field(t("camera"),scene.camera||"wide",value=>{scene.camera=value;},["wide","drift","close"].map(key=>[key,t(key)])));card.append(row);
      if($("renderer").value==="blender") {
        const blend=node("details");blend.append(node("summary",t("blendFile")),node("p",t("blendHelp"),"hint"));
        const data=()=>scene.blender||(scene.blender={});
        blend.append(field(t("blendFile"),scene.blender?.file||"",value=>{data().file=value;}));
        blend.append(field(t("blendCamera"),scene.blender?.camera||"",value=>{data().camera=value;}));
        card.append(blend);
      }
      const voiceDetails=node("details");voiceDetails.append(node("summary",t("voiceTitle")));
      voiceDetails.append(node("p",t("voiceHelp"),"hint"));
      const narration=()=>scene.narration||(scene.narration={language:language==="zh"?"Chinese":"English"});
      voiceDetails.append(field(t("voiceText"),scene.narration?.text||"",value=>{narration().text=value;},null,"textarea"));
      voiceDetails.append(field(t("voice"),scene.narration?.voice||"Serena",value=>{narration().voice=value;},["Serena","Dylan","Vivian","Uncle_Fu","Eric","Ryan","Aiden","Ono_Anna","Sohee"].map(v=>[v,v.replaceAll("_"," ")])));
      voiceDetails.append(field(t("voiceLanguage"),scene.narration?.language||(language==="zh"?"Chinese":"English"),value=>{narration().language=value;},[["Chinese","中文"],["English","English"],["Japanese","日本語"],["Korean","한국어"],["French","Français"],["German","Deutsch"],["Spanish","Español"],["Italian","Italiano"],["Portuguese","Português"],["Russian","Русский"]]));
      voiceDetails.append(field(t("direction"),scene.narration?.direction||"",value=>{narration().direction=value;},null,"textarea"));
      card.append(voiceDetails);$("scenes").append(card);
    });
  }
  function syncDuration() {$("duration").value=Number(story.scenes.reduce((sum,s)=>sum+s.duration_s,0).toFixed(3));}
  function showVideo(url) {
    $("video").src=url;$("video").hidden=false;$("poster").hidden=true;$("cover-copy").hidden=true;
    $("download").href=url;$("download").hidden=false;
  }
  async function request(url, options={}) {
    const response=await fetch(url,options);const data=await response.json();
    if(!response.ok)throw new Error(data.error||response.statusText);return data;
  }
  function setBusy(value) {busy=value;$("controls").disabled=value;$("language").disabled=value;$("film-id").readOnly=existing;$("accent").disabled=!$("custom-accent").checked;}
  function updateJob(job) {
    $("log-panel").hidden=false;$("log").textContent=job.log.join("\n");
    const line=job.log.filter(line=>line.startsWith("Picture ")).at(-1);
    const match=line&&line.match(/Picture (\d+)%/);
    let progress=match?10+Number(match[1])*0.65:7;
    if(job.log.some(line=>line.startsWith("Sound:")))progress=86;
    if(job.status==="done")progress=100;
    $("progress-fill").style.width=`${progress}%`;document.querySelector(".progress").hidden=false;
    $("status").textContent=job.status==="done"?t(job.preview?"previewDone":"done"):job.status==="error"?t("failed"):t("working");
    if(job.status==="done"){showVideo(job.video);existing=true;$("projects").value=job.id;}
    if(job.status!=="running")setBusy(false);
  }
  async function render(preview) {
    if(busy||!$("editor").reportValidity())return;
    setBusy(true);$("download").hidden=true;$("status").textContent=t("working");document.querySelector(".progress").hidden=false;$("progress-fill").style.width="3%";
    try {
      await request("/api/render",{method:"POST",headers:{"Content-Type":"application/json","X-CodeCinema-Token":state.token},body:JSON.stringify({id:$("film-id").value,existing,story,renderer:$("renderer").value,format:$("format").value,quality:$("quality").value,preview})});
      while(true){state=await request("/api/state");refreshProjects();updateJob(state.job);if(state.job.status!=="running")break;await new Promise(resolve=>setTimeout(resolve,700));}
    }catch(error){$("status").textContent=error.message;setBusy(false);}
  }
  $("language").addEventListener("click",()=>{language=language==="zh"?"en":"zh";translate();cover();});
  $("renderer").addEventListener("change",renderScenes);
  $("projects").addEventListener("change",()=>loadProject($("projects").value));
  $("title").addEventListener("input",()=>{const old=story.title;story.title=$("title").value;story.scenes.forEach(scene=>{if(scene.title===old)scene.title=story.title;});cover();renderScenes();});
  $("subtitle").addEventListener("input",()=>{story.scenes[0].subtitle=$("subtitle").value;cover();renderScenes();});
  $("duration").addEventListener("change",()=>{const sum=story.scenes.reduce((sum,s)=>sum+s.duration_s,0),total=Number($("duration").value);if(sum>0&&total>0){story.scenes.forEach(scene=>scene.duration_s*=total/sum);renderScenes();}});
  function applyAccent(){story.scenes.forEach(scene=>{if($("custom-accent").checked)scene.accent=$("accent").value;else delete scene.accent;});$("accent").disabled=!$("custom-accent").checked;}
  $("accent").addEventListener("input",applyAccent);$("custom-accent").addEventListener("change",applyAccent);
  $("add-scene").addEventListener("click",()=>{story.scenes.push({name:`Scene ${story.scenes.length+1}`,preset:selected,duration_s:4,camera:"drift",title:"",subtitle:captionsFor(selected)[1]});syncDuration();renderScenes();});
  $("editor").addEventListener("submit",event=>{event.preventDefault();render(false);});$("preview").addEventListener("click",()=>render(true));
  translate();
  request("/api/state").then(data=>{state=data;$("renderer").replaceChildren(...Object.entries(state.renderers).map(([key,value])=>option(key,value.title)));if(state.problems.length){$("setup").hidden=false;$("setup").textContent=state.problems.join("\n");}refreshProjects();loadProject("");if(state.job&&state.job.status==="running"){$("projects").value=state.job.id;loadProject(state.job.id);setBusy(true);(async()=>{while(busy){state=await request("/api/state");updateJob(state.job);await new Promise(resolve=>setTimeout(resolve,700));}})();}}).catch(error=>{$("setup").hidden=false;$("setup").textContent=error.message;});
})();
