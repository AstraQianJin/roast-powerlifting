#!/usr/bin/env node
// uiv.js —— App 全量 UI 遍历（v0.10 全量 UI 测试）
//
// 与另两套前端回归的分工：
//   v3v.js       钉「函数算得对不对 + 关键按钮点下去有没有反应」（单视口、按域断言）
//   check_hud.js 钉「顶栏在四档宽度不重叠不裁切」（只量头部，一个面板都不开）
//   uiv.js       钉「每个面板在每一档宽度都长得出去」——全量 .sheet × 4 档逐个开、量、关，
//                再加设置页全部真实入口的点击链、返回键收口、语言/主题/计时器/READONLY 阻断层、
//                动作选择链的真点（B 段）、把结构撑到契约上限后的整屏遍历（N 段），
//                最后断言这一整轮遍历没把账本、动作库、归档分片改过一个字。
//
// 判据是几何而不是截图 diff：越界 / 面板横向内容溢出 / 整页横向溢出 / 文本裁切 /
// 同级可点元素互叠。这四类正是历次真机与窄屏踩过的坑（v0.03 顶栏重叠、v0.09 归档行挤压），
// 用像素图会随字体渲染漂，用几何不会。
//
//   node tools/uiv.js
const { spawn } = require('child_process');
const path = require('path');
const os = require('os');
const tmpclean = require('./tmpclean');

const HERE = __dirname;
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const FILE = 'file:///' + path.resolve(HERE, '../app/src/main/assets/index.html').replace(/\\/g, '/');
const PORT = 9860 + Math.floor(Math.random() * 25);
const HEIGHT = 892;
const WIDTHS = [320, 360, 390, 412];

/* PANELS 就是 closeAllSheets 的名单（A0 段两头对账，少一个就说明名单漂了；
   条数不写在注释或断言里，由 PANELS.length 自己说）。
   open 给「函数名 + 参数」而不是字符串：顶层 function 声明挂在 window 上，
   页面侧 window[name] 取得到，探针因此完全不需要 eval，也就避开了
   「正则写在模板串里反斜杠被吞」那一类坑（见 README §6 第 16 条）。 */
const PANELS = [
  { id: 'setSheet', open: 'openSettings', args: [] },
  { id: 'edSheet', open: 'openEditor', args: [0] },
  { id: 'profSheet', open: 'openProfile', args: [] },
  { id: 'structSheet', open: 'openStructSheet', args: [] },
  { id: 'jtsSheet', open: 'openJtsSheet', args: [] },
  { id: 'teleSheet', open: 'openTeleSheet', args: [] },
  { id: 'aboutSheet', open: 'openAboutSheet', args: [] },
  { id: 'postSheet', open: 'openPoster', args: [] },
  { id: 'archSheet', open: 'openArchiveSheet', args: [] },
  { id: 'figsSheet', open: 'openFigsSheet', args: [] },
  { id: 'chartSheet', open: 'openChartHub', args: [] },
  { id: 'trendSheet', open: 'openTrendSheet', args: [] },
  { id: 'catVolSheet', open: 'openCatVolSheet', args: [] },
  { id: 'logSheet', open: 'openLogSheet', args: [] },
  { id: 'adviceSheet', open: 'openAdviceSheet', args: [] },
  { id: 'calibSheet', open: 'openCalibSheet', args: [] },
  { id: 'toolLoadSheet', open: 'openToolLoad', args: [] },
  { id: 'toolRmSheet', open: 'openToolRm', args: [] },
  { id: 'toolCoefSheet', open: 'openToolCoef', args: [] },
  { id: 'progLibSheet', open: 'openProgLibSheet', args: [] },
  { id: 'stratLibSheet', open: 'openStratLibSheet', args: [] },
  { id: 'brSheet', open: 'openBrowse', args: ['manage'] },
  { id: 'catSheet', open: 'openCat', args: [null, null] },
  { id: 'actSheet', open: 'openAct', args: [null] },
  { id: 'envSheet', open: 'openEnvSheet', args: [] },
  { id: 'kitSheet', open: 'openKitSheet', args: [] },
  { id: 'sciSheet', open: 'openSciSheet', args: [] },
  { id: 'ioSheet', open: 'openIoSheet', args: [] },
  { id: 'advSetSheet', open: 'openAdvSetSheet', args: [] },
];
/* 真实入口的点击链：点下去必须打开指定面板，且入口所在的面板留在栈底（返回可回上一页）。
   这条链过去只有归档一个被真点过，其余入口的 onclick 目标写错、函数改名都无人知
   （浏览器里点了没反应是静默故障）。
   host = 按钮长在哪个面板里，默认设置页；图表 hub 的四条视图入口长在 chartSheet 上，
   不写 host 就等于「在隐藏面板里点一个看不见按钮」——那是假点击链，测不到 onclick。 */
const ENTRIES = [
  { btn: 'logoBtn', want: 'setSheet' },
  { btn: 'setProfGo', want: 'profSheet' },
  { btn: 'setStructGo', want: 'structSheet' },
  { btn: 'setJtsGo', want: 'jtsSheet' },
  { btn: 'setArchGo', want: 'archSheet' },
  { btn: 'setProgLibGo', want: 'progLibSheet' },
  { btn: 'setStratLibGo', want: 'stratLibSheet' },
  { btn: 'setFigsGo', want: 'chartSheet' },
  { btn: 'setAdvGo', want: 'adviceSheet' },
  { btn: 'chartFigsGo', want: 'figsSheet', host: 'chartSheet' },
  { btn: 'chartTrendGo', want: 'trendSheet', host: 'chartSheet' },
  { btn: 'chartCatGo', want: 'catVolSheet', host: 'chartSheet' },
  { btn: 'chartLogGo', want: 'logSheet', host: 'chartSheet' },
  { btn: 'chartCalibGo', want: 'calibSheet', host: 'chartSheet' },
  { btn: 'setEnvGo', want: 'envSheet' },
  { btn: 'setKitGo', want: 'kitSheet' },
  { btn: 'setSciGo', want: 'sciSheet' },
  { btn: 'setIOGo', want: 'ioSheet' },
  { btn: 'setAdvSetGo', want: 'advSetSheet' },
  { btn: 'setLibGo', want: 'brSheet' },
  { btn: 'setAboutGo', want: 'aboutSheet' },
];
const FN_NEEDED = ['openSettings', 'openEditor', 'openProfile', 'openStructSheet', 'openJtsSheet',
  'openTeleSheet', 'openAboutSheet', 'openPoster', 'openArchiveSheet', 'openProgLibSheet',
  'openStratLibSheet', 'openFigsSheet', 'openChartHub', 'openTrendSheet', 'openCatVolSheet', 'openLogSheet', 'openAdviceSheet',
  'openEnvSheet', 'openSciSheet', 'openIoSheet', 'openKitSheet', 'renderKitPhoto', 'kitPhotoPick', 'renderFigs', 'openBrowse', 'openCat', 'openAct', 'closeAllSheets', 'showSheet',
  'closeSheet', 'renderBootFail', 'startTimer', 'stopTimer', '__handleBack', 'setLang', 'cycleTheme',
  'setTheme', 'applyTheme', 'paintThemeUI', 'themeId',
  'flashCard', 'pingDayComplete', 'edChain', 'toast', 'toggleDone', 'flushSave',
  'openAdviceSheet', 'setAdvTier', 'onAdvWeekChange', 'advApplyRow', 'advApplyAll', 'advUndo', 'advUndoLast',
  'advPaintTools', 'advPaintAudit', 'fillAdviceTier',
  /* v0.26 环境配置与本地计算器：L 段真的点这些控件，名字漂了就是「点了个不存在的开关」 */
  'renderEnvSheet', 'renderEnvLoc', 'saveDayLoc', 'dayLoc', 'activeWeekNums',
  'plateStock', 'plateOn', 'togglePlateKg', 'lcPickType', 'renderLoadCalc',
  'readLoadCalc', 'openToolLoad', 'runToolRm', 'openToolRm', 'runToolCoef', 'openToolCoef',
  'applyToolsFold', 'toggleToolsFold', 'rankIconHtml', 'calcGlRank', 'lcTotal', 'lcReset', 'exportUnifiedCsv', 'xStateToPlanDict',
  /* v0.27 阈值回测：E 段真点 chartCalibGo，名字漂了就是一层打不开的面板 */
  'openCalibSheet', 'renderCalib', 'calibSweep', 'withAutoreg',
  /* v0.29 B 段真点动作选择链：这几个名字只在 JS 拼串的 onclick 里出现，
     改名后探针会直接 ReferenceError 炸掉整轮，所以先点名 */
  'openBrowse', 'renderBrowse', 'brGo', 'brUp', 'brSearch', 'brSearchHits', 'pickAct'];

/* 装进页面的一次性量具。整段字符串里不许出现反斜杠转义：它是模板串，
   `\s` 会被吞成 `s`、`\d` 会被吞成 `d`，所以这里一律用 replace(' ','') 式的写法。 */
const HELP = `(function(){
  var SEL='button,input,select,textarea,label,a,.pill,.dock-btn,.ico-btn,.sc-btn,.done-btn,.set-row,.dbtn';
  function vis(e){
    var r=e.getBoundingClientRect();
    if(r.width<1||r.height<1) return false;
    var cs=getComputedStyle(e);
    if(cs.visibility==='hidden'||cs.display==='none'||parseFloat(cs.opacity)<0.05) return false;
    return !!e.offsetParent||cs.position==='fixed';
  }
  function name(e){
    var parts=[];
    if(e.id) parts.push('#'+e.id);
    var c=e.getAttribute&&e.getAttribute('class');
    if(c){ var arr=c.split(' '),k; for(k=0;k<arr.length&&parts.length<3;k++){ if(arr[k]) parts.push('.'+arr[k]); } }
    return e.tagName.toLowerCase()+parts.join('');
  }
  function flat(s){ return s.replace(/ +/g,' ').trim(); }
  function djb2(s){ var h=5381,i; for(i=0;i<s.length;i++){ h=((h<<5)+h+s.charCodeAt(i))|0; } return h>>>0; }
  window.__uiv={
    call:function(n,a){ var f=window[n]; if(typeof f!=='function') throw new Error('页面没有函数 '+n); f.apply(null,a||[]); return n; },
    click:function(nid){ var e=document.getElementById(nid); if(!e) throw new Error('没有节点 #'+nid); e.click(); return nid; },
    anyOpen:function(){ return !!document.querySelector('.sheet.on'); },
    /* 入场动效是真的动画：量几何之前必须等它落地，否则读到的是中间帧（translateY 会让
       .down 面板下沿暂时越出视口）。只数「有限次」的动画——无限循环的那批（计时脉冲）
       永远不结束，等它就等于死循环；取不到 getAnimations 就当作没有，让调用方按超时兜底。 */
    animBusy:function(){
      if(!document.getAnimations) return '0';
      var a=document.getAnimations(),n=0,i,t;
      for(i=0;i<a.length;i++){
        t=(a[i].effect && a[i].effect.getTiming)?a[i].effect.getTiming():{};
        if(t.iterations===Infinity) continue;
        if(a[i].playState==='finished'||a[i].playState==='idle') continue;
        n++;
      }
      return String(n);
    },
    animNames:function(id){
      var el=document.querySelector('#'+id+'.sheet.on .panel');
      if(!el) return '(no panel for '+id+')';
      var cs=getComputedStyle(el),cls=String(el.parentNode.className||'');
      var kind=cls.indexOf('mid')>=0?'mid':(cls.indexOf('down')>=0?'down':'?');
      return id+':'+kind+':'+(cs.animationName||'none')+' '+cs.animationDuration+' '+cs.animationTimingFunction;
    },
    motionTokens:function(){
      /* 名单从 :root 块里现读，不在探针里另抄一份：加一条令牌不必改这里，
         少一条也不会「查了个不存在的名字」装成查过。取到几个就报几个，前缀带数量。 */
      var cs=getComputedStyle(document.documentElement),out=[],i;
      var css=String(document.querySelector('style')?document.querySelector('style').textContent:'');
      var a=css.indexOf(':root{'), b=a<0?-1:css.indexOf('}', a);
      if(a<0||b<0) return '(no :root)';
      var body=css.slice(a,b), re=new RegExp('(--(?:dur|ease)-[a-z0-9-]+):','g'), m, ks=[];
      while((m=re.exec(body))){ if(ks.indexOf(m[1])<0) ks.push(m[1]); }
      for(i=0;i<ks.length;i++){ var v=cs.getPropertyValue(ks[i]); out.push(ks[i]+'='+(v?v.trim():'(空)')); }
      return ks.length+'|'+out.join(' ');
    },
    reducedMotionCss:function(){
      var st=document.querySelector('style'),css=st?String(st.textContent):'';
      var i=css.indexOf('@media (prefers-reduced-motion');
      if(i<0) return '(absent)';
      var seg=css.slice(i, css.indexOf('@keyframes', i)>i?Math.min(css.length, css.indexOf('}', css.indexOf('*', i))+1):i+260);
      return seg.replace(/ +/g,' ').trim().slice(0,120);
    },
    focusFrom:function(id){
      var el=document.getElementById(id);
      if(!el) return '(no input)';
      el.focus();
      var ev=null;
      try{ ev=new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}); }catch(e){ return '(no KeyboardEvent)'; }
      el.dispatchEvent(ev);
      var a=document.activeElement;
      return (a&&a.id)?a.id:((a&&a.tagName)?a.tagName.toLowerCase():'(none)');
    },
    enterHints:function(){
      var ids=['edLoad','edReps','edRpe','edNotes'],out=[],i;
      for(i=0;i<ids.length;i++){ var e=document.getElementById(ids[i]);
        out.push(ids[i]+':'+(e?(e.getAttribute('enterkeyhint')||'(缺)'):'(无节点)')); }
      return out.join(' ');
    },
    snap:function(){ return JSON.stringify(state); },
    restore:function(txt){ state = JSON.parse(txt); flushSave(); return JSON.stringify(state)===txt?'1':'0'; },
    flashCardCheck:function(i){
      var box=document.getElementById('exList');
      var card=box?box.children[i]:null;
      if(!card) return '(no card)';
      var before=card.getBoundingClientRect().width;
      var ok=flashCard(i);
      var during=card.classList.contains('just');
      var after=card.getBoundingClientRect().width;
      return JSON.stringify({called:ok,cls:during,wStable:Math.abs(before-after)<0.5,
        anim:(getComputedStyle(card).animationName||'none')});
    },
    openIds:function(){ var o=[],n=document.querySelectorAll('.sheet.on'),i; for(i=0;i<n.length;i++) o.push(n[i].id); return o.join(','); },
    storeHash:function(){
      var keys=Object.keys(LS_BY_KIND),out=[],i;
      for(i=0;i<keys.length;i++){ var k=LS_BY_KIND[keys[i]],v=localStorage.getItem(k); if(v===null) v='(absent)'; out.push(keys[i]+':'+v.length+':'+djb2(v)); }
      return out.sort().join('|');
    },
    ledgerHash:function(){ return djb2(JSON.stringify({w:state.weeks,s:state.structure,j:state.jts,e:state.e1rmLog,a:state.aux,p:state.profile}))+' ('+JSON.stringify(state.weeks).length+'B)'; },
    missingFns:function(list){ var o=[],i; for(i=0;i<list.length;i++){ if(typeof window[list[i]]!=='function') o.push(list[i]); } return o.join(','); },
    closeList:function(){ var m=(String(closeAllSheets).match(/'[A-Za-z]+Sheet'/g)||[]),i; for(i=0;i<m.length;i++) m[i]=m[i].slice(1,-1); return m.join(','); },
    lang:function(){ return document.documentElement.lang+'|'+state.lang; },
    theme:function(){ var r=document.documentElement;
      return (state.theme||'')+'|'+(r.getAttribute('data-theme')||'')+'|'+(r.getAttribute('data-mode')||''); },
    /* 选择器的形状只能按注册表判：写死「两个按钮」的断言在第三档加进来那天就会静默少测一档 */
    segInfo:function(id){ var seg=document.getElementById(id||'themeSeg');
      if(!seg) return '{"noseg":1}';
      var b=seg.querySelectorAll('button'),on=0,i,ids=[],w=[],h=0,l=[];
      for(i=0;i<b.length;i++){ if(b[i].classList.contains('on')) on++;
        ids.push(b[i].id); var rr=b[i].getBoundingClientRect(); w.push(Math.round(rr.width));
        l.push(Math.round(rr.left));
        if(rr.height>h) h=Math.round(rr.height); }
      /* 滑块真实落在哪一格只能量像素：段数/格位是写进 --seg-n / --seg-i 的，
         算错了 CSS 不报错，只是滑块跟按钮错开半个格。 */
      var th=seg.querySelector('.thumb'),tr=null;
      if(th){ var q=th.getBoundingClientRect();
        tr={l:Math.round(q.left),w:Math.round(q.width)}; }
      return JSON.stringify({n:b.length,on:on,ids:ids,w:w,l:l,h:h,
        sn:Number(seg.style.getPropertyValue('--seg-n')),
        si:Number(seg.style.getPropertyValue('--seg-i')),
        thumb:!!th,th:tr,tw:Math.round(seg.getBoundingClientRect().width)}); },
    bootFail:function(show,theme){
      var old=document.getElementById('bootFail'); if(old) old.remove();
      if(!show){ bootFatal=null; return 0; }
      bootFatal={reason:'parse',text:'uiv 注入的假故障',raw:'{}',theme:theme||'dark',parsed:null};
      renderBootFail();
      var b=document.getElementById('bootFail');
      return b?b.querySelectorAll('button').length:0;
    },
    timerState:function(sec,mode){
      startTimer(sec,mode);
      var bar=document.getElementById('timerBar'), on=bar.classList.contains('on');
      var dg=(document.getElementById('tDigits').textContent||'');
      stopTimer();
      var off=!bar.classList.contains('on');
      return JSON.stringify({on:on, off:off, digits:dj2(dg), running:(typeof timerId!=='undefined'&&timerId!==null)});
    },
    /* 真点档钮（走 markup 的 onclick，不是替它调 startTimer）：量「按钮上写的数」
       与「它实际启动的倒计时」与「state.timerCfg 那格」三者对不对得上。
       标签抄在文案里时，改 cfg 不会跟着改 —— 只有点一下才看得见。 */
    chipTap:function(t){
      var b=document.getElementById('chip'+t); if(!b) return '{"nochip":1}';
      var lab=(b.textContent||'').trim();
      b.click();
      var dg=(document.getElementById('tDigits').textContent||'').trim();
      var bar=document.getElementById('timerBar');
      var shown=!!(bar&&bar.classList.contains('on'));
      stopTimer();
      return JSON.stringify({lab:lab,digits:dg,shown:shown,cfg:state.timerCfg[t]});
    },
    /* HUD 圆点是「必须写内联色」的部件，色只能从 TIER_TOKEN 指向的主题令牌来。
       写死十六进制的后果只有在换主题那天才看得见，所以逐档主题各量一次。 */
    tierDots:function(){
      var root=document.documentElement, dot=document.getElementById('tDot');
      var ids=(window.THEME_IDS||[]), tokMap=window.TIER_TOKEN||{}, back=state.theme;
      var probe=document.createElement('span'); probe.style.display='none'; root.appendChild(probe);
      var out=[], i;
      for(i=0;i<ids.length;i++){
        setTheme(ids[i]);
        ['T1','T2','T3'].forEach(function(tier){
          var tok=String(tokMap[tier]||'');
          var raw=tok?String(getComputedStyle(root).getPropertyValue(tok)).trim():'';
          probe.style.color=tok?'var('+tok+')':'red';
          var want=getComputedStyle(probe).color;
          startTimer(30,tier);
          var got=dot?getComputedStyle(dot).backgroundColor:'(无圆点)';
          stopTimer();
          out.push(ids[i]+'/'+tier+' tok='+(tok||'(缺)')+' 令牌='+(raw||'(缺值)')+' 实色='+want+' 圆点='+got
            +((tok&&raw&&want===got)?' ok':' MISMATCH'));
        });
      }
      probe.remove(); setTheme(back);
      return out.join(' ; ');
    },
    /* 「换到纸底主题就看不见字」这件事只有在纸底主题才看得见，而它不报错、不塌版 ——
       几何类判据全绿，色板却整片留在暗色那套值上。所以逐主题真算一遍对比度：
       半透明底（--tX-soft / --warn-soft）先按 alpha 叠到卡底上再算，
       否则「13% 的红」会被当成接近透明而误判。判据是 WCAG 相对亮度比，不是色号相等。 */
    contrast:function(){
      var root=document.documentElement, back=state.theme, out=[], i;
      /* 整段在 HELP 模板串里，反斜杠会被吞（\d 变 d、\( 变 (），所以这里一律不用转义：
         按 # / ( / , / ) 这些字符切，切完用 isNaN 兜住 —— 量不出色必须报，
         不能让 NaN 走进比较式（NaN<3 是 false，那会让整条判据静默恒真）。 */
      function parse(v){ v=String(v).trim();
        if(v.charAt(0)==='#'){ var t=v.slice(1);
          if(t.length===3) t=t.replace(/./g,function(c){ return c+c; });
          if(t.length!==6) return null;
          var hc=[0,2,4].map(function(k){ return parseInt(t.substr(k,2),16); });
          return isNaN(hc[0]+hc[1]+hc[2])?null:{c:hc,a:1}; }
        var o=v.indexOf('('); if(o<0) return null;
        var body=v.slice(o+1); var e=body.indexOf(')'); if(e>=0) body=body.slice(0,e);
        var p=body.split('/').join(',').split(',');
        var c=[0,1,2].map(function(k){ var s=String(p[k]===undefined?'':p[k]).split(' ').join('');
          return s.charAt(s.length-1)==='%'?Number(s.slice(0,-1))*2.55:Number(s); });
        if(isNaN(c[0]+c[1]+c[2])) return null;
        var a=p.length>=4?Number(String(p[3]).split(' ').join('')):1;
        return {c:c,a:isNaN(a)?1:a}; }
      function lum(c){ var f=function(x){ x=x/255; return x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4); };
        return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2]); }
      function over(fg,bg){ var p=parse(fg); if(!p) return bg;
        return [0,1,2].map(function(k){ return p.c[k]*p.a+bg[k]*(1-p.a); }); }
      function tok(n){ return String(getComputedStyle(root).getPropertyValue(n)).trim(); }
      function ratio(fg,bgc){ var p=parse(fg); if(!p) return -1;
        if(isNaN(bgc[0]+bgc[1]+bgc[2])) return -1;
        var c=[0,1,2].map(function(k){ return p.c[k]*p.a+bgc[k]*(1-p.a); });
        if(isNaN(c[0]+c[1]+c[2])) return -1;
        var a=lum(c),b=lum(bgc); if(isNaN(a+b)) return -1;
        var hi=Math.max(a,b),lo=Math.min(a,b);
        return (hi+0.05)/(lo+0.05); }
      /* 成对表：[文字令牌, 由外到内的底色令牌…，本检查要盯的旧手抄值]。
         底色逐层按 alpha 叠：13% 的档位浅底要先叠到卡底上再算，不然会当成透明而误判。 */
      var PAIRS=[['--on-accent',['--t1'],['#fff']],['--on-accent',['--t1-deep'],['#fff']],
                 ['--on-accent',['--t2'],['#fff']],['--on-accent',['--t3'],['#fff']],
                 ['--on-accent',['--dl'],['#fff']],['--on-accent',['--dl-deep'],['#fff']],
                 ['--on-rts',['--rts'],['#1A1200']],['--on-rts',['--rts-deep'],['#1A1200']],
                 ['--on-gold',['--gold'],['#1A1200']],
                 ['--t1-ink',['--card-a','--t1-soft'],['#FF9C98']],
                 ['--t2-ink',['--card-a','--t2-soft'],['#9CCBFF']],
                 ['--t3-ink',['--card-a','--t3-soft'],['#9BE4A5']],
                 ['--warn',['--card-a'],['#F0C060']],
                 ['--warn',['--card-a','--warn-soft'],['#F0C060']],
                 ['--danger-fg',['--card-a'],['#E53935']]];
      var minR=99, minAt='';
      for(i=0;i<(window.THEME_IDS||[]).length;i++){
        var tid=window.THEME_IDS[i]; setTheme(tid);
        var base=parse(getComputedStyle(document.body).backgroundColor);
        if(!base){ out.push(tid+' 页面底色取不到（不是 rgb 写法）'); continue; }
        PAIRS.forEach(function(p){
          if(!tok(p[0])){ out.push(tid+'/'+p[0]+' 令牌没值'); return; }
          var bg=base.c.slice();
          p[1].forEach(function(bt){ bg=over(tok(bt),bg); });
          var r=ratio(tok(p[0]),bg);
          if(r<0){ out.push(tid+' '+p[0]+' 写法量不出色值：'+tok(p[0])); return; }
          if(r<minR){ minR=r; minAt=tid+' '+p[0]+'@'+p[1].join('+'); }
          if(r<3) out.push(tid+' '+p[0]+'@'+p[1][p[1].length-1]+' 对比 '+r.toFixed(2)
            +'（旧手抄 '+p[2]+'，令牌化后必须跟着主题走）');
        });
      }
      setTheme(back);
      return JSON.stringify({bad:out,pairs:PAIRS.length,themes:(window.THEME_IDS||[]).length,
        min:minR.toFixed(2),minAt:minAt});
    },
    /* 动作选择链（B 段）的四个探针：都走「真点/真输入」，不直呼 openBrowse、brGo、pickAct。
       加练钮与 mv-btn 都没有 id（markup 里的 class），所以按选择器取节点后 .click()；
       列表行是 renderBrowse 拼出来的，按 #brBody .br-row 的下标取。 */
    addTap:function(){
      var on=function(x){ var e=document.getElementById(x); return e&&e.classList.contains('on')?1:0; };
      var b=document.querySelector('button.add');
      if(!b) return JSON.stringify({noAdd:1});
      var n0=(day().exercises||[]).length;
      b.click();
      return JSON.stringify({noAdd:0,n0:n0,n1:(day().exercises||[]).length,
        ed:on('edSheet'),br:on('brSheet'),lvl:BR.level,mode:BR.mode,q:BR.q,
        rows:document.querySelectorAll('#brBody .br-row').length,
        name:flat(document.getElementById('edMvName').textContent||''),
        path:flat(document.getElementById('edMvPath').textContent||''),
        ttl:flat(document.getElementById('brTitle').textContent||''),
        addH:Math.round(b.getBoundingClientRect().height)});
    },
    mvTap:function(){
      var on=function(x){ var e=document.getElementById(x); return e&&e.classList.contains('on')?1:0; };
      var b=document.querySelector('#edSheet .mv-btn');
      if(!b) return JSON.stringify({noBtn:1});
      b.click();
      return JSON.stringify({noBtn:0,br:on('brSheet'),ed:on('edSheet'),act:on('actSheet'),
        ttl:flat(document.getElementById('brTitle').textContent||''),
        rows:document.querySelectorAll('#brBody .br-row').length,
        lvl:BR.level,mode:BR.mode,q:BR.q,
        backOff:document.getElementById('brBack').classList.contains('off')?1:0,
        btnH:Math.round(b.getBoundingClientRect().height)});
    },
    brTap:function(i){
      var on=function(x){ var e=document.getElementById(x); return e&&e.classList.contains('on')?1:0; };
      var r0=document.querySelectorAll('#brBody .br-row');
      var n=r0.length, got=i<n?1:0;
      var nm=document.getElementById('edMvName'), pt=document.getElementById('edMvPath');
      var cur=flat(nm?nm.textContent:'');
      /* 点之前先记下这一行自己写的名字：点完它该原样出现在编辑器的两个标签上。
         pickAct(分类,动作) 的参数顺序一旦颠倒，落进标签的就不是被点的那一行。
         otherIdx 是「与当前标签不同名的那一行」的下标：选它才保证账真的动了。 */
      var lab=got?(function(){ var x=r0[i].querySelector('.bmain b'); return flat(x?x.textContent:''); })():'';
      /* 点之前量这一行自己有多高：它就是用户拇指落上去的那块热区。
         点完 r0 整批脱离文档，getBoundingClientRect 只会恒报 0。 */
      var rh=got?Math.round(r0[i].getBoundingClientRect().height):0;
      var oi=-1,k;
      for(k=0;k<n;k++){ var t=flat((r0[k].querySelector('.bmain b')||{textContent:''}).textContent);
        if(t && t!==cur){ oi=k; break; } }
      if(got) r0[i].click();
      /* 点完 renderBrowse 重画过，旧 NodeList 已脱离文档：下面一律重新取 */
      var r1=document.querySelectorAll('#brBody .br-row');
      var b=document.querySelector('#edSheet .mv-btn');
      var pk=-1,k2;
      for(k2=0;k2<r1.length;k2++){ if(r1[k2].classList.contains('picked')) pk=k2; }
      return JSON.stringify({n:n,got:got,lab:lab,other:oi,br:on('brSheet'),ed:on('edSheet'),act:on('actSheet'),
        lvl:BR.level,dom:BR.dom,cat:BR.cat,q:BR.q,mode:BR.mode,
        rows:r1.length,
        crumb:document.querySelectorAll('#brCrumb button').length,
        cur:document.querySelectorAll('#brCrumb button.cur').length,
        pickN:document.querySelectorAll('#brBody .br-row.picked').length,pickAt:pk,
        meta:flat(document.getElementById('brMeta').textContent||''),
        empty:document.querySelector('#brBody .br-empty')?1:0,
        backOff:document.getElementById('brBack').classList.contains('off')?1:0,
        rowH:rh,
        mvName:flat(nm?nm.textContent:''),mvPath:flat(pt?pt.textContent:''),
        title:flat(document.getElementById('edTitle').textContent||''),
        btnH:b?Math.round(b.getBoundingClientRect().height):0});
    },
    brType:function(v){
      var e=document.getElementById('brQ');
      if(!e) return JSON.stringify({noIn:1});
      e.value=v; e.dispatchEvent(new Event('input'));
      return JSON.stringify({noIn:0,q:BR.q,lvl:BR.level,
        rows:document.querySelectorAll('#brBody .br-row').length,
        hits:(window.brSearchHits?brSearchHits().length:-1),
        empty:document.querySelector('#brBody .br-empty')?1:0,
        crumb:flat(document.getElementById('brCrumb').textContent||''),
        rowH:(function(){var x=document.querySelectorAll('#brBody .br-row');
          return x.length?Math.round(x[0].getBoundingClientRect().height):0;})()});
    },
    /* 极端结构（N 段）三枚探针。三个上限一律从契约现取：周与块走 planCapacity()，
       日数走 PLAN_SCHEMA.sheets.Days.max_rows，周期类型走 cycle_presets.items，
       块元数据（deloadMode / baseRpe 那份）从出厂块 clone —— 这一段不写死 52/16/6，
       契约哪天抬高上限，这段自己跟着长。都只回「有没有脏、脏在哪个节点」，
       不把整页文字搬过 CDP。 */
    extremeBuild:function(){
      /* PLAN_SCHEMA 是顶层 const，不挂 window，只能按裸名取（planCapacity 也这么取） */
      var sch=(typeof PLAN_SCHEMA!=='undefined'&&PLAN_SCHEMA)||{};
      var cap=planCapacity(), maxW=+cap.maxWeeks, maxB=+cap.maxBlocks;
      var spec=(sch.sheets||{}).Days||{};
      var maxD=+spec.max_rows;
      var pres=((sch.cycle_presets||{}).items)||[];
      if(!(maxW>0&&maxB>0&&maxD>0&&pres.length))
        return JSON.stringify({bad:'契约里读不到上限（周'+maxW+' 块'+maxB+' 日'+maxD+' 预设'+pres.length+'）'});
      var st=clone(state.structure);
      var proto=clone(((state.structure.blocks||[])[0])||{});
      var base=Math.floor(maxW/maxB), extra=maxW-base*maxB, blocks=[], b, w;
      for(b=0;b<maxB;b++){
        w=base+(b<extra?1:0); if(w<1) break;
        var bl=clone(proto), p=pres[b%pres.length];
        bl.id='B'+(b+1); bl.cycleType=p.id; bl.workMode=p.work_mode;
        bl.nameZh='压测块'+(b+1); bl.nameEn='STRESS '+(b+1);
        bl.workWeeks=Math.max(1,w-1); bl.deloadWeeks=(w>1?1:0);
        if(p.rpe_step) bl.rpeStep=p.rpe_step;
        blocks.push(bl);
      }
      st.totalWeeks=maxW; st.blocks=blocks;
      var d=st.dayDefs.slice(0);
      while(d.length<maxD){
        var last=d[d.length-1]||{constraints:{}}, L=String.fromCharCode(65+d.length);
        d.push({id:L, label:'DAY '+L, titleZh:'压测日'+L, titleEn:'STRESS DAY '+L,
          weekdayOffset:d.length%7, focusTags:clone(last.focusTags||[]),
          constraints:clone(last.constraints||{})});
      }
      st.dayDefs=d;
      state.structure=st; applyStructure(st);
      return JSON.stringify({maxW:maxW, maxB:maxB, maxD:maxD, pres:pres.length,
        blocks:st.blocks.length, timeline:compileTimeline(st).length,
        days:dayIds().length, dayIds:dayIds().join(''),
        weeks:Object.keys(state.weeks||{}).length});
    },
    extremeWalk:function(){
      var vis=function(){
        var c=document.body.cloneNode(true);
        var s=c.querySelectorAll('script,style,noscript'), i;
        for(i=0;i<s.length;i++) s[i].parentNode.removeChild(s[i]);
        return c.textContent||'';
      };
      var ids=dayIds(), total=+state.structure.totalWeeks||1;
      var ws=[1, Math.ceil(total/2), total], bad=[], prog=[], n=0;
      ws.forEach(function(w){ ids.forEach(function(d){
        /* 缺账本周片就先记一句人话再说：让它走到 renderAll 里炸成 TypeError，
           红是红了，但读的人只看到一串栈，看不出是「第 26 周根本没被补出来」 */
        if(!state.weeks[String(w)]){
          var miss='W' + w + ' 没有账本周片（补周没撑到上限）';
          if(bad.indexOf(miss) < 0) bad.push(miss);
          return;
        }
        state.week=w; state.day=d; renderAll(); n++;
        var hit=['NaN','undefined','Infinity'].filter(function(x){return vis().indexOf(x)>=0;});
        var ov=document.documentElement.scrollWidth-window.innerWidth;
        var on=document.querySelectorAll('.sheet.on').length;
        if(hit.length||ov>0||on)
          bad.push('W'+w+'/'+d+' 脏'+hit.join(',')+' 溢'+ov+' 叠'+on);
        prog.push((document.getElementById('dayProg')||{textContent:'?'}).textContent);
      });});
      state.week=1; state.day='A'; renderAll();
      return JSON.stringify({n:n, expect:ws.length*ids.length, weeks:ws.join(','), days:ids.join(''),
        bad:bad.length?bad.join(' / '):'无', prog:prog.join(' ')});
    },
    dirtyIn:function(id){
      var root=document.getElementById(id); if(!root) return JSON.stringify({noRoot:1});
      var words=['NaN','undefined','Infinity'], hit={}, all=root.querySelectorAll('*'), i, j;
      for(i=0;i<all.length;i++){
        var node=all[i];
        if(node.tagName==='SCRIPT'||node.tagName==='STYLE'||node.tagName==='NOSCRIPT') continue;
        var own='';
        for(j=0;j<node.childNodes.length;j++){
          if(node.childNodes[j].nodeType===3) own+=node.childNodes[j].nodeValue;
        }
        if(!own) continue;
        for(j=0;j<words.length;j++){
          if(own.indexOf(words[j])>=0){
            var key=(node.id?('#'+node.id):'')
              +((typeof node.className==='string'&&node.className)?('.'+node.className.split(' ')[0]):'')
              || '(无名节点)';
            hit[key]=(hit[key]||0)+1;
          }
        }
      }
      return JSON.stringify({hits:hit});
    },
    measure:function(id){
      var main=(id==='MAIN');
      var root=main?document.body:document.getElementById(id);
      if(!root) return {bad:['没有节点 #'+id],clips:[],ov:[],n:0};
      var panel=main?document.body:(document.querySelector('#'+id+' .panel')||root);
      var vw=window.innerWidth,vh=window.innerHeight;
      var r=panel.getBoundingClientRect(),bad=[],list=[],i;
      /* 只看「该元素是 .sheet 时」的 .on：阻断层 #bootFail 不是 .sheet，它靠自身在 DOM 里存在 */
      if(!main&&root.classList.contains('sheet')&&!root.classList.contains('on')) bad.push('未显示（.on 不在）');
      if(r.width<1||r.height<1) bad.push('零尺寸 '+Math.round(r.width)+'x'+Math.round(r.height));
      if(r.left<-0.5) bad.push('左溢 '+r.left.toFixed(1));
      if(r.right>vw+0.5) bad.push('右溢 '+(r.right-vw).toFixed(1));
      /* 主屏是「可以往下长」的滚动文档，量 body 的下沿没意义（它本来比视口高出一截）；
         真正必须落在视口里的是两块钉住不动的：吸顶的 header.hdr 与钉底的 nav.dock。
         面板则相反——.panel 有 max-height:92vh，越出视口就是画不进去。 */
      if(main){
        var hd=document.querySelector('header.hdr'), dk=document.querySelector('nav.dock');
        if(!hd||!dk){ bad.push('主屏缺 header.hdr 或 nav.dock'); }
        else{
          var hr=hd.getBoundingClientRect(), kr=dk.getBoundingClientRect();
          if(hr.top<-0.5) bad.push('顶栏上溢 '+hr.top.toFixed(1));
          if(hr.bottom>vh) bad.push('顶栏下溢到屏外 '+hr.bottom.toFixed(1));
          if(hr.left<-0.5||hr.right>vw+0.5) bad.push('顶栏横向越界 '+hr.left.toFixed(1)+'..'+hr.right.toFixed(1));
          if(kr.bottom>vh+0.5) bad.push('dock 沉到屏外 '+(kr.bottom-vh).toFixed(1));
          if(kr.top<0) bad.push('dock 顶边出屏 '+kr.top.toFixed(1));
          if(kr.left<-0.5||kr.right>vw+0.5) bad.push('dock 横向越界 '+kr.left.toFixed(1)+'..'+kr.right.toFixed(1));
          if(kr.top<hr.bottom) bad.push('dock 压住顶栏 ('+hr.bottom.toFixed(1)+' vs '+kr.top.toFixed(1)+')');
        }
      }else{
        if(r.top<-0.5) bad.push('上溢 '+r.top.toFixed(1));
        if(r.bottom>vh+0.5) bad.push('下溢 '+(r.bottom-vh).toFixed(1));
      }
      var ho=panel.scrollWidth-panel.clientWidth;
      if(ho>1) bad.push('面板横向溢出 '+ho+'px');
      var dO=Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-vw;
      if(dO>1) bad.push('整页横向溢出 '+dO+'px');
      var tlen=flat(panel.textContent||'').length;
      if(tlen<(main?40:8)) bad.push('文本过少 '+tlen);
      var all=panel.querySelectorAll(SEL);
      for(i=0;i<all.length;i++){ if(vis(all[i])) list.push(all[i]); }
      if(main&&list.length<12) bad.push('主屏可点元素过少 '+list.length);
      if(!main&&list.length<1) bad.push('面板内没有可点元素');
      var clips=[];
      for(i=0;i<list.length;i++){
        var e=list[i];
        if(e.tagName==='INPUT'||e.tagName==='SELECT'||e.tagName==='TEXTAREA') continue;
        if(e.scrollWidth>e.clientWidth+1&&flat(e.textContent||'')){
          clips.push(name(e)+' “'+flat(e.textContent).slice(0,14)+'” '+e.scrollWidth+'/'+e.clientWidth);
        }
      }
      var ov=[],nOv=0;
      for(i=0;i<list.length;i++){
        var a=list[i];
        for(var k=i+1;k<list.length;k++){
          var b=list[k];
          if(a.parentElement!==b.parentElement) continue;
          var ca=getComputedStyle(a),cb=getComputedStyle(b);
          if(ca.position==='absolute'||ca.position==='fixed'||cb.position==='absolute'||cb.position==='fixed') continue;
          var ra=a.getBoundingClientRect(),rb=b.getBoundingClientRect();
          var ix=Math.min(ra.right,rb.right)-Math.max(ra.left,rb.left);
          var iy=Math.min(ra.bottom,rb.bottom)-Math.max(ra.top,rb.top);
          if(ix<=1||iy<=1) continue;
          var small=Math.min(ra.width*ra.height,rb.width*rb.height);
          if(!small||ix*iy/small<=0.25) continue;
          nOv++;
          if(ov.length<3) ov.push(name(a)+'×'+name(b)+' '+Math.round(ix)+'x'+Math.round(iy));
        }
      }
      return {bad:bad,clips:clips.slice(0,3),nClips:clips.length,ov:ov,nOv:nOv,n:list.length};
    }
  };
  function dj2(s){ return flat(s||'').slice(0,8); }
})()`;

let PASS = 0, FAIL = 0, LINES = [];
function T(label, ok, detail) {
  PASS += ok ? 1 : 0; FAIL += ok ? 0 : 1;
  LINES.push((ok ? 'PASS  ' : 'FAIL  ') + label + (detail !== undefined ? '  [' + detail + ']' : ''));
}
const EXP_N = 266;                       // 正常一轮应有的条数（Z0 只在崩了才出现，不计入）；v0.44/F20 advSetSheet 加 7 条（4 档几何 + BACK 收口 + 入口 2 腿）；v0.70 档案/水平合并成一行，入口减 1 条 → 2 腿减 2；v0.70 加 Dk1（底部日卡在 360px 内不被长日名撑出屏）；v0.70 工具区三张 sheet 加 15（3×4 档几何 + 3 BACK 收口）；v0.70 加 G12（320px 工具区/RPE 提示不裁切）
let SECT = { s: 'A0' };

function send(ws, idRef, method, params) {
  return new Promise((res, rej) => {
    const mid = ++idRef.v;
    const cb = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id !== mid) return;
      ws.removeEventListener('message', cb);
      m.error ? rej(m.error) : res(m.result);
    };
    ws.addEventListener('message', cb);
    ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
}

let chrome = null, tmp = null, ws = null, idRef = { v: 0 };
async function main() {
  tmp = path.join(os.tmpdir(), 'rpl-uiv-' + Date.now());
  chrome = spawn(CHROME, [
    '--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${path.join(tmp, 'profile')}`,
    `--window-size=412,${HEIGHT}`, '--force-device-scale-factor=1', '--hide-scrollbars',
    '--no-first-run', '--allow-file-access-from-files', 'about:blank',
  ], { stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 800));
  let wsUrl = null;
  for (let i = 0; i < 60 && !wsUrl; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json`).then(x => x.json());
      const pg = (r || []).find(x => x.type === 'page');
      if (pg) wsUrl = pg.webSocketDebuggerUrl;
    } catch (e) { await new Promise(r => setTimeout(r, 200)); }
  }
  if (!wsUrl) { console.error('连不上 CDP（Chrome 没起来？）'); await tmpclean.close(chrome, tmp, true); process.exit(2); }
  ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  const rawSend = (m, p) => send(ws, idRef, m, p);
  async function ev(expr) {
    const r = await rawSend('Runtime.evaluate', { expression: expr, returnByValue: true });
    if (r.exceptionDetails) {
      throw new Error('页面求值失败：' + ((r.exceptionDetails.exception && r.exceptionDetails.exception.description) || r.exceptionDetails.text));
    }
    return r.result.value;
  }
  const call = (fn, args) => ev(`__uiv.call(${JSON.stringify(fn)},${JSON.stringify(args || [])})`);
  const click = (nid) => ev(`__uiv.click(${JSON.stringify(nid)})`);
  const measure = (id) => ev(`__uiv.measure(${JSON.stringify(id)})`);
  /* 等入场动效落地再量几何：轮询「还有没有有限次的动画在跑」，最多等 1200ms 兜底
     （页面没有 getAnimations 时直接返回，等价于旧的一次固定等待，不会卡死）。 */
  const settle = async () => {
    await new Promise(r => setTimeout(r, 60));
    for (let i = 0; i < 20; i++) {
      let busy = '0';
      try { busy = await ev('__uiv.animBusy()'); } catch (e) { return; }
      if (busy === '0') return;
      await new Promise(r => setTimeout(r, 60));
    }
  };

  await rawSend('Runtime.enable');
  const pageErrors = [];
  ws.addEventListener('message', (e) => {
    const m = JSON.parse(e.data);
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params && m.params.exceptionDetails;
      pageErrors.push(((d && d.exception && d.exception.description) || (d && d.text) || '未名异常').split('\n')[0]);
    }
  });
  await rawSend('Page.navigate', { url: FILE });
  let ready = false;
  for (let i = 0; i < 40 && !ready; i++) {
    try { ready = !!(await ev('(state&&state.lib)?1:0')); } catch (e) { /* 页面还没解析完 */ }
    if (!ready) await new Promise(r => setTimeout(r, 300));
  }
  if (!ready) { console.error('页面 12s 内未就绪'); await tmpclean.close(chrome, tmp, true); process.exit(2); }
  await ev(HELP);
  /* 状态监控面板现在默认关着（开关入口在设置页·我的档案）。本套的 P 段要逐面板量几何，
     所以按「用户已经打开」进门；关门那条腿由 v3v 的 TM 段单独测。
     必须连盘一起写：只改内存的话，遍历中途任何一次 savePrefsOnly 都会把 true 落下去，
     K1 那条「四路分片遍历前后逐字节同」就会红 1 个字节（"teleOn":false → true）。 */
  await ev('state.teleOn=true; savePrefsOnly(); renderTelemetry();');

  /* ---------------- A0 段：名单与点名 ---------------- */
  SECT.s = 'A0';
  const miss = await ev(`__uiv.missingFns(${JSON.stringify(FN_NEEDED)})`);
  T('A0 UI 入口函数点名到齐（' + FN_NEEDED.length + ' 个）', miss === '', miss === '' ? '全部在 window 上' : '缺失 ' + miss);
  const pageList = (await ev('__uiv.closeList()')).split(',');
  const mine = PANELS.map(p => p.id);
  const drift = mine.filter(x => pageList.indexOf(x) < 0).concat(pageList.filter(x => mine.indexOf(x) < 0));
  T('A0 面板名单与 closeAllSheets 双向一致（' + pageList.length + ' 个 .sheet）',
    drift.length === 0 && pageList.length === PANELS.length,
    drift.length ? '漂移 ' + drift.join('/') : '名单 ' + pageList.join(','));
  const store0 = await ev('__uiv.storeHash()');
  const ledger0 = await ev('__uiv.ledgerHash()');

  /* ---------------- G / P 段：四档宽度 × 主屏 + 14 面板 ---------------- */
  const verdict = (m) => {
    const bad = (m.bad || []).concat(m.nClips ? (m.nClips + ' 处文本裁切：' + m.clips.join(' ; ')) : [])
      .concat(m.nOv ? (m.nOv + ' 处同级可点元素互叠：' + m.ov.join(' ; ')) : []);
    return { ok: bad.length === 0, detail: bad.join(' / '), n: m.n };
  };
  for (const w of WIDTHS) {
    SECT.s = 'G/P ' + w;
    await rawSend('Emulation.setDeviceMetricsOverride', { width: w, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
    await ev('closeAllSheets()'); await settle();
    const gm = verdict(await measure('MAIN'));
    T('G 主屏 ' + w + 'px 几何合格', gm.ok, gm.detail || ('可点元素 ' + gm.n + ' 个'));
    for (const p of PANELS) {
      await ev('closeAllSheets()'); await settle();
      await call(p.open, p.args); await settle();
      const m = verdict(await measure(p.id));
      T('P ' + w + 'px ' + p.id + ' 打开后几何合格', m.ok, m.detail || ('可点元素 ' + m.n + ' 个'));
      if (p.id === 'adviceSheet') {
        /* 表格容器自己滚不算「几何合格」：建议那一列要是得横滚才看见，这屏就白做了。
           measure() 量的是可点元素的矩形，表格里没有按钮，所以这条得单独量容器。 */
        const box = await ev('(function(){var x=document.querySelector("#advBody .log-wrap");'
          + 'if(!x) return "";return x.clientWidth+","+x.scrollWidth;})()');
        const parts = String(box || '').split(',');
        const cw = +parts[0], sw = +parts[1];
        T('P ' + w + 'px adviceSheet 的建议列不用横滚：表格容器不横向溢出',
          parts.length === 2 && cw > 0 && sw <= cw + 1,
          parts.length === 2 ? ('可视 ' + cw + 'px · 内容 ' + sw + 'px') : '取不到 #advBody .log-wrap');
      }
    }
  }

  /* ---------------- S 段：返回键逐个面板收口（412px） ---------------- */
  SECT.s = 'S';
  await rawSend('Emulation.setDeviceMetricsOverride', { width: 412, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
  for (const p of PANELS) {
    await ev('closeAllSheets()'); await settle();
    await call(p.open, p.args); await settle();
    const opened = await ev('__uiv.anyOpen()');
    const back = await ev('(window.__handleBack&&__handleBack())?1:0');
    await settle();
    const still = await ev('__uiv.openIds()');
    T('S ' + p.id + ' 返回键收口（BACK 后不该有 .sheet.on）',
      opened === true && back === 1 && still === '',
      'open=' + opened + ' back=' + back + ' 残留=[' + still + ']');
  }

  /* ---------------- E 段：全部真实入口的点击链 ---------------- */
  SECT.s = 'E';
  for (const en of ENTRIES) {
    const host = en.host || 'setSheet';
    const hostPanel = PANELS.find(p => p.id === host);
    await ev('closeAllSheets()'); await settle();
    if (en.btn !== 'logoBtn') await call(hostPanel.open, hostPanel.args);
    await settle();
    await click(en.btn); await settle();
    const on = await ev(`document.getElementById(${JSON.stringify(en.want)}).classList.contains('on')?1:0`);
    const others = await ev(`(function(){var n=document.querySelectorAll('.sheet.on'),o=[],i;for(i=0;i<n.length;i++){if(n[i].id!==${JSON.stringify(en.want)}) o.push(n[i].id);}return o.join(',');})()`);
    T('E #' + en.btn + ' 点开 ' + en.want, on === 1,
      on === 1 ? ('同屏其他面板 [' + others + ']') : '点击后该面板没 on（当前 on 的是 [' + (await ev('__uiv.openIds()')) + ']）');
    /* 设置是独立页而不是抽屉：入口把目标页叠在 host 之上，host 留在栈底，
       返回键先回 host（设置/图表 hub），再回首页。所以这里断言的是「host 仍在且只有 host 一层」。 */
    if (en.btn !== 'logoBtn') {
      const still = await ev(`document.getElementById(${JSON.stringify(host)}).classList.contains('on')?1:0`);
      T('E #' + en.btn + ' 点后' + host + ' 留栈底（返回回上一页）', still === 1 && others === host,
        host + ' 仍 on=' + still + ' 同屏=[' + others + ']');
    }
  }

  /* ---------------- X 段：语言 / 主题 / 计时器 / 阻断层 ---------------- */
  SECT.s = 'X';
  await ev('closeAllSheets()'); await ev("setLang('en')"); await settle();
  const enLang = await ev('__uiv.lang()');
  const enPanels = [];
  for (const pid of ['setSheet', 'archSheet', 'progLibSheet']) {
    await ev('closeAllSheets()'); await settle();
    await call(PANELS.find(p => p.id === pid).open, PANELS.find(p => p.id === pid).args); await settle();
    const v = verdict(await measure(pid));
    if (!v.ok) enPanels.push(pid + ' ' + v.detail);
  }
  T('X1 切英文后主屏与三块面板仍合格、html lang 落到 en',
    enLang.indexOf('en') >= 0 && enPanels.length === 0, enLang + ' / ' + (enPanels.join(' ; ') || '三面板 OK'));
  await ev("setLang('zh')"); await ev('closeAllSheets()'); await settle();
  const zhLang = await ev('__uiv.lang()');
  const zhV = verdict(await measure('MAIN'));
  T('X2 切回中文后主屏仍合格', zhLang.indexOf('zh') >= 0 && zhV.ok, zhLang + ' / ' + (zhV.detail || 'OK'));
  const themeIds = JSON.parse(await ev('JSON.stringify(window.THEME_IDS||[])'));
  const theme0 = await ev('__uiv.theme()');
  const hops = [];
  for (const t of themeIds) { await call('setTheme', [t]); await settle(); hops.push(await ev('__uiv.theme()')); }
  const themeV = verdict(await measure('MAIN'));
  T('X3 逐主题切换（'+themeIds.length+' 档）：state.theme / data-theme / data-mode 三样一致且主屏几何不受影响',
    themeIds.length >= 3 && hops.length === themeIds.length
    && hops.every((h, i) => { const p = h.split('|'); return p[0] === themeIds[i] && p[1] === themeIds[i]
        && (p[2] === 'dark' || p[2] === 'light'); }) && themeV.ok,
    hops.join(' → ') + ' / ' + (themeV.detail || 'OK'));
  await call('setTheme', [themeIds[0]]); await settle();
  const cyc0 = await ev('__uiv.theme()');
  for (let i = 0; i < themeIds.length; i++) await call('cycleTheme'); await settle();
  const themeBack = await ev('__uiv.theme()');
  T('X3b cycleTheme 走完注册表长度后回到起点（老「两跳即回环」在第三档会漏掉一档）',
    themeBack === cyc0, cyc0 + ' → ' + themeBack);
  await call('openSettings'); await settle();
  /* 两个分段器都要量：段数与格位现在是 segThumb 从按钮数派生出来的，
     「CSS 里少一条特例」这类坏法只有量像素才看得见——滑块跟按钮错开半格不会报错。 */
  function segBad(tag, info, idx, wantN, v) {
    const bad = [];
    if (!info || info.noseg) return [tag + ' 找不到分段器'];
    if (info.n !== wantN) bad.push(tag + ' 按钮' + info.n + '个≠' + wantN);
    if (info.on !== 1) bad.push(tag + ' 亮' + info.on + '个');
    if (info.sn !== info.n) bad.push(tag + ' --seg-n=' + info.sn + '≠按钮' + info.n);
    if (info.si !== idx) bad.push(tag + ' --seg-i=' + info.si + '≠' + idx);
    if (!info.thumb) bad.push(tag + ' 无滑块');
    else if (Math.abs(info.th.l - info.l[idx]) > 1 || Math.abs(info.th.w - info.w[idx]) > 1)
      bad.push(tag + ' 滑块left' + info.th.l + '/格' + info.l[idx]
        + ' 宽' + info.th.w + '/格' + info.w[idx]);
    if (info.h < 24) bad.push(tag + ' 按钮高' + info.h);
    if (v && !v.ok) bad.push(tag + ' 面板几何');
    return bad;
  }
  const segRows = [];
  for (const t of themeIds) {
    await call('setTheme', [t]); await settle();
    const info = JSON.parse(await ev('__uiv.segInfo("themeSeg")'));
    const v = verdict(await measure('setSheet'));
    const bad = segBad(t, info, themeIds.indexOf(t), themeIds.length, v);
    if (bad.length) segRows.push(bad.join(' , ') + ' ' + JSON.stringify(info)
      + (v.detail ? ' || ' + v.detail : ''));
  }
  const langBak = await ev('state.lang');
  for (const lg of ['zh', 'en']) {
    if (langBak !== lg) await ev("setLang('" + lg + "')");
    await settle();
    const info = JSON.parse(await ev('__uiv.segInfo("langSeg")'));
    const bad = segBad('lang:' + lg, info, lg === 'en' ? 1 : 0, 2, null);
    if (bad.length) segRows.push(bad.join(' , ') + ' ' + JSON.stringify(info));
  }
  const langNow = await ev('state.lang');
  if (langNow !== langBak) await ev("setLang('" + langBak + "')");
  await call('setTheme', [theme0.split('|')[0]]); await ev('closeAllSheets()'); await settle();
  T('X3c 两个分段器逐档合格：按钮数=注册表长度、恰好一个亮、段数与格位取自真实按钮数、'
    + '滑块像素压在该档按钮上、按钮高>=24px、面板几何合格',
    segRows.length === 0, segRows.join(' ; ')
      || (themeIds.length + ' 档主题 + 2 档语言 ' + 'OK'));
  /* 色板可读性只能逐主题量：几何类判据对「纸底上一片灰字」完全无感，
     而色号抄在规则里时它恰恰只在这一档出问题。半透明浅底先叠到卡底再算比值。 */
  const con = JSON.parse(await ev('__uiv.contrast()'));
  T('X3d 逐主题色板可读（' + con.pairs + ' 对 × ' + con.themes + ' 档）：写在档位实色 / '
    + '档位浅底 / 卡底上的文字，按 WCAG 相对亮度比都不低于 3.0',
    con.bad.length === 0,
    con.bad.length ? con.bad.join(' ; ') : ('最低 ' + con.min + ' @ ' + con.minAt));
  const tim = JSON.parse(await ev('__uiv.timerState(45,"T2")'));
  T('X4 计时器开→关：条子显示、收口干净、不留 interval',
    tim.on === true && tim.off === true && tim.running === false, JSON.stringify(tim));
  const dotRows = String(await ev('__uiv.tierDots()')).split(' ; ');
  const dotBad = dotRows.filter(r => /MISMATCH|tok=\(缺\)|令牌=\(缺值\)/.test(r));
  T('X4b 计时圆点跟主题令牌同源：每档主题 × T1/T2/T3 的圆点实色 = 该主题 --tX 令牌实色，且令牌都有值（'
    + themeIds.length + '×3 组）',
    dotBad.length === 0 && dotRows.length === themeIds.length * 3,
    dotBad.join(' | ') || (dotRows.length + ' 组一致 ' + dotRows[0]));
  /* 三方对账：按钮标签的数 / 点下去真的倒计时 / state.timerCfg 那格。
     标签原先是抄在 markup 里的（T1·5m），改默认值或老存档带别的秒数时它就撒谎。 */
  const chipRows = [], chipOk = [];
  for (const t of ['T1', 'T2', 'T3']) {
    const info = JSON.parse(await ev('__uiv.chipTap("' + t + '")'));
    const lab = String(info.lab || ''), unit = lab.split('·')[1] || '';
    const num = Number(unit.replace(/[ms]$/, ''));
    const labSecs = (!isFinite(num) || num <= 0) ? -1 : (/m$/.test(unit) ? Math.round(num * 60) : num);
    const mm = String(info.digits || '').split(':');
    const digSecs = (mm.length === 2) ? (Number(mm[0]) * 60 + Number(mm[1])) : -1;
    if (info.nochip || info.shown !== true || labSecs !== Number(info.cfg) || digSecs !== Number(info.cfg))
      chipRows.push(t + ' 标签「' + lab + '」=' + labSecs + 's / 表=' + digSecs + 's / cfg=' + info.cfg + 's');
    else chipOk.push(t + ' ' + info.cfg + 's');
  }
  T('X4c 点档钮走的是配置里的秒数，且按钮标签写的就是这一个数（标签 / 倒计时 / timerCfg 三方对账）',
    chipRows.length === 0, chipRows.join(' ; ') || chipOk.join(' / '));
  const bfBtns = await ev('__uiv.bootFail(1)');
  const bfV = verdict(await measure('bootFail'));
  T('X5 READONLY 阻断层在 412px 画得开（' + bfBtns + ' 个按钮、几何合格）',
    bfBtns >= 3 && bfV.ok, bfV.detail || (bfBtns + ' 按钮 OK'));
  await ev('closeAllSheets()');
  const bfAfter = await ev("document.getElementById('bootFail')?1:0");
  T('X6 阻断层不归 closeAllSheets 管（只有导出原文/重试/只读浏览三条出路）', bfAfter === 1,
    'closeAllSheets 后仍在=' + bfAfter);
  await ev('__uiv.bootFail(0)');
  await rawSend('Emulation.setDeviceMetricsOverride', { width: 320, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
  await settle();
  const bf320 = await ev('__uiv.bootFail(1)');
  const bf320V = verdict(await measure('bootFail'));
  T('X7 阻断层在 320px 也画得开', bf320 >= 3 && bf320V.ok, bf320V.detail || (bf320 + ' 按钮 OK'));
  await ev('__uiv.bootFail(0)');
  /* 阻断层不吃 CSS 令牌（它跑起来时账本已经不可信了），所以纸底档那套行内色是独立一段代码 ——
     独立一段就得单独点一次：只看暗色档的 X5/X7 看不出「主题分档」有没有跟上。 */
  const lightFirst = await ev("(window.THEME_IDS.filter(function(t){return window.THEME_MODE[t]==='light';}))[0]||''");
  const bfPaper = await ev(`__uiv.bootFail(1,${JSON.stringify(lightFirst)})`);
  const bfPaperV = verdict(await measure('bootFail'));
  const bfSt = JSON.parse(await ev("(function(){var b=document.getElementById('bootFail'),r=document.documentElement;"
    + "return JSON.stringify({bg:b?getComputedStyle(b).backgroundColor:'none',"
    + "theme:r.getAttribute('data-theme'),mode:r.getAttribute('data-mode'),"
    + "meta:document.getElementById('metaTheme').getAttribute('content'),"
    + "want:String(window.THEME_BG[r.getAttribute('data-theme')]||'')});})()"));
  await ev('__uiv.bootFail(0)');
  const bfRgb = (String(bfSt.bg).match(/[0-9]+/g) || [0, 0, 0]).map(Number);
  const hexRgb = (h) => { h = String(h).replace('#', ''); if (h.length === 3) h = h.split('').map(c => c + c).join('');
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]; };
  const bfLum = (c => { const a = c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2]; })(bfRgb);
  T('X8 纸底档的阻断层跟着注册表分档：320px 画得开、正文是亮底、状态栏与正文底色都取注册表该档值',
    !!lightFirst && bfPaper >= 3 && bfPaperV.ok && bfLum >= 0.55
    && bfSt.theme === lightFirst && bfSt.mode === 'light'
    && String(bfSt.meta).toLowerCase() === String(bfSt.want).toLowerCase()
    && bfRgb.join() === hexRgb(bfSt.want).join(),
    lightFirst + ' 底=' + bfSt.bg + ' 亮度=' + bfLum.toFixed(3) + ' 标记=' + bfSt.theme + '/' + bfSt.mode + ' 状态栏=' + bfSt.meta + ' 按钮=' + bfPaper);
  await rawSend('Emulation.setDeviceMetricsOverride', { width: 412, height: HEIGHT, deviceScaleFactor: 1, mobile: true });

  /* ---------------- M 段：动效与记录流反馈（v0.16） ---------------- */
  /* M 段是本轮唯一真会动账本的段落（Enter 焦点链会落一次 saveEditor，完成反馈会逐组勾）。
     所以段首先拍整份 state 快照，段尾按快照还原 —— K1/K2 那两条「遍历不留痕」才仍然成立；
     否则 M 段自己会把「全绿」变成「跑过一遍就把数据改了」。 */
  SECT.s = 'M';
  const mSnap0 = await ev('__uiv.snap()');
  const tokLine = await ev('__uiv.motionTokens()');
  const tokN = Number(String(tokLine).split('|')[0]);
  T('M1 动效令牌全部解析出值（时长与缓动只有 :root 这一处出处，名单现读不手抄）',
    String(tokLine).indexOf('(空)') < 0 && String(tokLine).indexOf('(no :root)') < 0
    && tokN >= 5 && String(tokLine).split('|')[1].split(' ').length === tokN, tokLine);
  await call('openProfile'); await settle();
  const midAnim = await ev("__uiv.animNames('profSheet')");
  await call('closeAllSheets'); await settle();
  await call('openEditor', [0]); await settle();
  const downAnim = await ev("__uiv.animNames('edSheet')");
  await call('closeAllSheets'); await settle();
  T('M2 居中面板（profSheet/mid）入场走 panel-in，时长取自动效令牌',
    midAnim.indexOf('profSheet:mid:panel-in') === 0 && midAnim.indexOf('0.22s') > 0, midAnim);
  T('M3 底部抽屉（edSheet/down）走另一条 keyframes（drawer-in），两类面板不是同一条规则凑数',
    downAnim.indexOf('edSheet:down:drawer-in') === 0 && downAnim.indexOf('0.22s') > 0, downAnim);
  const rmCss = await ev('__uiv.reducedMotionCss()');
  T('M4 减动偏好有兜底：@media (prefers-reduced-motion:reduce) 把时长压到 0（通配 * 一条）',
    rmCss.indexOf('@media (prefers-reduced-motion:reduce)') === 0
    && rmCss.indexOf('animation-duration') > 0 && rmCss.indexOf('transition-duration') > 0, rmCss);
  const hints = await ev('__uiv.enterHints()');
  await call('openEditor', [0]); await settle();
  const hintsOpen = await ev('__uiv.enterHints()');
  const focusChain = [];
  focusChain.push(await ev("__uiv.focusFrom('edLoad')"));
  focusChain.push(await ev("__uiv.focusFrom('edReps')"));
  focusChain.push(await ev("__uiv.focusFrom('edRpe')"));
  const noteHop = await ev("(function(){document.getElementById('edNotes').value=' uiv-M7 ';"
    + "return __uiv.focusFrom('edNotes');})()");
  const savedNote = await ev("String((day().exercises[0]||{}).notes)");
  /* 这一步必须在 closeAllSheets 之前读：先收一遍再问「关没关」，等于替 saveEditor 把活干了，
     断言就永远绿。 */
  const openAfterNote = await ev('__uiv.anyOpen()');
  await call('closeAllSheets'); await settle();
  T('M5 编辑器四个字段的软键盘提示齐（三个 next + 笔记 done）',
    hints.indexOf('(缺)') < 0 && hints.indexOf('(无节点)') < 0
    && /edLoad:next/.test(hintsOpen) && /edNotes:done/.test(hintsOpen), hintsOpen);
  T('M6 Enter 焦点链 载荷→次数→RPE→笔记 逐跳落点正确',
    focusChain[0] === 'edReps' && focusChain[1] === 'edRpe' && focusChain[2] === 'edNotes',
    focusChain.join(' → ') + ' / 字段 ' + hints);
  T('M7 笔记上按 Enter 就是保存：内容真的落账（trim 后写入）、面板收起、焦点交还',
    noteHop === 'body' && openAfterNote === false && savedNote === 'uiv-M7',
    '落点=' + noteHop + ' 仍开=' + openAfterNote + ' 笔记落账=[' + savedNote + ']');
  await call('openEditor', [0]); await settle();
  const flash0 = await ev('__uiv.flashCardCheck(0)');
  await call('closeAllSheets'); await settle();
  T('M8 刚落账的卡闪一下且不改变卡片宽度（动效不许动几何）',
    JSON.parse(flash0).cls === true && JSON.parse(flash0).wStable === true
    && JSON.parse(flash0).anim === 'card-just', flash0);
  /* 「凑齐那一下」只能发生一次，但上一版可能已经把这天的组全勾完了 —— 所以先把勾全部撤掉，
     从干净起点逐组勾满，中途用 pingDayComplete() 的返回值摸闸门：
       未满 → false 且复位；刚满 → true（出 toast）；再问一次 → false（只报一次）；
       撤一组再问 → false；补回去 → 又出 toast（证明复位是真的复位，不是靠 toastId 没到期糊过去的）。
     全程改的是当日勾选项，结尾按**段首**快照整体还原，K1/K2 会复核不留痕。
     中途每次要看 toast 之前先把它清空 —— toast 自己 1.8s 才收，不清就分不清「又弹了一次」和「上一次还没散」。 */
  const gate = JSON.parse(await ev("(function(){"
    + "var l=(day().exercises||[]),i,t=document.getElementById('toast');"
    + "function tx(){return t.classList.contains('on')?String(t.textContent||'').trim():'';}"
    + "function clr(){clearTimeout(toastId);t.classList.remove('on');t.textContent='';}"
    + "for(i=0;i<l.length;i++) if(l[i].done) toggleDone(i);"
    + "clr(); var offAll=pingDayComplete(),flips=0;"
    + "for(i=0;i<l.length;i++) if(!l[i].done){ toggleDone(i); flips++; }"
    + "var first=tx(),again=pingDayComplete();"
    + "if(l.length) toggleDone(l.length-1); clr(); var afterOff=pingDayComplete(),undo=tx();"
    + "if(l.length) toggleDone(l.length-1); var second=tx();"
    + "if(l.length) toggleDone(l.length-1); clr(); var tail=pingDayComplete();"
    + "return JSON.stringify({n:l.length,offAll:offAll,flips:flips,first:first,again:again,"
    + "afterOff:afterOff,undo:undo,second:second,tail:tail});})()"));
  await ev('stopTimer()'); await settle();
  const midSnap = await ev('__uiv.snap()');
  await ev(`__uiv.restore(${JSON.stringify(mSnap0)})`); await settle();
  const snapBack = await ev('__uiv.snap()');
  const stillOpen = await ev('__uiv.anyOpen()');
  T('M9 本日全部完成只报一次：未满不报、凑齐那一下报、重复点不报、撤一组即复位',
    gate.n > 0 && gate.flips === gate.n && gate.offAll === false && gate.again === false
    && gate.afterOff === false && gate.tail === false && gate.undo === ''
    && ((gate.first || '').indexOf('本日全部完成') >= 0 || (gate.first || '').indexOf('DAY COMPLETE') >= 0)
    && ((gate.second || '').indexOf('本日全部完成') >= 0 || (gate.second || '').indexOf('DAY COMPLETE') >= 0),
    '当天 ' + gate.n + ' 组 / 补勾 ' + gate.flips + ' / 满后再问=' + gate.again + ' / toast「' + gate.first + '」「' + gate.second + '」');
  T('M10 M 段动完账本就还原：确实动过（还原前快照与段首不同）、还原后逐字节相同、面板全部收起',
    midSnap !== mSnap0 && snapBack === mSnap0 && stillOpen === false,
    '动过=' + (midSnap !== mSnap0) + ' 还原相同=' + (snapBack === mSnap0) + ' 仍开着=' + (stillOpen));

  /* ---------------- B 段：动作选择链真点 + 逐层几何（四档宽度） ----------------
     G/P 段量的是 brSheet 打开那一眼（manage 态、层级 0）；而用户实际走的是
     主屏「+ 添加训练动作」→ 编辑器 → 里面那颗 mv-btn → 层级 0 → 1 → 2 → 点一行动作
     → 回到编辑器，每一层换的是 #brBody 里同一批 .br-row。crumb 三段、meta 的数字、
     「上次选的就是这一行」的高亮都只在换层之后才出现。
     全程真点：加练钮与 mv-btn 都只有 class 没有 id，列表行是拼出来的，
     所以下探针一律按选择器取节点再 .click()，一个 openBrowse/brGo/pickAct 都不直呼。
     段尾按段首快照还原 —— 选择动作是真的落账（还多加了一行），不留痕给 K1/K2。 */
  SECT.s = 'B';
  const bSnap0 = await ev('__uiv.snap()');
  const bKey = await ev("(function(){var c=state.lib.cats,k,i,a;"
    + "for(i=0;i<c.length;i++){a=c[i].acts||[];for(k=0;k<a.length;k++){if(a[k]&&a[k].en)return String(a[k].en).slice(0,4).toLowerCase();}}return '';})()");
  const bDomN = Number(await ev('state.lib.domains.length'));
  for (const w of WIDTHS) {
    SECT.s = 'B ' + w;
    await rawSend('Emulation.setDeviceMetricsOverride', { width: w, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
    await ev('closeAllSheets()'); await settle();
    const tap = JSON.parse(await ev('__uiv.addTap()'));
    await settle();
    const g0 = verdict(await measure('brSheet'));
    const p1 = JSON.parse(await ev('__uiv.brTap(0)')); await settle();
    const g1 = verdict(await measure('brSheet'));
    const p2 = JSON.parse(await ev('__uiv.brTap(0)')); await settle();
    const g2 = verdict(await measure('brSheet'));
    const bIdx = Number(p2.other) >= 0 ? Number(p2.other) : 0;
    const p3 = JSON.parse(await ev('__uiv.brTap(' + bIdx + ')')); await settle();
    /* 再点一次 mv-btn 进来：选过的行该带 .picked（这条高亮是「我刚才选的是它」的唯一回执） */
    const q0 = JSON.parse(await ev('__uiv.mvTap()')); await settle();
    await ev('__uiv.brTap(0)'); await settle();
    const q2 = JSON.parse(await ev('__uiv.brTap(0)')); await settle();
    const pickBad = [];
    if (p3.br !== 0) pickBad.push('选完动作选择器还开着（两层叠着回不去改载荷）');
    if (p3.ed !== 1) pickBad.push('选完编辑器被一起收掉了');
    if (!p3.mvName || p3.mvName === '—') pickBad.push('动作名标签还是空占位：[' + p3.mvName + ']');
    if (!p3.mvPath || p3.mvPath === '—') pickBad.push('路径标签还是空占位：[' + p3.mvPath + ']');
    if (p3.got === 1 && p3.lab && p3.mvName !== p3.lab) pickBad.push('标签落的不是点的那一行：钮里「' + p3.mvName + '」/ 点的行「' + p3.lab + '」');
    if (p3.got === 1 && p3.title !== p3.mvName) pickBad.push('面板标题与钮内动作名分叉：' + p3.title + ' vs ' + p3.mvName);
    if (q0.br !== 1) pickBad.push('mv-btn 第二次进来动作面板没开');
    if (q0.ed !== 1) pickBad.push('mv-btn 进来时编辑器让位了（父子两层都该在）');
    if (q2.pickN !== 1) pickBad.push('重进来时选中行的高亮有 ' + q2.pickN + ' 个（应为 1 个）');
    else if (q2.pickAt !== bIdx) pickBad.push('高亮停在第 ' + q2.pickAt + ' 行，但选的是第 ' + bIdx + ' 行');
    const geBad = [];
    if (tap.noAdd) geBad.push('主屏没有 button.add 那颗加练钮');
    if (Number(tap.n1) !== Number(tap.n0) + 1) geBad.push('点加练没追加动作行：' + tap.n0 + ' → ' + tap.n1);
    if (tap.ed !== 1) geBad.push('加练后编辑器没开');
    if (tap.br !== 1) geBad.push('加练后没有直接进选择器（用户得再点一次才选到动作）');
    if (tap.mode !== 'pick') geBad.push('加练进的是 ' + tap.mode + ' 态');
    if (tap.name !== '—') geBad.push('新行的动作名不是占位：' + tap.name);
    if (String(tap.path).indexOf('未关联') < 0 && String(tap.path).indexOf('No category') < 0) geBad.push('空 mv 的新行没有「未关联分类」提示：[' + tap.path + ']');
    if (String(tap.ttl).indexOf('选择') < 0 && String(tap.ttl).indexOf('PICK') < 0) geBad.push('标题不是选择态：' + tap.ttl);
    if (tap.rows !== bDomN) geBad.push('层级 0 行数 ' + tap.rows + ' ≠ 功能域数 ' + bDomN);
    if (!g0.ok) geBad.push('层级 0 ' + g0.detail);
    if (p1.lvl !== 1) geBad.push('点功能域行没下到分类层：lvl=' + p1.lvl);
    if (!g1.ok) geBad.push('层级 1 ' + g1.detail);
    if (p1.crumb !== 2 || p1.cur !== 1) geBad.push('层级 1 crumb ' + p1.crumb + ' 段 / 高亮 ' + p1.cur);
    if (p2.lvl !== 2) geBad.push('点分类行没下到动作层：lvl=' + p2.lvl);
    if (!g2.ok) geBad.push('层级 2 ' + g2.detail);
    if (p2.crumb !== 3 || p2.cur !== 1) geBad.push('层级 2 crumb ' + p2.crumb + ' 段 / 高亮 ' + p2.cur);
    if (!/^[0-9]/.test(String(p2.meta))) geBad.push('层级 2 的 meta 没报动作数：[' + p2.meta + ']');
    if (p2.rows !== Number(String(p2.meta).replace(/[^0-9]/g, ''))) geBad.push('meta 报 ' + p2.meta + ' 但画了 ' + p2.rows + ' 行');
    if (p3.got !== 1) geBad.push('动作层没点到第 ' + bIdx + ' 行（共 ' + p3.n + ' 行）');
    if (Number(tap.addH) < 40 || Number(p1.rowH) < 40 || Number(p2.rowH) < 40 || Number(p3.rowH) < 40) {
      const thin = [];
      if (Number(tap.addH) < 40) thin.push('加练钮 ' + tap.addH + 'px');
      if (Number(p1.rowH) < 40) thin.push('功能域行 ' + p1.rowH + 'px');
      if (Number(p2.rowH) < 40) thin.push('分类行 ' + p2.rowH + 'px');
      if (Number(p3.rowH) < 40) thin.push('动作行 ' + p3.rowH + 'px');
      geBad.push('热区不足 40px（' + thin.join(' / ') + '）：戴护腕、屏幕糊着镁粉时拇指点不准');
    }
    T('B ' + w + 'px 加练 → 逐层下钻 → 点动作回编辑器 → 再进来高亮还在：两层关系、三层几何、落的正是点的那一行',
      geBad.length === 0 && pickBad.length === 0,
      geBad.concat(pickBad).join(' / ')
      || ('+' + tap.n0 + '→' + tap.n1 + ' 行 / 层级0 ' + tap.rows + ' 域 → 层级1 ' + p1.rows + ' 类 → 层级2 ' + p2.rows + ' 动作（meta ' + p2.meta + '）→ ' + p3.mvName
        + ' · 热区 加练' + tap.addH + '/域' + p1.rowH + '/类' + p2.rowH + '/动作' + p3.rowH + 'px'));
    /* 搜索那一腿：走 #brQ 真实的 oninput，命中数与行数对账、空态在位、返回先清词 */
    await ev('closeAllSheets()'); await settle();
    await call('openEditor', [0]); await settle();
    await ev('__uiv.mvTap()'); await settle();
    const sHit = JSON.parse(await ev('__uiv.brType(' + JSON.stringify(bKey) + ')'));
    const sv = verdict(await measure('brSheet'));
    const sNone = JSON.parse(await ev('__uiv.brType("zzz 不存在 zzz")'));
    await click('brBack');
    /* 这里不再输入任何东西：只看真点返回钮之后 BR.q 与搜索框各自的残留 */
    const sUp = await ev("(function(){var e=document.getElementById('brQ');"
      + "return String(BR.q)+'|'+String(e?e.value:'(无框)')+'|'+document.querySelectorAll('#brBody .br-row').length;})()");
    const sBad = [];
    if (sHit.noIn) sBad.push('没有 #brQ 搜索框');
    if (!bKey) sBad.push('取不到搜索关键词（库里没有带 en 名的动作）');
    if (sHit.hits < 1) sBad.push('「' + bKey + '」命中 0 条');
    if (sHit.rows !== sHit.hits) sBad.push('命中 ' + sHit.hits + ' 条但画了 ' + sHit.rows + ' 行');
    if (String(sHit.crumb).indexOf('搜索') < 0 && String(sHit.crumb).indexOf('Search') < 0) sBad.push('crumb 没进搜索态：[' + sHit.crumb + ']');
    if (!sv.ok) sBad.push('搜索结果几何：' + sv.detail);
    if (sNone.empty !== 1) sBad.push('零命中没有空态节点（一片白，看不出是搜索没结果）');
    const sParts = String(sUp).split('|');
    if (sParts[0] !== '' || sParts[1] !== '') sBad.push('真点返回钮后关键词没清：BR.q=[' + sParts[0] + '] 框内=[' + sParts[1] + ']');
    if (Number(sParts[2]) !== bDomN) sBad.push('清词后没回到层级 0 的 ' + bDomN + ' 个功能域，实为 ' + sParts[2]);
    T('B ' + w + 'px 搜索腿走 #brQ 真实 oninput：命中数=行数、crumb 进搜索态、零命中有空态、返回先清词',
      sBad.length === 0, sBad.join(' / ')
      || ('「' + bKey + '」' + sHit.hits + ' 条 / 行高 ' + sHit.rowH + 'px / 空态 ' + sNone.empty));
  }
  await ev('closeAllSheets()'); await settle();
  const bMid = await ev('__uiv.snap()');
  await ev(`__uiv.restore(${JSON.stringify(bSnap0)})`); await settle();
  const bBack = await ev('__uiv.snap()');
  const bOpen = await ev('__uiv.anyOpen()');
  await rawSend('Emulation.setDeviceMetricsOverride', { width: 412, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
  T('B 段出段还原：真点选择链改过的账回到进段前、面板收干净（K1/K2 复核全站不留痕）',
    bMid !== bSnap0 && bBack === bSnap0 && bOpen === false,
    '动过=' + (bMid !== bSnap0) + ' 还原相同=' + (bBack === bSnap0) + ' 仍开着=' + bOpen);

  /* ---------------- U 段：写回四档的真点击链（412px） ----------------
     全程不直呼 advApply / advUndo，只点页面上真实存在的控件：
     select 的 change、行内「应用」、审计行「撤销」、批量按钮的第一下与第二下。
     写盘是真的发生（分片会动），所以段尾按段首快照整体还原，交给 K1/K2 复核不留痕。 */
  SECT.s = 'U';
  await ev('closeAllSheets()'); await settle();
  const uSnap0 = await ev('__uiv.snap()');
  const uLedgerPre = await ev('__uiv.ledgerHash()');
  await ev(`(function(){
    var d=dayIds()[0];
    function mk(row,mv,mode,load,ds,rpe,tr,reps){return {row:row,cat:'S.Main',mv:mv,mode:mode,load:load,
      reps:reps,rpe:rpe,targetRpe:tr,doneSets:ds,done:ds>0,notes:''};}
    function wk(list){var o={};o[d]={title:'U FIX',exercises:list};return o;}
    /* 夹具必须落在「对比周」下拉真的选得到的那一对上：adviceSrcWeekOptions 的默认值 =
       最后一个可选源周 = 末周−1，内置 8 周模板下就是 W7 → W8。 */
    /* 整块换掉周表（同 O 段口径）：默认源周 = 末周−1 恒为 W7 → W8，不随种子计划长度漂移。
       换表后必须把当前周/日也落进新表：renderAll 会读 state.weeks[state.week][state.day]，
       留在旧号上会让写回后的重渲染抛错（应用按钮点了没 toast、也不算失败，纯静默）。 */
    state.week=7; state.day=d;
    state.weeks={'6':wk([]),'7':wk([mk(900,'U Up','T1.Mod',120,3,6,7,6),mk(901,'U Hard','T2.5x5',100,5,9.6,7,3),
                          mk(902,'U DL','T1.Mod',120,3,6,7,6)]),
                 '8':wk([mk(900,'U Up','T1.Mod',120,3,6,7,6),mk(901,'U Hard','T2.5x5',100,5,9.6,7,3),
                          mk(902,'U DL','T1.DL',120,3,6,7,6)])};
    state.advAudit=[]; return d;})()`);
  /* 基线取在夹具注入之后：夹具本身就要改周表，拿进段前的哈希去比「没写」等于比夹具自己。 */
  const uLedger0 = await ev('__uiv.ledgerHash()');
  await ev('openAdviceSheet()'); await settle();
  const uSug = JSON.parse(await ev(`(function(){var x=document.querySelector('#advBody .log-wrap');
    return JSON.stringify({tier:advTier(),btns:document.querySelectorAll('#advBody .adv-mini').length,
      dis:document.getElementById('advApplyAll').disabled,undoDis:document.getElementById('advUndoLast').disabled,
      opts:document.getElementById('advTier').options.length,sel:document.getElementById('advTier').value,
      rows:document.querySelectorAll('#advBody tbody tr').length,ovf:x?(x.scrollWidth-x.clientWidth):-1,
      led:__uiv.ledgerHash()});})()`));
  T('U1 默认档「只建议」真点开：下拉四档且选中只建议，表里一个应用按钮都没有、批量与撤销都禁用，账本一字未动',
    uSug.tier === 'suggest' && uSug.opts === 4 && uSug.sel === 'suggest' && uSug.rows === 3
    && uSug.btns === 0 && uSug.dis === true && uSug.undoDis === true && uSug.ovf <= 1
    && uSug.led === uLedger0,
    '档位=' + uSug.tier + ' 按钮=' + uSug.btns + ' 溢出=' + uSug.ovf + ' 账本同=' + (uSug.led === uLedger0));

  await ev("(function(){var s=document.getElementById('advTier');s.value='confirm';s.dispatchEvent(new Event('change'));})()");
  await settle();
  const uConf = JSON.parse(await ev(`(function(){var x=document.querySelector('#advBody .log-wrap');
    return JSON.stringify({tier:advTier(),btns:document.querySelectorAll('#advBody .adv-mini').length,
      dis:document.getElementById('advApplyAll').disabled,no:document.querySelectorAll('#advBody s.no').length,
      at:document.querySelectorAll('#advBody s.at').length,ovf:x?(x.scrollWidth-x.clientWidth):-1});})()`));
  T('U2 切到「确认后应用」：可写的两行才长出按钮，减载那行显示拒绝标记，容器仍不横滚',
    uConf.tier === 'confirm' && uConf.btns === 2 && uConf.dis === false && uConf.no >= 1 && uConf.ovf <= 1,
    '按钮=' + uConf.btns + ' 拒绝标记=' + uConf.no + ' 溢出=' + uConf.ovf);

  const uRow = JSON.parse(await ev(`(function(){var b=document.querySelector('#advBody .adv-mini');b.click();
    var t=document.getElementById('toast');
    return JSON.stringify({toast:t.classList.contains('on')?String(t.textContent||'').trim():'',
      up:(state.weeks['8'][dayIds()[0]].exercises[0].load),
      hard:(state.weeks['8'][dayIds()[0]].exercises[1].load),
      dl:(state.weeks['8'][dayIds()[0]].exercises[2].load),
      kinds:advAuditOf().map(function(b){return b.kind+':'+b.items.length;}).join(','),
      btns:document.querySelectorAll('#advAudit .adv-mini').length});})()`));
  T('U3 点行内「应用」：只有那一格变成交付值，其余两行原样，批次记成 kind=row 并长出撤销按钮',
    uRow.up === 125 && uRow.hard === 100 && uRow.dl === 120
    && uRow.kinds === 'row:1' && uRow.btns === 1 && (uRow.toast || '').indexOf('已写回') >= 0,
    JSON.stringify(uRow));

  const uUndo = JSON.parse(await ev(`(function(){var b=document.querySelector('#advAudit .adv-mini');b.click();
    var t=document.getElementById('toast');
    return JSON.stringify({toast:t.classList.contains('on')?String(t.textContent||'').trim():'',
      up:state.weeks['8'][dayIds()[0]].exercises[0].load,
      undone:advAuditOf().map(function(b){return b.undone;}).join(','),
      btns:document.querySelectorAll('#advAudit .adv-mini').length,
      led:__uiv.ledgerHash()});})()`));
  T('U4 点审计行「撤销」：那一格逐字节退回原值，批次标成已撤销且撤销按钮收掉',
    uUndo.up === 120 && uUndo.undone === 'true' && uUndo.btns === 0
    && (uUndo.toast || '').indexOf('已撤销') >= 0 && uUndo.led === uLedger0,
    JSON.stringify(uUndo));

  await ev("document.getElementById('advApplyAll').click()"); await settle();
  const uArm = JSON.parse(await ev(`(function(){var a=document.getElementById('advApplyAll');
    return JSON.stringify({txt:String(a.textContent||'').trim(),armed:a.dataset.armed,
      up:state.weeks['8'][dayIds()[0]].exercises[0].load,n:advAuditOf().length});})()`));
  await ev("document.getElementById('advApplyAll').click()"); await settle();
  const uBatch = JSON.parse(await ev(`(function(){return JSON.stringify({
      up:state.weeks['8'][dayIds()[0]].exercises[0].load,
      hard:state.weeks['8'][dayIds()[0]].exercises[1].load,
      dl:state.weeks['8'][dayIds()[0]].exercises[2].load,
      kinds:advAuditOf().map(function(b){return b.kind+':'+b.items.length;}).join(',')});})()`));
  T('U5 批量按钮要连点两下：第一下只把按钮变成「再点一次确认」且不写，第二下才落两笔、减载行仍被拒',
    uArm.txt.indexOf('再点一次') >= 0 && uArm.armed === '1' && uArm.up === 120 && uArm.n === 1
    && uBatch.up === 125 && uBatch.hard === 97.5 && uBatch.dl === 120 && uBatch.kinds.indexOf('batch:2') >= 0,
    '第一下=' + uArm.txt + ' / 第二下 W8=' + uBatch.up + '/' + uBatch.hard + '/' + uBatch.dl + ' 批=' + uBatch.kinds);

  await ev("closeSheet('adviceSheet');openAdviceSheet()"); await settle();
  const uAuto = JSON.parse(await ev(`(function(){var s=document.getElementById('advTier');
    s.value='auto';s.dispatchEvent(new Event('change'));
    return JSON.stringify({tier:advTier(),n:advAuditOf().length,
      kinds:advAuditOf().map(function(b){return b.kind;}).join(','),
      up:state.weeks['8'][dayIds()[0]].exercises[0].load});})()`));
  await ev("openAdviceSheet()"); await settle();
  const uAuto2 = JSON.parse(await ev(`(function(){return JSON.stringify({n:advAuditOf().length,
      at:document.querySelectorAll('#advBody s.at').length});})()`));
  T('U6 切到「自动应用」只按护栏补写：该写的早已到位就一笔不新增，再开一次全是「已到位」',
    uAuto.tier === 'auto' && uAuto.n === 2 && uAuto.up === 125 && uAuto2.n === 2 && uAuto2.at >= 2,
    '切换后批次=' + uAuto.n + ' · 再开后=' + uAuto2.n + ' · 已到位标记=' + uAuto2.at);

  await ev("(function(){var s=document.getElementById('advTier');s.value='off';s.dispatchEvent(new Event('change'));})()");
  await settle();
  const uOff = JSON.parse(await ev(`(function(){return JSON.stringify({tier:advTier(),
      rows:document.querySelectorAll('#advBody tbody tr').length,
      txt:String(document.getElementById('advBody').textContent||'').trim(),
      dis:document.getElementById('advApplyAll').disabled,
      undoDis:document.getElementById('advUndoLast').disabled,
      led:__uiv.ledgerHash()});})()`));
  T('U7 切到「关闭」：表格收成一句说明，批量禁用而撤销仍可用（已经落笔的批次不能被档位锁死）',
    uOff.tier === 'off' && uOff.rows === 0 && uOff.txt.indexOf('关闭') >= 0
    && uOff.dis === true && uOff.undoDis === false && uOff.led !== uLedger0,
    '说明=' + uOff.txt.slice(0, 20) + ' 批量禁用=' + uOff.dis + ' 撤销禁用=' + uOff.undoDis);

  const uGeo = verdict(await measure('adviceSheet'));
  await ev("(function(){var s=document.getElementById('advTier');s.value='confirm';s.dispatchEvent(new Event('change'));})()");
  await settle();
  const uGeo2 = verdict(await measure('adviceSheet'));
  T('U8 写回态几何合格：关闭档的空态与「确认后应用」的按钮态都没有裁切 / 互叠',
    uGeo.ok && uGeo2.ok, (uGeo.detail || '') + (uGeo2.ok ? '' : ' / ' + uGeo2.detail));

  await ev('closeAllSheets()'); await settle();
  await ev(`__uiv.restore(${JSON.stringify(uSnap0)})`); await settle();
  const uBack = await ev('__uiv.snap()');
  const uLedger1 = await ev('__uiv.ledgerHash()');
  T('U9 写回段不留痕：夹具周表、审计与档位全部按段首快照还原，账本哈希回到进段前',
    uBack === uSnap0 && uLedger1 === uLedgerPre,
    '还原相同=' + (uBack === uSnap0) + ' 账本 ' + uLedger1 + ' / 进段前 ' + uLedgerPre);

  /* ---------------- L 段：环境配置（配片库存 / 地点网格）+ 本地配重计算器 ----------------
     P 段已经在四档宽度量过 envSheet / edSheet 的几何，这里只补几何量不到的四件事：
       ① 控件是否真按注册表（PLATES / LC_TYPES / LC_FIELDS / dayIds）长出，而不是抄了个固定数；
       ② 真点下去有没有反应（芯片换亮暗、周下拉换网格、输入框换总重）；
       ③ 写进去的键清没清干净（清空地点要删键，不能留空字符串占账本）；
       ④ 环境项与计算器有没有漏进导出面。
     togglePlateKg 动 prefs 分片、setDayLoc 动 workout 分片，所以和 M / U 一样按段首快照
     整体还原，交给 K1/K2 复核「遍历不留痕」。 */
  SECT.s = 'L';
  await rawSend('Emulation.setDeviceMetricsOverride', { width: 412, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
  await ev('closeAllSheets()'); await settle();
  const lSnap0 = await ev('__uiv.snap()');
  const lLedPre = await ev('__uiv.ledgerHash()');
  const lStorePre = await ev('__uiv.storeHash()');

  await call('openEnvSheet'); await settle();
  /* 库存归场地后，「这块片在不在场」= inventory.plates 里有没有那个键：
     旧版用 have:null 表示全套以省字节，现在键就是事实本体，所以核对的是键数而不是 null 简写。 */
  const lChips = JSON.parse(await ev(`(function(){
    var c=document.querySelectorAll('#envPlates .ps-chip');
    return JSON.stringify({n:c.length,on:document.querySelectorAll('#envPlates .ps-chip.on').length,
      want:PLATES.length,kg0:PLATES[0].kg,first:c.length?String(c[0].textContent).trim():'',
      stock:plateStock().length,keys:Object.keys(venueInv().plates).length,
      cfg:state.plateCfg?'(还有 plateCfg)':'(无 plateCfg)'});})()`));
  T('L1 库存芯片按 PLATES 现读数长出（' + lChips.want + ' 片）：默认全亮、点亮数=库存片数、场地键数一致、旧全局键已退役',
    lChips.n === lChips.want && lChips.on === lChips.want && lChips.stock === lChips.want
    && lChips.first === String(lChips.kg0) && lChips.keys === lChips.want && lChips.cfg === '(无 plateCfg)',
    '芯片 ' + lChips.n + ' 亮 ' + lChips.on + ' 库存 ' + lChips.stock + ' keys=' + lChips.keys + ' ' + lChips.cfg);

  const lTap = JSON.parse(await ev(`(function(){
    function chip(){return document.querySelector('#envPlates .ps-chip');}   /* 每次重新取：点一下整块 innerHTML 会重建 */
    var kg=PLATES[0].kg;
    chip().click();
    var cut={on:document.querySelectorAll('#envPlates .ps-chip.on').length,press:String(chip().getAttribute('aria-pressed')),
      stock:plateStock().length,has:plateOn(kg),keys:Object.keys(venueInv().plates).length,led:__uiv.ledgerHash()};
    chip().click();
    var back={on:document.querySelectorAll('#envPlates .ps-chip.on').length,press:String(chip().getAttribute('aria-pressed')),
      stock:plateStock().length,has:plateOn(kg),keys:Object.keys(venueInv().plates).length};
    return JSON.stringify({kg:kg,cut:cut,back:back});})()`));
  T('L2 真点库存芯片可逆：点掉最大片即少一片少一键、aria-pressed 落 false、账本一字未动；点回来键数回满',
    lTap.cut.on === lTap.back.on - 1 && lTap.cut.press === 'false' && lTap.cut.has === false
    && lTap.cut.stock === lTap.back.stock - 1 && lTap.cut.led === lLedPre
    && lTap.cut.keys === lChips.want - 1
    && lTap.back.on === lChips.want && lTap.back.press === 'true' && lTap.back.has === true
    && lTap.back.keys === lChips.want, JSON.stringify(lTap));

  for (const w of WIDTHS) {
    SECT.s = 'L ' + w;
    await rawSend('Emulation.setDeviceMetricsOverride', { width: w, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
    await ev('closeAllSheets()'); await settle();
    await call('openEnvSheet'); await settle();
    const lBox = JSON.parse(await ev(`(function(){
      function vis(e){var r=e.getBoundingClientRect();
        return r.width>=1&&r.height>=1&&getComputedStyle(e).display!=='none'&&getComputedStyle(e).visibility!=='hidden';}
      var ch=document.querySelectorAll('#envPlates .ps-chip'),cv=0,i;
      for(i=0;i<ch.length;i++){ if(vis(ch[i])) cv++; }
      var inp=document.querySelectorAll('#envLocGrid .loc-in'),iv=0,nw=9999;
      for(i=0;i<inp.length;i++){ if(vis(inp[i])){ iv++; var bw=inp[i].getBoundingClientRect().width; if(bw<nw) nw=bw; } }
      var ps=document.getElementById('envPlates'),lg=document.getElementById('envLocGrid');
      return JSON.stringify({chips:ch.length,cv:cv,inputs:inp.length,iv:iv,nw:Math.round(nw),
        days:dayIds().length,psOvf:ps?(ps.scrollWidth-ps.clientWidth):-1,lgOvf:lg?(lg.scrollWidth-lg.clientWidth):-1});})()`));
    T('L3 ' + w + 'px 两块新面长齐：库存芯片 ' + lBox.chips + ' 个全可见、地点输入 ' + lBox.inputs
      + ' 格最窄 ' + lBox.nw + 'px、两处都不横向滚动',
      lBox.chips === lChips.want && lBox.cv === lBox.chips && lBox.inputs === lBox.days
      && lBox.iv === lBox.days && lBox.nw >= 48 && lBox.psOvf <= 1 && lBox.lgOvf <= 1, JSON.stringify(lBox));
  }
  await rawSend('Emulation.setDeviceMetricsOverride', { width: 412, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
  await ev('closeAllSheets()'); await call('openEnvSheet'); await settle();

  const lWeek = JSON.parse(await ev(`(function(){
    var ws=activeWeekNums(),a=+state.week,b=ws.filter(function(x){return x!==a;})[0];
    var sel=document.getElementById('envLocWeek'),before=String(sel.value);
    if(b==null) return JSON.stringify({err:'活动周不足两周：'+ws.join('/')});
    sel.value=String(b); sel.dispatchEvent(new Event('change'));
    var cells=[],n=document.querySelectorAll('#envLocGrid .loc-in'),i;
    for(i=0;i<n.length;i++) cells.push(n[i].getAttribute('data-locw'));
    return JSON.stringify({a:a,b:b,before:before,cur:String(_envLocWeek),n:cells.length,days:dayIds().length,
      uniq:cells.filter(function(x,i){return cells.indexOf(x)===i;}).join(','),led:__uiv.ledgerHash()});})()`));
  T('L4 周下拉真的驱动地点网格：换档后每格 data-locw 全跟到新周、_envLocWeek 同步，换周本身一个字节都不写',
    !lWeek.err && lWeek.n === lWeek.days && lWeek.uniq === String(lWeek.b) && lWeek.cur === String(lWeek.b)
    && lWeek.before !== String(lWeek.b) && lWeek.led === lLedPre,
    lWeek.err || ('起点周=' + lWeek.before + ' 选到 W' + lWeek.b + ' 格标=' + lWeek.uniq + ' 变量=' + lWeek.cur + ' 账本同=' + (lWeek.led === lLedPre)));

  const lLoc = JSON.parse(await ev(`(function(){
    var w=state.week,d=state.day,TXT='L段铁馆A区';
    var sel=document.getElementById('envLocWeek'); sel.value=String(w); sel.dispatchEvent(new Event('change'));
    function cell(){return document.querySelector('#envLocGrid .loc-in[data-locw="'+w+'"][data-locd="'+d+'"]');}
    var e0=cell(); if(!e0) return JSON.stringify({err:'缺本周(W'+w+')本日('+d+')的地点输入格，网格标的是 W'+_envLocWeek});
    e0.value=TXT; e0.dispatchEvent(new Event('change'));
    var line=document.getElementById('locLine');
    var o={w:w,d:d,wk:String(_envLocWeek),got:dayLoc(w,d),txt:String(line.textContent||'').trim(),
      disp:getComputedStyle(line).display,led:__uiv.ledgerHash(),
      colsHead:(function(){try{return CSV_COLS.join('|');}catch(e){return 'THREW '+e.message;}})(),
      csv:(function(){try{return exportUnifiedCsv();}catch(e){return 'THREW '+e.message;}})(),
      plan:(function(){try{return JSON.stringify(xStateToPlanDict(state));}catch(e){return 'THREW '+e.message;}})(),
      cols:CSV_COLS.length,TXT:TXT};
    var e1=cell(); e1.value=''; e1.dispatchEvent(new Event('change'));
    o.after=String(line.textContent||'').trim();
    o.afterDisp=getComputedStyle(line).display;
    o.keyGone=Object.keys(state.weeks[String(w)][d]).indexOf('loc')<0;
    o.held=JSON.stringify(state.weeks[String(w)][d]).indexOf(TXT)<0;
    return JSON.stringify(o);})()`));
  T('L5 地点真填真清：输入即落 dayLoc、主屏 #locLine 显出来；清空后行对象里连 loc 键都删掉、那一行收回 display:none',
    !lLoc.err && lLoc.wk === String(lLoc.w) && lLoc.got === lLoc.TXT && lLoc.txt.indexOf(lLoc.TXT) >= 0
    && lLoc.disp !== 'none' && lLoc.after === '' && lLoc.afterDisp === 'none'
    && lLoc.keyGone === true && lLoc.held === true,
    lLoc.err || ('网格周=W' + lLoc.wk + ' / 主屏行=' + JSON.stringify(lLoc.txt) + ' / 清空后残留 loc 键=' + (!lLoc.keyGone)));
  T('L6 地点不漏进导出面：填着地名时 CSV 仍是 ' + lLoc.cols + ' 列、26 个列名里无 loc，CSV 与六表工作簿文本都搜不到这个地名',
    lLoc.cols === 26 && lLoc.csv.indexOf('THREW') < 0 && lLoc.plan.indexOf('THREW') < 0
    && lLoc.csv.indexOf(lLoc.TXT) < 0 && lLoc.plan.indexOf(lLoc.TXT) < 0
    && lLoc.colsHead.indexOf('loc') < 0,
    'CSV 命中=' + (lLoc.csv.indexOf(lLoc.TXT) >= 0) + ' 工作簿命中=' + (lLoc.plan.indexOf(lLoc.TXT) >= 0)
    + ' 列数=' + lLoc.cols);

  await ev('closeAllSheets()'); await settle();
  await call('openToolLoad', []); await settle();
  const lKeys = JSON.parse(await ev('JSON.stringify(LC_TYPES.map(function(t){return t.k;}))'));
  const lTypeBad = [], lTypeSeen = [];
  for (const k of lKeys) {
    /* 自重三类与手动类的默认值都是 0（体重取当日/档案，无头环境里就是 0），
       所以这里真的把该填的格填上再看总重——「填了才算得出」本身就是这条要钉的行为。 */
    await ev("(function(){var s=document.getElementById('toolLoadType');s.value=" + JSON.stringify(k)
      + ";s.dispatchEvent(new Event('change'));})()");
    await settle();
    const st = JSON.parse(await ev(`(function(){
      function put(fk,v){var e=document.querySelector('#toolLoadBody [data-lc="'+fk+'"]');if(!e)return 0;
        e.value=String(v);e.dispatchEvent(new Event('input'));return 1;}
    var touched=put('bw',80)+put('manual',72.5);
      return JSON.stringify({sel:_lcType,f:String(document.getElementById('toolLoadFormula').textContent||'').trim().length,
        ins:document.querySelectorAll('#toolLoadBody .lc-in').length,flds:document.querySelectorAll('#toolLoadBody .lc-fld').length,
        tot:lcTotal(),
        out:String(document.getElementById('toolLoadOut').textContent||'').trim(),touched:touched});})()`));
    const g = verdict(await measure('toolLoadSheet'));
    lTypeSeen.push(k + '(' + st.flds + '格/' + st.tot + 'kg)');
    if (!(st.sel === k && st.f > 0 && st.ins >= 1 && st.ins === st.flds && st.tot > 0
        && st.out.indexOf('kg') > 0 && g.ok)) {
      lTypeBad.push(k + ' ' + JSON.stringify(st) + (g.detail ? ' || ' + g.detail : ''));
    }
  }
  T('L7 六类器械逐档真点（' + lKeys.length + ' 档）：选中标的与档位一致、公式非空、每块字段配一个输入、总重>0、toolLoadSheet 几何合格',
    lKeys.length === 6 && lTypeBad.length === 0, lTypeBad.join(' ; ') || lTypeSeen.join(' → '));

  const lCount = JSON.parse(await ev(`(function(){
    function pick(k){var s=document.getElementById('toolLoadType');s.value=k;s.dispatchEvent(new Event('change'));}
    function rows(fk){return document.querySelectorAll('#toolLoadBody [data-lcper="'+fk+'"]').length;}
    function put(fk,v){var e=document.querySelector('#toolLoadBody [data-lc="'+fk+'"]');
      e.value=String(v);e.dispatchEvent(new Event('input'));}
    pick('stack'); var sb=rows('pins'); put('stacks',LC_FIELDS.stacks.max); var sa=rows('pins');
    var sf=document.querySelectorAll('#toolLoadBody .lc-fld').length;
    pick('loaded'); var ab=rows('armKg'); put('arms',LC_FIELDS.arms.max); var aa=rows('armKg');
    return JSON.stringify({sb:sb,sa:sa,smax:LC_FIELDS.stacks.max,amax:LC_FIELDS.arms.max,
      cnt:lcCount('stacks'),sf:sf,ab:ab,aa:aa,acnt:lcCount('arms')});})()`));
  await settle();
  T('L8 计数型字段真的重排逐档输入：插片类栈数与挂片类杆数改到 LC_FIELDS 上限，插销/每杆格数跟到同数',
    lCount.sb === 1 && lCount.sa === lCount.smax && lCount.cnt === lCount.smax && lCount.sf > lCount.sa
    && lCount.aa === lCount.amax && lCount.acnt === lCount.amax && lCount.ab < lCount.aa,
    JSON.stringify(lCount));

  const lClamp = JSON.parse(await ev(`(function(){
    var s=document.getElementById('toolLoadType');s.value='bwassist';s.dispatchEvent(new Event('change'));
    function put(fk,v){var e=document.querySelector('#toolLoadBody [data-lc="'+fk+'"]');
      e.value=String(v);e.dispatchEvent(new Event('input'));}
    put('bw',60);put('coef',1);put('assist',90);
    var a={tot:lcTotal(),
      out:String(document.getElementById('toolLoadOut').textContent||'').trim()};
    put('assist',10);
    var b={tot:lcTotal()};
    return JSON.stringify({a:a,b:b});})()`));
  await settle();
  T('L9 自重辅助不出负总重：辅助超过体重×系数时钳到 0、输出显示 0；缩回辅助又算得出正数',
    lClamp.a.tot === 0 && lClamp.a.out.indexOf('0') >= 0 && lClamp.b.tot === 50,
    '辅助 90：' + JSON.stringify(lClamp.a) + ' / 辅助 10：' + JSON.stringify(lClamp.b));

  const lFill0 = await ev('__uiv.ledgerHash()');
  const lFill = JSON.parse(await ev(`(function(){
    var s=document.getElementById('toolLoadType');s.value='manual';s.dispatchEvent(new Event('change'));
    var e=document.querySelector('#toolLoadBody [data-lc="manual"]');e.value='72.5';e.dispatchEvent(new Event('input'));
    var led0=__uiv.ledgerHash();
    return JSON.stringify({led0:led0,led1:__uiv.ledgerHash(),
      tot:lcTotal(),out:String(document.getElementById('toolLoadOut').textContent||'').trim()});})()`));
  await settle();
  T('L10 配片计算器只算不写盘：改输入后账本哈希一字未改、输出跟着重算',
    lFill.led0 === lFill.led1 && lFill.led1 === lFill0 && lFill.tot === 72.5 && lFill.out.indexOf('72.5') >= 0,
    '账本同=' + (lFill.led1 === lFill0) + ' / tot=' + lFill.tot + ' / out「' + lFill.out + '」');

  await ev("(function(){var e=document.querySelector('#toolLoadBody [data-lc=\"manual\"]');e.value='137.5';e.dispatchEvent(new Event('input'));})()");
  await ev('closeAllSheets()'); await settle();
  await call('openToolLoad', []); await settle();
  const lFresh = JSON.parse(await ev(`(function(){
    return JSON.stringify({type:_lcType,first:LC_TYPES[0].k,manual:_lcVal.manual,
      pins:(_lcVal.pins||[])[0],plateKg:_lcVal.plateKg,stacks:_lcVal.stacks,base:_lcVal.base,
      dPins:LC_FIELDS.pins.def,dPlate:LC_FIELDS.plateKg.def,dStacks:LC_FIELDS.stacks.def,dBase:LC_FIELDS.base.def,dManual:LC_FIELDS.manual.def,
      tot:lcTotal(),sel:document.getElementById('toolLoadType').value});})()`));
  /* 期望总重按 LC_FIELDS 现算（基数 + 插销档 × 每片），不抄 12.5：默认值一改，抄死的数字就变成假通过 */
  T('L11 计算器不跨次留参：脏过手动总重后重开计算器，档位退回第一类、每格退回 LC_FIELDS 默认、下拉与模块变量一致',
    lFresh.type === lFresh.first && lFresh.sel === lFresh.type
    && Number(lFresh.manual) === Number(lFresh.dManual)
    && Number(lFresh.pins) === Number(lFresh.dPins) && Number(lFresh.plateKg) === Number(lFresh.dPlate)
    && Number(lFresh.stacks) === Number(lFresh.dStacks) && Number(lFresh.base) === Number(lFresh.dBase)
    && lFresh.tot === Number(lFresh.dBase) + Number(lFresh.dPins) * Number(lFresh.dPlate), JSON.stringify(lFresh));

  await ev('closeAllSheets()'); await settle();
  await new Promise(r => setTimeout(r, 200));
  await ev(`__uiv.restore(${JSON.stringify(lSnap0)})`); await settle();
  const lBack = await ev('__uiv.snap()');
  const lLed1 = await ev('__uiv.ledgerHash()');
  const lStore1 = await ev('__uiv.storeHash()');
  const lOpen = await ev('__uiv.anyOpen()');
  T('L12 环境段不留痕：库存与地点按段首快照还原后逐字节相同、四路分片哈希回到进段前、面板全部收起',
    lBack === lSnap0 && lLed1 === lLedPre && lStore1 === lStorePre && lOpen === false,
    '还原相同=' + (lBack === lSnap0) + ' 账本同=' + (lLed1 === lLedPre)
    + ' 分片同=' + (lStore1 === lStorePre) + ' 仍开着=' + lOpen);

  /* ---------------- R 段：阈值回测的「有账」形状 ----------------
     P 段量到的 calibSheet 是出厂空账状态——那只有空态一个 div，表的几何根本没被量过。
     这里在段内给内置模板的第 2、3 周补上真实账（完成率 / 实 RPE），让它渲染出 11 行 ×
     最多 4 个候选的真表，再按四档里最窄的两档量：
       · 数据格（td）自己也算溢出对象——uiv 原先只量「可点元素」，这正是审计里
         「图表格子里的字被裁掉没人知道」那个盲区，v0.29 会把它推广到全部面板，
         这一段先把最容易撑爆的新表管住；
       · 正文里不许漏出 NaN / undefined / Infinity；
     段末整份还原，交给 K1/K2 复核不留痕。 */
  SECT.s = 'R';
  await rawSend('Emulation.setDeviceMetricsOverride', { width: 412, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
  await ev('closeAllSheets()'); await settle();
  const rSnap0 = await ev('__uiv.snap()');
  const rLedPre = await ev('__uiv.ledgerHash()');
  const rStorePre = await ev('__uiv.storeHash()');
  const rSeed = JSON.parse(await ev(`(function(){
    var rec=function(wn){
      var wk=state.weeks[String(wn)], n=0;
      if(!wk) return 0;
      Object.keys(wk).forEach(function(d){
        ((wk[d]||{}).exercises||[]).forEach(function(e,i){
          var pr=prescriptionOf(e), st=(+pr.sets||1), rp=(+pr.reps||1), tr=(+e.targetRpe||7);
          e.doneSets=(i%3===2)?Math.max(1,Math.floor(st/2)):st;
          e.done=e.doneSets>=st;
          e.reps=(i%3===0)?rp:Math.max(1,rp-1);
          e.targetRpe=tr;
          e.rpe=(i%4===0)?Math.max(1,tr-1):((i%4===1)?tr:((i%4===2)?tr+0.8:9.8));
          n++;
        });
      });
      return n;
    };
    return JSON.stringify({w2:rec(2),w3:rec(3),params:calibParamKeys().length});})()`));
  await call('openCalibSheet'); await settle();
  const rShape = JSON.parse(await ev(`(function(){
    var tb=document.querySelector('#calibBody table.calib-table');
    var body=document.getElementById('calibBody');
    var t=(body?body.textContent:'');
    var dirty=['NaN','undefined','Infinity'].filter(function(s){ return t.indexOf(s)>=0; });
    return JSON.stringify({
      rows:tb?tb.querySelectorAll('tbody tr').length:-1,
      th:tb?tb.querySelectorAll('thead th').length:-1,
      cand:document.querySelectorAll('#calibBody .cal-cand').length,
      empty:document.querySelectorAll('#calibBody .log-empty').length,
      stat:(document.getElementById('calibStat')||{}).textContent||'',
      dirty:dirty.join(','),
      pct:(document.getElementById('calibStat')||{}).textContent.indexOf('%')>=0});})()`));
  T('R1 记满相邻两周后，空态换成真表：行数=契约参数字典数、表头 ' + rShape.th + ' 列、候选格非空、汇总行给出命中率',
    rSeed.w2 > 0 && rSeed.w3 > 0 && rShape.empty === 0 && rShape.rows === rSeed.params && rShape.th === 4
    && rShape.cand >= rShape.rows && rShape.dirty === '' && rShape.pct === true && rShape.stat.length > 8,
    '行 ' + rShape.rows + '/' + rSeed.params + ' 列头 ' + rShape.th + ' 候选 ' + rShape.cand
    + ' 空态 ' + rShape.empty + ' 脏词=' + (rShape.dirty || '无') + ' 汇总=' + rShape.stat.slice(0, 46));

  for (const w of [320, 412]) {
    SECT.s = 'R ' + w;
    await rawSend('Emulation.setDeviceMetricsOverride', { width: w, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
    await settle();
    const rBox = JSON.parse(await ev(`(function(){
      var p=document.querySelector('#calibSheet .panel');
      var wrap=document.querySelector('#calibBody .log-wrap');
      var tb=document.querySelector('#calibBody table.calib-table');
      if(!p||!wrap||!tb) return JSON.stringify({miss:1});
      var vw=window.innerWidth, vh=window.innerHeight;
      var pr=p.getBoundingClientRect(), wr=wrap.getBoundingClientRect();
      var td=tb.querySelectorAll('td'), cells=td.length, clipped=[], narrow=0, i;
      for(i=0;i<cells;i++){
        var e=td[i], r=e.getBoundingClientRect();
        if(e.scrollWidth>e.clientWidth+1) clipped.push((e.textContent||'').slice(0,10)+' '+e.scrollWidth+'/'+e.clientWidth);
        if(r.width<24) narrow++;
      }
      return JSON.stringify({cells:cells,clipped:clipped.slice(0,3).join(' ; '),nNarrow:narrow,
        wrapOvf:wrap.scrollWidth-wrap.clientWidth,
        inView:pr.left>=-0.5&&pr.right<=vw+0.5&&pr.top>=-0.5&&pr.bottom<=vh+0.5,
        wrapInView:wr.left>=-0.5&&wr.right<=vw+0.5,
        docOvf:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-vw});})()`));
    T('R2 ' + w + 'px 下整张回测表画得进去：' + rBox.cells + ' 个数据格无一横向裁切、表体在滚动容器里不越界、'
      + '面板四边在视口内、整页不横滚（数据格也量，不只量按钮）',
      rBox.miss !== 1 && rBox.clipped === '' && rBox.wrapOvf <= 1 && rBox.inView === true
      && rBox.wrapInView === true && rBox.docOvf <= 1 && rBox.nNarrow === 0, JSON.stringify(rBox));
  }
  await rawSend('Emulation.setDeviceMetricsOverride', { width: 412, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
  await ev('closeAllSheets()'); await settle();
  await new Promise(r => setTimeout(r, 200));
  await ev(`__uiv.restore(${JSON.stringify(rSnap0)})`); await settle();
  const rBack = await ev('__uiv.snap()');
  const rLed1 = await ev('__uiv.ledgerHash()');
  const rStore1 = await ev('__uiv.storeHash()');
  const rOpen = await ev('__uiv.anyOpen()');
  T('R3 回测段不留痕：补进去的两周账目还原后 state 逐字节相同、账本与四路分片哈希回到进段前、面板收起',
    rBack === rSnap0 && rLed1 === rLedPre && rStore1 === rStorePre && rOpen === false,
    '还原相同=' + (rBack === rSnap0) + ' 账本同=' + (rLed1 === rLedPre)
    + ' 分片同=' + (rStore1 === rStorePre) + ' 仍开着=' + rOpen);

  /* ---------------- N 段：把结构撑到契约上限，看这份 UI 还站不站得住 ----------------
     内置那份 8 周 2 Block 只是随种子出厂的模板，不是模型上限（契约 capacity 段就这么说）。
     在此之前每一段都跑在 8 周 4 日上：时间轴编译、周导航、状态矩阵、每张面板的循环渲染
     在 52 周 × 16 Block × 6 日底下走的是同一段代码的另一条路径，从来没被真点过。
     这一段全程只动内存（applyStructure 不写盘），出段按段首快照还原，K1/K2 兜底。 */
  SECT.s = 'N';
  const nSnap0 = await ev('__uiv.snap()');
  const nLed0 = await ev('__uiv.ledgerHash()');
  const nStore0 = await ev('__uiv.storeHash()');
  await ev('closeAllSheets()'); await settle();
  const nB = JSON.parse(await ev('__uiv.extremeBuild()'));
  await settle();
  T('N1 结构撑到契约上限：三个上限全从契约现取，时间轴、块数、训练日与账本周片跟着长齐',
    !nB.bad && Number(nB.timeline) === Number(nB.maxW) && Number(nB.blocks) === Number(nB.maxB)
    && Number(nB.days) === Number(nB.maxD) && Number(nB.weeks) === Number(nB.maxW),
    nB.bad || ('契约上限 周 ' + nB.maxW + ' · 块 ' + nB.maxB + ' · 日 ' + nB.maxD
      + '（周期预设 ' + nB.pres + ' 种轮着用）→ 实撑出 时间轴 ' + nB.timeline + ' 周 / '
      + nB.blocks + ' 块 / 训练日 [' + nB.dayIds + '] / 账本 ' + nB.weeks + ' 周片'));
  const nW = JSON.parse(await ev('__uiv.extremeWalk()'));
  T('N2 极端结构下主屏逐周逐日真遍历（首·中·末三档 × 每个训练日）：屏屏都画得出、不画脏词、不横滚、不叠面板',
    nW.bad === '无' && Number(nW.n) === Number(nW.expect),
    '周 [' + nW.weeks + '] × 日 [' + nW.days + '] 实走 ' + nW.n + '/' + nW.expect + ' 屏 / 问题=' + nW.bad
    + ' / 进度串=' + String(nW.prog).slice(0, 32));
  const nBad = [];
  let nSlow = { id: '-', ms: 0 };
  for (const p of PANELS) {
    await ev('closeAllSheets()'); await settle();
    const t0 = Date.now();
    await call(p.open, p.args); await settle();
    const ms = Date.now() - t0;
    if (ms > nSlow.ms) nSlow = { id: p.id, ms };
    const on = await ev(`document.getElementById(${JSON.stringify(p.id)}).classList.contains('on')?1:0`);
    const g = verdict(await measure(p.id));
    const dz = JSON.parse(await ev('__uiv.dirtyIn(' + JSON.stringify(p.id) + ')'));
    const keys = Object.keys(dz.hits || {});
    if (on !== 1) nBad.push(p.id + ' 开不起来');
    if (!g.ok) nBad.push(p.id + ' ' + g.detail);
    if (keys.length) nBad.push(p.id + ' 画脏词于 ' + keys.slice(0, 2).join(','));
  }
  T('N3 极端结构下 ' + PANELS.length + ' 张面板逐一真开：全部开对、几何合格（裁切·互叠·越界）、面板内零脏词',
    nBad.length === 0, nBad.join(' / ')
    || ('最慢 ' + nSlow.id + ' ' + nSlow.ms + 'ms（含等待渲染）/ 脏词节点 0 个'));
  await ev('closeAllSheets()'); await settle();
  await new Promise(r => setTimeout(r, 200));
  await ev(`__uiv.restore(${JSON.stringify(nSnap0)})`); await settle();
  const nBack = await ev('__uiv.snap()');
  const nOpen = await ev('__uiv.anyOpen()');
  const nLed1 = await ev('__uiv.ledgerHash()');
  const nStore1 = await ev('__uiv.storeHash()');
  T('N4 撑到上限这一段不留痕：还原后 state 逐字节相同、账本与四路分片哈希回到进段前、面板收起',
    nBack === nSnap0 && nLed1 === nLed0 && nStore1 === nStore0 && nOpen === false,
    '还原相同=' + (nBack === nSnap0) + ' 账本同=' + (nLed1 === nLed0)
    + ' 分片同=' + (nStore1 === nStore0) + ' 仍开着=' + nOpen);
  /* G12：320dp 窄屏下工具区三卡并排不越界、RPE<5 提示行不横向裁切 */
  await rawSend('Emulation.setDeviceMetricsOverride', { width: 320, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
  await settle();
  await ev('closeAllSheets()');
  await ev('openSettings()'); await settle();
  await ev("(function(){var c=document.getElementById('setToolsCard'); if(c) c.classList.remove('collapsed');})()");
  await settle();
  const g12 = JSON.parse(await ev(`(function(){
    var grid=document.getElementById('setToolsBody');
    var cards=document.querySelectorAll('#setToolsBody .set-tool-card');
    var vw=window.innerWidth, minW=9999, out=0, ovf=0, i;
    for(i=0;i<cards.length;i++){ var r=cards[i].getBoundingClientRect();
      if(r.width<minW) minW=r.width; if(r.right>vw+0.5||r.left<-0.5) out++; }
    if(grid) ovf=grid.scrollWidth-grid.clientWidth;
    return JSON.stringify({n:cards.length,minW:Math.round(minW*10)/10,ovf:ovf,out:out,
      doc:Math.max(document.documentElement.scrollWidth,window.innerWidth)-vw});})()`));
  await ev('openEditor(0)'); await settle();
  await ev("(function(){var i=document.getElementById('edRpe'); if(i){i.value='4.5'; refreshConsole();}})()"); await settle();
  const g12b = JSON.parse(await ev(`(function(){
    var n=document.getElementById('edRpeNote'), b=n&&n.parentNode, r=n?n.getBoundingClientRect():null;
    return JSON.stringify({txt:(n&&n.textContent)||'', ovf:n?n.scrollWidth-n.clientWidth:0,
      boxOvf:b?b.scrollWidth-b.clientWidth:0, inView:r?r.right<=window.innerWidth+0.5:false});})()`));
  T('G12 320px 下工具区三卡不越界、RPE 提示行不裁切也不撑破输入框容器',
    g12.n === 3 && g12.minW >= 84 && g12.ovf <= 1 && g12.out === 0 && g12.doc <= 1
    && g12b.txt.indexOf('低于 5') >= 0 && g12b.ovf <= 1 && g12b.boxOvf <= 1 && g12b.inView === true,
    JSON.stringify(g12) + ' / ' + JSON.stringify(g12b));
  await ev('closeAllSheets()');
  await rawSend('Emulation.setDeviceMetricsOverride', { width: 412, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
  await settle();
  await ev(`__uiv.restore(${JSON.stringify(nSnap0)})`); await settle();

  /* ---------------- Dk 段：底部日卡不被长日名撑出屏 ---------------- */
  SECT.s = 'Dk';
  await rawSend('Emulation.setDeviceMetricsOverride', { width: 360, height: HEIGHT, deviceScaleFactor: 1, mobile: true });
  await ev('closeAllSheets()'); await settle();
  const dkFit = JSON.parse(await ev(`(function(){
    var bs=document.querySelectorAll('#dock button'),vw=innerWidth,bad=[],i,r;
    for(i=0;i<bs.length;i++){ r=bs[i].getBoundingClientRect();
      if(r.right>vw+1||r.left<-1||r.width<40) bad.push(i+':'+Math.round(r.left)+'-'+Math.round(r.right)+'/'+Math.round(r.width)); }
    return JSON.stringify({n:bs.length,vw:vw,bad:bad});})()`));
  T('Dk1 360px 底部日卡全在屏内：长日名不得把按钮撑出屏（周五/周六/GPP 必须点得到）',
    dkFit.n >= 3 && dkFit.bad.length === 0,
    '按钮 ' + dkFit.n + ' 个 / 越界 ' + (dkFit.bad.join(',') || '无'));

  /* ---------------- K 段：整轮遍历不留痕 ---------------- */
  SECT.s = 'K';
  await new Promise(r => setTimeout(r, 600));            // 等可能的防抖写盘落地，别让「晚到的写」骗过断言
  const store1 = await ev('__uiv.storeHash()');
  T('K1 四路分片（prefs/workout/lib/archive）遍历前后逐字节同', store0 === store1,
    store0 === store1 ? '四片哈希一致' : '分片漂移：' + store0 + ' → ' + store1);
  const ledger1 = await ev('__uiv.ledgerHash()');
  T('K2 账本域（weeks/structure/jts/e1rmLog/aux/profile）一字未改', ledger0 === ledger1,
    ledger0 === ledger1 ? ledger1 : ('前 ' + ledger0 + ' 后 ' + ledger1));
  T('K3 全程无未捕获异常（Runtime.exceptionThrown 计数为 0）', pageErrors.length === 0,
    pageErrors.length ? pageErrors.slice(0, 3).join(' | ') : '0 条');

  SECT.s = 'Z1';
  /* 这条自己也占一项，所以比较的是「即将落账的条数」 */
  T('Z1 断言总数无漂移（实到 ' + (PASS + FAIL + 1) + '，应 ' + EXP_N + '）', (PASS + FAIL + 1) === EXP_N,
    (PASS + FAIL + 1) === EXP_N ? 'OK' : '实到 ' + (PASS + FAIL + 1) + ' 应 ' + EXP_N);

  for (const l of LINES) console.log(l);
  console.log('\n== uiv 汇总: ' + PASS + ' PASS / ' + FAIL + ' FAIL （共 ' + (PASS + FAIL) + ' 项）==');
  if (FAIL) console.log('未通过：' + LINES.filter(l => l.startsWith('FAIL')).length + ' 条，见上');
  await tmpclean.close(chrome, tmp, FAIL > 0);
  process.exit(FAIL > 0 ? 1 : 0);
}
main().catch(async (e) => {
  LINES.push('FAIL  Z0 断言块在 ' + SECT.s + ' 段中途抛错（其后断言未执行）  [' + (e && e.message ? e.message : e) + ']');
  for (const l of LINES) console.log(l);
  console.error(e && e.stack ? ('Z0 现场栈：\n' + e.stack) : e);
  console.log('\n== uiv 汇总: ' + PASS + ' PASS / ' + (FAIL + 1) + ' FAIL （共 ' + (PASS + FAIL + 1) + ' 项，中断）==');
  if (chrome) await tmpclean.close(chrome, tmp, true);
  process.exit(1);
});
