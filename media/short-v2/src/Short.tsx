import React from 'react';
import {AbsoluteFill,Audio,Img,OffthreadVideo,Sequence,staticFile,useCurrentFrame,useVideoConfig,interpolate,spring,Easing,continueRender,delayRender} from 'remotion';
import vo from '../public/vo.json';

// ---------------------------------------------------------------- timing
export const FPS=30;
const L:Record<string,{start:number;end:number;words:{w:string;s:number;e:number}[]}>={};
for(const l of vo.lines)L[l.key]=l as any;
const f=(s:number)=>Math.round(s*FPS);
export const TOTAL=f(vo.duration+1.6);
// scene boundaries: each scene starts a hair before its line
const CUT={
  hook:0, bits:f(L.bits.start-.12), milled:f(L.milled.start-.1), pcbway:f(L.pcbway.start-.05),
  layers:f(L.layers.start-.1), holes:f(L.holes.start-.08), silk:f(L.silk.start-.08), pi:f(L.pi.start-.1),
  rip:f(L.rip.start+.25), result:f(L.result.start-.1), end:f(L.end.start-.15), done:TOTAL,
};
const order=['hook','bits','milled','pcbway','layers','holes','silk','pi','rip','result','end','done'] as const;
const dur=(k:typeof order[number])=>CUT[order[order.indexOf(k)+1]]-CUT[k];

// ---------------------------------------------------------------- style
export const GREEN='#7CF29A',COPPER='#F0A06A',RED='#FF4D4D',INK='#F4F7F5';
export const fontCss=`
@font-face{font-family:'Pop';src:url('${staticFile('fonts/Poppins-Bold.ttf')}');font-weight:700}
@font-face{font-family:'Pop';src:url('${staticFile('fonts/Poppins-SemiBold.ttf')}');font-weight:600}
@font-face{font-family:'Plex';src:url('${staticFile('fonts/PlexMono-Medium.ttf')}');font-weight:500}`;
export const useFonts=()=>{
  const [h]=React.useState(()=>delayRender('fonts'));
  React.useEffect(()=>{(document as any).fonts.ready.then(()=>{
    Promise.all([(document as any).fonts.load("700 40px Pop"),(document as any).fonts.load("500 40px Plex")]).then(()=>continueRender(h));
  });},[h]);
};
export const pop:React.CSSProperties={fontFamily:'Pop',fontWeight:700,color:INK,letterSpacing:-1};
export const mono:React.CSSProperties={fontFamily:'Plex',fontWeight:500,color:GREEN,letterSpacing:1};
export const shadow='0 6px 30px rgba(0,0,0,.65), 0 2px 6px rgba(0,0,0,.6)';

export const ease=(fr:number,a:number,b:number,from=0,to=1,e=Easing.bezier(.22,1,.36,1))=>interpolate(fr,[a,b],[from,to],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:e});

// ---------------------------------------------------------------- building blocks
export const Vignette:React.FC<{strength?:number}>=({strength=.55})=>(
  <AbsoluteFill style={{background:`radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 45%, rgba(0,0,0,${strength}) 100%)`}}/>
);
export const Grain:React.FC=()=>{
  const fr=useCurrentFrame();
  return <AbsoluteFill style={{opacity:.07,mixBlendMode:'overlay',backgroundImage:`url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' seed='${fr%7}'/></filter><rect width='300' height='300' filter='url(%23n)'/></svg>")`}}/>;
};
// Ken Burns on a still: from/to = [scale, x%, y%] (object-position)
export const KB:React.FC<{src:string;from:[number,number,number];to:[number,number,number];blur?:[number,number];grade?:string}>=({src,from,to,blur,grade})=>{
  const fr=useCurrentFrame();const {durationInFrames:d}=useVideoConfig();
  const u=ease(fr,0,d,0,1,Easing.inOut(Easing.cubic));
  const s=from[0]+(to[0]-from[0])*u,x=from[1]+(to[1]-from[1])*u,y=from[2]+(to[2]-from[2])*u;
  const b=blur?blur[0]+(blur[1]-blur[0])*ease(fr,0,d*.45):0;
  return <AbsoluteFill style={{overflow:'hidden'}}>
    <Img src={staticFile(src)} style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:`${x}% ${y}%`,transform:`scale(${s})`,transformOrigin:`${x}% ${y}%`,filter:`blur(${b}px) ${grade??'saturate(.92) contrast(1.06)'}`}}/>
  </AbsoluteFill>;
};
export const Clip:React.FC<{src:string;start?:number;rate?:number;pos?:string;scale?:[number,number];grade?:string}>=({src,start=0,rate=1,pos='50% 50%',scale=[1,1],grade})=>{
  const fr=useCurrentFrame();const {durationInFrames:d}=useVideoConfig();
  const s=scale[0]+(scale[1]-scale[0])*ease(fr,0,d,0,1,Easing.inOut(Easing.quad));
  return <AbsoluteFill style={{overflow:'hidden'}}>
    <OffthreadVideo src={staticFile(src)} startFrom={Math.round(start*FPS)} playbackRate={rate} muted
      style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:pos,transform:`scale(${s})`,filter:grade??'saturate(.9) contrast(1.07)'}}/>
  </AbsoluteFill>;
};
// a scene enters with a quick zoom-blur punch
export const Punch:React.FC<{children:React.ReactNode;amount?:number}>=({children,amount=.12})=>{
  const fr=useCurrentFrame();
  const s=1+amount*(1-ease(fr,0,9));const b=8*(1-ease(fr,0,7));
  return <AbsoluteFill style={{transform:`scale(${s})`,filter:`blur(${b}px)`}}>{children}</AbsoluteFill>;
};
export const Flash:React.FC<{at?:number;len?:number;color?:string}>=({at=0,len=8,color='#fff'})=>{
  const fr=useCurrentFrame();const o=interpolate(fr,[at,at+1,at+len],[0,.9,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  return <AbsoluteFill style={{background:color,opacity:o}}/>;
};
// headline that slams in word by word
export const Headline:React.FC<{text:string;y:number;size?:number;delay?:number;color?:string;accent?:string[]}>=({text,y,size=96,delay=0,color=INK,accent=[]})=>{
  const fr=useCurrentFrame();const {fps}=useVideoConfig();
  const words=text.split(' ');
  return <div style={{position:'absolute',top:y,left:60,right:60,textAlign:'center',lineHeight:1.02}}>
    {words.map((w,i)=>{const sp=spring({frame:fr-delay-i*3,fps,config:{damping:14,stiffness:180}});
      return <span key={i} style={{...pop,fontSize:size,display:'inline-block',margin:'0 .14em',color:accent.includes(w)?GREEN:color,
        transform:`translateY(${(1-sp)*50}px) scale(${.7+.3*sp})`,opacity:Math.min(1,sp*1.4),textShadow:shadow}}>{w}</span>;})}
  </div>;
};
export const Tag:React.FC<{text:string;x:number;y:number;delay:number;color?:string;align?:'left'|'right'}>=({text,x,y,delay,color=GREEN,align='left'})=>{
  const fr=useCurrentFrame();const {fps}=useVideoConfig();const sp=spring({frame:fr-delay,fps,config:{damping:16,stiffness:200}});
  return <div style={{position:'absolute',left:align==='left'?x:undefined,right:align==='right'?1080-x:undefined,top:y,transform:`scale(${sp})`,transformOrigin:align==='left'?'left center':'right center',
    background:'rgba(8,12,10,.78)',border:`2px solid ${color}`,borderRadius:14,padding:'10px 20px',...mono,fontSize:34,color,boxShadow:'0 8px 30px rgba(0,0,0,.5)'}}>{text}</div>;
};

// ---------------------------------------------------------------- captions: three words at a time, the spoken one lit
export const Captions:React.FC<{data?:any;top?:number;size?:number}>=({data=vo,top=1262,size=80})=>{
  const fr=useCurrentFrame();const t=fr/FPS;
  const line=(data.lines as any[]).find(l=>t>=l.start-.05&&t<=l.end+.25);
  if(!line)return null;
  // merge whisper's split tokens ("op -amps", "forty -nine")
  const words:{w:string;s:number;e:number}[]=[];
  for(const w of line.words){if(w.w.startsWith('-')&&words.length){words[words.length-1].w+=w.w;words[words.length-1].e=w.e;}else words.push({...w});}
  const chunks:typeof words[]=[];let cur:typeof words=[];
  for(const w of words){cur.push(w);if(cur.length===3||/[.,?]$/.test(w.w)){chunks.push(cur);cur=[];}}
  if(cur.length)chunks.push(cur);
  let ci=chunks.findIndex(c=>t<=c[c.length-1].e+.08);if(ci<0)ci=chunks.length-1;const chunk=chunks[ci];
  const cstart=chunk[0].s;const k=(t-cstart)*FPS;const sp=Math.min(1,k/4);
  const hot=(w:string)=>/PCBWay|649|forty|Seventy|decibels|Eleven|ground|lossless|Barely|no|chip/i.test(w);
  return <div style={{position:'absolute',left:40,right:40,top,display:'flex',flexWrap:'wrap',justifyContent:'center',columnGap:26,rowGap:0,transform:`scale(${.85+.15*sp})`,opacity:sp}}>
    {chunk.map((w,i)=>{const on=t>=w.s-.03;const spoken=t>=w.s-.03&&t<=w.e+.05;
      return <span key={i} style={{...pop,fontSize:size,display:'inline-block',textTransform:'uppercase',lineHeight:1.12,
        color:spoken?(hot(w.w)?GREEN:'#fff'):(on?'#fff':'rgba(255,255,255,.55)'),
        transform:`scale(${spoken?1.08:1})`,WebkitTextStroke:'2px rgba(0,0,0,.35)',textShadow:'0 5px 0 rgba(0,0,0,.55), 0 10px 30px rgba(0,0,0,.6)'}}>{w.w.replace(/[.,]$/,'')}</span>;})}
  </div>;
};

// ---------------------------------------------------------------- scenes
const Hook:React.FC=()=>{
  const fr=useCurrentFrame();const {fps}=useVideoConfig();
  const chip=spring({frame:fr-14,fps,config:{damping:12,stiffness:160}});
  const x=spring({frame:fr-48,fps,config:{damping:9,stiffness:260}});
  const shake=fr>=48&&fr<60?Math.sin(fr*3)*10*(1-(fr-48)/12):0;
  return <AbsoluteFill style={{transform:`translateX(${shake}px)`}}>
    <Punch amount={.25}><Clip src="video/v_led.mp4" start={.4} rate={.8} scale={[1.15,1.35]}/></Punch>
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.65) 0%,rgba(0,0,0,0) 40%)'}}/>
    {/* a DIP "ADC" chip that gets struck out */}
    <div style={{position:'absolute',left:540-210,top:330,width:420,height:250,transform:`scale(${chip}) rotate(${(1-chip)*-12}deg)`}}>
      <svg width="420" height="250" viewBox="0 0 420 250">
        {[0,1,2,3,4,5].map(i=><rect key={'t'+i} x={70+i*52} y={6} width={22} height={40} rx={3} fill="#c9ccd1"/>)}
        {[0,1,2,3,4,5].map(i=><rect key={'b'+i} x={70+i*52} y={204} width={22} height={40} rx={3} fill="#c9ccd1"/>)}
        <rect x={30} y={40} width={360} height={170} rx={16} fill="#15171a" stroke="#3a3f45" strokeWidth={4}/>
        <circle cx={66} cy={76} r={12} fill="#2a2e33"/>
        <text x={210} y={150} textAnchor="middle" style={{fontFamily:'Plex',fontSize:78,fill:'#e8eaed',letterSpacing:6}}>ADC</text>
        <g transform={`translate(210 125) scale(${x})`} opacity={x>0.01?1:0}>
          <line x1={-185} y1={-110} x2={185} y2={110} stroke={RED} strokeWidth={26} strokeLinecap="round"/>
          <line x1={185} y1={-110} x2={-185} y2={110} stroke={RED} strokeWidth={26} strokeLinecap="round"/>
        </g>
      </svg>
    </div>
    <Flash at={48} len={6} color={RED}/>
    <Vignette/>
  </AbsoluteFill>;
};

// first-order sigma-delta of a slow sine: the bits a real modulator would send, density following the wave
const BITS=(()=>{const out:number[]=[];let acc=0;for(let n=0;n<4000;n++){const x=.86*Math.sin(2*Math.PI*n/64);acc+=x-(out.length?(out[out.length-1]?1:-1):0);out.push(acc>=0?1:0);}return out;})();
const Bits:React.FC=()=>{
  const fr=useCurrentFrame();const {fps,durationInFrames:d}=useVideoConfig();
  const N=96,bw=1080/N,speed=1.2;const off=fr*speed;
  const wave=(xp:number)=>Math.sin(2*Math.PI*((xp/bw)+off)/64);
  let path='';for(let xp=0;xp<=1080;xp+=6){const y=520+wave(xp)*150;path+=(xp?'L':'M')+xp+' '+y.toFixed(1);}
  const intro=ease(fr,0,14);const cnt=Math.round(ease(fr,f(L.bits.start+3.8)-CUT.bits,f(L.bits.end)-CUT.bits,0,1536000,Easing.out(Easing.cubic)));
  const blocks=[{t:'OP-AMP',sub:'integrators',x:90},{t:'LM311',sub:'comparator',x:395},{t:'74HC',sub:'logic + DAC',x:700}];
  return <AbsoluteFill style={{background:'#060908'}}>
    <AbsoluteFill style={{opacity:.25}}><Clip src="video/v_fly.mp4" rate={.6} grade="blur(14px) saturate(.6) brightness(.7)"/></AbsoluteFill>
    <AbsoluteFill style={{backgroundImage:'linear-gradient(rgba(124,242,154,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(124,242,154,.07) 1px,transparent 1px)',backgroundSize:'60px 60px',backgroundPosition:`${-off*2}px 0`}}/>
    <div style={{position:'absolute',top:250,left:0,right:0,textAlign:'center',...mono,fontSize:34,color:COPPER,opacity:intro}}>ANALOG FROM THE GROOVE</div>
    <svg width="1080" height="1920" style={{position:'absolute'}}>
      <defs><filter id="glow"><feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
      <path d={path} stroke={COPPER} strokeWidth={9} fill="none" filter="url(#glow)" strokeDasharray={1600} strokeDashoffset={1600*(1-intro)}/>
      {/* the three parts that do the converting */}
      {blocks.map((b,i)=>{const s=spring({frame:fr-10-i*5,fps,config:{damping:14}});return <g key={i} transform={`translate(${b.x+145} 790) scale(${s}) translate(${-145} 0)`}>
        <rect x={0} y={0} width={290} height={120} rx={18} fill="rgba(10,18,14,.9)" stroke={GREEN} strokeWidth={3}/>
        <text x={145} y={58} textAnchor="middle" style={{fontFamily:'Pop',fontWeight:700,fontSize:44,fill:INK}}>{b.t}</text>
        <text x={145} y={96} textAnchor="middle" style={{fontFamily:'Plex',fontSize:24,fill:GREEN}}>{b.sub}</text></g>;})}
      <path d="M540 660 L540 770" stroke={GREEN} strokeWidth={4} strokeDasharray="10 10" strokeDashoffset={-fr*2} opacity={intro}/>
      <path d="M540 930 L540 1010" stroke={GREEN} strokeWidth={4} strokeDasharray="10 10" strokeDashoffset={-fr*2} opacity={intro}/>
      {/* the bitstream */}
      {Array.from({length:N+1}).map((_,i)=>{const k=Math.floor(i+off)%BITS.length;const b=BITS[k];const xx=i*bw-(off%1)*bw;
        return <rect key={i} x={xx+2} y={b?1030:1100} width={bw-4} height={b?110:40} rx={3} fill={b?GREEN:'rgba(124,242,154,.25)'}/>;})}
    </svg>
    <div style={{position:'absolute',top:1170,left:0,right:0,textAlign:'center',...mono,fontSize:30,color:'rgba(124,242,154,.8)'}}>{Array.from({length:24}).map((_,i)=>BITS[Math.floor(i+off*1.0)%BITS.length]).join(' ')}</div>
    <div style={{position:'absolute',top:1500,left:0,right:0,textAlign:'center'}}>
      <div style={{...pop,fontSize:110,color:INK,textShadow:shadow,opacity:cnt>0?1:0}}>{cnt.toLocaleString('en-US')}</div>
      <div style={{...mono,fontSize:34,opacity:cnt>0?1:0}}>BITS PER SECOND, PER CHANNEL</div>
    </div>
    <Vignette strength={.6}/>
  </AbsoluteFill>;
};

const Milled:React.FC=()=>{
  const fr=useCurrentFrame();const b0=f(L.barely.start)-CUT.milled;
  const glitch=fr>=b0+8&&fr<b0+22;const gx=glitch?(Math.sin(fr*7)*24):0;
  const stamp=spring({frame:fr-(b0+14),fps:FPS,config:{damping:10,stiffness:240}});
  return <AbsoluteFill>
    <AbsoluteFill style={{transform:`translateX(${gx}px)`,filter:glitch?'hue-rotate(40deg) saturate(1.6)':'none'}}>
      <KB src="img/20261021_001723.jpg" from={[1.05,18,55]} to={[1.3,22,48]} grade="saturate(.85) contrast(1.08) sepia(.12)"/>
    </AbsoluteFill>
    {glitch&&<AbsoluteFill style={{background:`repeating-linear-gradient(0deg,rgba(255,0,60,.18) 0 6px,transparent 6px 22px)`,transform:`translateY(${(fr*37)%40}px)`}}/>}
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.7) 0%,rgba(0,0,0,0) 30%,rgba(0,0,0,0) 60%,rgba(0,0,0,.6) 100%)'}}/>
    <Headline text="VERSION 1" y={250} size={64} color={COPPER}/>
    <Tag text="4 boards" x={90} y={560} delay={f(.9)}/>
    <Tag text="milled at home" x={990} y={760} delay={f(2.0)} align="right"/>
    <Tag text="jumper wires" x={120} y={980} delay={f(3.6)} color={COPPER}/>
    <div style={{position:'absolute',left:0,right:0,top:760,textAlign:'center',transform:`rotate(-8deg) scale(${.6+.4*stamp})`,opacity:stamp}}>
      <span style={{...pop,fontSize:104,lineHeight:1.05,color:RED,border:`10px solid ${RED}`,borderRadius:24,padding:'10px 40px',background:'rgba(12,0,0,.72)',display:'inline-block',textShadow:'none'}}>2 DAYS<br/>OF DEBUGGING</span>
    </div>
    <Vignette/>
  </AbsoluteFill>;
};

const PCBWay:React.FC=()=>{
  const fr=useCurrentFrame();const {fps}=useVideoConfig();
  const sp=spring({frame:fr-4,fps,config:{damping:11,stiffness:170}});
  return <AbsoluteFill>
    <Punch amount={.35}><Clip src="video/20261021_001916.mp4" start={.3} rate={1.15} scale={[1.05,1.18]}/></Punch>
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.72) 0%,rgba(0,0,0,0) 38%)'}}/>
    <div style={{position:'absolute',top:250,left:0,right:0,textAlign:'center',transform:`scale(${.6+.4*sp})`,opacity:sp}}>
      <div style={{...mono,fontSize:34,color:INK,opacity:.85}}>VERSION 2 · MADE BY</div>
      <div style={{...pop,fontSize:150,color:GREEN,textShadow:shadow,letterSpacing:-3}}>PCBWay</div>
    </div>
    <Flash len={10}/>
    <Vignette/>
  </AbsoluteFill>;
};

const Layers:React.FC=()=>(
  <AbsoluteFill style={{background:'#050605'}}>
    <Punch><AbsoluteFill style={{transform:'translateX(70px) translateY(40px) scale(.95)'}}><Clip src="video/layers.mp4" start={.35} rate={1.1} scale={[1.0,1.06]} grade="none"/></AbsoluteFill></Punch>
    <Headline text="4 COPPER LAYERS" y={250} size={86} accent={['4']}/>
    <Vignette strength={.4}/>
  </AbsoluteFill>
);

const Holes:React.FC=()=>{
  const fr=useCurrentFrame();const a=f(L.holes.start)-CUT.holes;
  const n=Math.round(ease(fr,a,a+f(1.5),0,649,Easing.out(Easing.quad)));
  return <AbsoluteFill>
    <Punch><KB src="img/20261021_001213.jpg" from={[1.0,45,45]} to={[1.45,55,60]}/></Punch>
    <AbsoluteFill style={{background:'radial-gradient(circle at 50% 30%,rgba(0,0,0,.55) 0%,rgba(0,0,0,0) 45%)'}}/>
    <div style={{position:'absolute',top:240,left:0,right:0,textAlign:'center'}}>
      <div style={{...pop,fontSize:230,color:INK,textShadow:shadow,lineHeight:1}}>{n}</div>
      <div style={{...mono,fontSize:40,color:GREEN,textShadow:shadow}}>PLATED HOLES · PER BOARD</div>
    </div>
    <Vignette/>
  </AbsoluteFill>;
};

const Silk:React.FC=()=>{
  const fr=useCurrentFrame();const ring=ease(fr,8,26);
  return <AbsoluteFill>
    <KB src="img/20261021_001028.jpg" from={[1.35,50,42]} to={[1.6,50,40]} blur={[18,0]}/>
    <div style={{position:'absolute',left:540-260,top:640-260,width:520,height:520,borderRadius:'50%',border:`5px solid ${GREEN}`,opacity:ring*(1-ease(fr,30,44)),transform:`scale(${1.4-.4*ring})`,boxShadow:`0 0 40px ${GREEN}`}}/>
    <Headline text="0.8 mm TEXT" y={250} size={86} accent={['0.8','mm']} delay={6}/>
    <Vignette/>
  </AbsoluteFill>;
};

const Pi:React.FC=()=>(
  <AbsoluteFill>
    <Punch><Clip src="video/20261021_002125.mp4" start={1.7} rate={1.35} pos="44% 50%" scale={[1.08,1.15]}/></Punch>
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.65) 0%,rgba(0,0,0,0) 35%)'}}/>
    <Headline text="RASPBERRY PI HAT" y={250} size={84} accent={['PI']}/>
    <Vignette/>
  </AbsoluteFill>
);

const Rip:React.FC=()=>{
  const fr=useCurrentFrame();const {fps}=useVideoConfig();
  const panel=spring({frame:fr-6,fps,config:{damping:15}});
  const files=['Side A · Track 1.flac','Side A · Track 2.flac','Side A · Track 3.flac'];
  const lvl=(i:number)=>.55+.35*Math.abs(Math.sin(fr*.37+i*1.7))*Math.abs(Math.sin(fr*.11+i));
  return <AbsoluteFill>
    <Punch><Clip src="video/20261021_002515.mp4" start={.5} rate={1} pos="14% 50%" scale={[1.06,1.16]}/></Punch>
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.6) 0%,rgba(0,0,0,0) 30%)'}}/>
    <div style={{position:'absolute',left:90,right:90,top:250,transform:`translateY(${(1-panel)*-60}px)`,opacity:panel,background:'rgba(6,10,8,.82)',border:'2px solid rgba(124,242,154,.5)',borderRadius:26,padding:'26px 32px',boxShadow:'0 20px 60px rgba(0,0,0,.6)'}}>
      <div style={{display:'flex',alignItems:'center',gap:18}}>
        <div style={{width:30,height:30,borderRadius:15,background:RED,opacity:fr%30<18?1:.35,boxShadow:`0 0 20px ${RED}`}}/>
        <div style={{...pop,fontSize:46}}>Recording · Side A</div>
      </div>
      {[0,1].map(i=><div key={i} style={{display:'flex',alignItems:'center',gap:14,marginTop:16}}>
        <div style={{...mono,fontSize:26,width:26,color:INK}}>{i?'R':'L'}</div>
        <div style={{flex:1,height:22,borderRadius:11,background:'rgba(255,255,255,.08)',overflow:'hidden'}}>
          <div style={{width:`${lvl(i)*100}%`,height:'100%',background:`linear-gradient(90deg,${GREEN},#d8f27c 80%,${RED})`}}/></div></div>)}
      {files.map((n,i)=>{const s=spring({frame:fr-f(1.2)-i*f(.45),fps,config:{damping:13}});return <div key={i} style={{...mono,fontSize:30,color:INK,marginTop:14,opacity:s,transform:`translateX(${(1-s)*80}px)`}}>
        <span style={{color:GREEN}}>✓</span> {n}</div>;})}
    </div>
    <Vignette/>
  </AbsoluteFill>;
};

const Result:React.FC=()=>{
  const fr=useCurrentFrame();const {fps}=useVideoConfig();
  const a=ease(fr,8,48,0,1,Easing.out(Easing.cubic)),b=ease(fr,18,64,0,1,Easing.out(Easing.cubic));
  const lo=50,hi=82;const w=(v:number)=>(v-lo)/(hi-lo)*820;
  const bar=(label:string,v:number,u:number,col:string,y:number,glow=false)=><div style={{position:'absolute',left:110,top:y}}>
    <div style={{...mono,fontSize:32,color:'rgba(244,247,245,.8)',marginBottom:12}}>{label}</div>
    <div style={{display:'flex',alignItems:'center',gap:24}}>
      <div style={{width:w(lo+(v-lo)*u),height:96,borderRadius:18,background:col,boxShadow:glow?`0 0 50px ${col}`:'none'}}/>
      <div style={{...pop,fontSize:70,color:INK,textShadow:shadow}}>{(lo+(v-lo)*u).toFixed(1)}</div></div></div>;
  return <AbsoluteFill style={{background:'#050706'}}>
    <AbsoluteFill style={{opacity:.55}}><Clip src="video/v_orbit.mp4" rate={.7} grade="brightness(.55) saturate(.8)"/></AbsoluteFill>
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(5,7,6,.9) 0%,rgba(5,7,6,.35) 55%,rgba(5,7,6,.85) 100%)'}}/>
    <Headline text="DYNAMIC RANGE" y={250} size={86}/>
    <div style={{position:'absolute',top:370,left:0,right:0,textAlign:'center',...mono,fontSize:30,color:'rgba(244,247,245,.7)'}}>dB · measured · higher is better</div>
    {bar('MILLED AT HOME',67.9,a,'#8a8f94',540)}
    {bar('PCBWAY · REV D',78.7,b,GREEN,760,true)}
    <Vignette/>
    {/* callback: the two builds side by side, and the gap between them */}
    <Sequence from={f(L.eleven.start)-CUT.result-4}><Compare/></Sequence>
  </AbsoluteFill>;
};
const Compare:React.FC=()=>{
  const fr=useCurrentFrame();const {fps}=useVideoConfig();
  const badge=spring({frame:fr-6,fps,config:{damping:9,stiffness:220}});
  const wipe=ease(fr,0,10);
  return <AbsoluteFill style={{clipPath:`inset(0 0 ${100-wipe*100}% 0)`}}>
    <KB src="img/20261021_001723.jpg" from={[1.0,50,50]} to={[1.1,56,52]} grade="saturate(.9) contrast(1.08)"/>
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.72) 0%,rgba(0,0,0,0) 32%,rgba(0,0,0,0) 62%,rgba(0,0,0,.7) 100%)'}}/>
    <Tag text="MILLED · 67.9 dB" x={60} y={560} delay={4} color="#c9ccd1"/>
    <Tag text="PCBWAY · 78.7 dB" x={1020} y={1000} delay={10} align="right"/>
    <div style={{position:'absolute',left:0,right:0,top:250,textAlign:'center',transform:`scale(${badge}) rotate(-4deg)`}}>
      <span style={{background:GREEN,borderRadius:26,padding:'8px 40px',...pop,fontSize:130,color:'#06120b',display:'inline-block',boxShadow:`0 0 60px rgba(124,242,154,.55)`}}>+11 dB</span></div>
    <Vignette/>
  </AbsoluteFill>;
};

const End:React.FC=()=>{
  const fr=useCurrentFrame();const {fps}=useVideoConfig();
  const sp=spring({frame:fr-3,fps,config:{damping:13}});const u=spring({frame:fr-24,fps,config:{damping:15}});
  return <AbsoluteFill style={{background:'#050605'}}>
    <Clip src="video/v_explode.mp4" rate={1.05} grade="none"/>
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.75) 0%,rgba(0,0,0,0) 40%)'}}/>
    <div style={{position:'absolute',top:240,left:0,right:0,textAlign:'center',transform:`scale(${.7+.3*sp})`,opacity:sp}}>
      <div style={{...mono,fontSize:36,color:INK,opacity:.85}}>PCBs BY</div>
      <div style={{...pop,fontSize:160,color:GREEN,textShadow:shadow,letterSpacing:-3,lineHeight:1.05}}>PCBWay</div>
    </div>
    <div style={{position:'absolute',top:1560,left:0,right:0,textAlign:'center',opacity:u,transform:`translateY(${(1-u)*30}px)`}}>
      <div style={{...mono,fontSize:34,color:INK}}>vinyl-adc.madsrudolph.dev</div>
      <div style={{...mono,fontSize:26,color:'rgba(244,247,245,.6)',marginTop:10}}>music: Voxel Revolution · Kevin MacLeod · CC BY 4.0</div>
    </div>
    <Vignette strength={.45}/>
  </AbsoluteFill>;
};

// ---------------------------------------------------------------- sound
export const S:React.FC<{src:string;at:number;vol?:number}>=({src,at,vol=1})=>(
  <Sequence from={Math.max(0,at)} layout="none"><Audio src={staticFile(`audio/${src}.wav`)} volume={vol}/></Sequence>
);

export const Short:React.FC=()=>{
  useFonts();
  const scenes:[typeof order[number],React.FC][]=[['hook',Hook],['bits',Bits],['milled',Milled],['pcbway',PCBWay],['layers',Layers],['holes',Holes],['silk',Silk],['pi',Pi],['rip',Rip],['result',Result],['end',End]];
  const drop=f(L.pcbway.start);const holes0=f(L.holes.start);
  return <AbsoluteFill style={{background:'#000'}}>
    <style>{fontCss}</style>
    {scenes.map(([k,C])=><Sequence key={k} from={CUT[k]} durationInFrames={dur(k)}><C/></Sequence>)}
    <Grain/>
    <Captions/>
    {/* audio */}
    <Audio src={staticFile('audio/vo.wav')} volume={1.0}/>
    <Audio src={staticFile('audio/music.wav')} volume={(fr)=>{
      const base=fr<drop?.15:.18;const tail=interpolate(fr,[f(L.end.end),f(L.end.end)+8,TOTAL-14,TOTAL],[.18,.42,.42,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
      return fr>f(L.end.end)?tail:base;}}/>
    <S src="impact" at={0} vol={.9}/>
    <S src="glitch" at={f(L.barely.start)+8} vol={.5}/>
    <S src="riser" at={drop-f(2.0)} vol={.45}/>
    <S src="impact" at={drop} vol={.8}/>
    {[CUT.bits,CUT.milled,CUT.layers,CUT.silk,CUT.pi,CUT.result].map((c,i)=><S key={i} src="whoosh" at={c-8} vol={.35}/>)}
    {Array.from({length:12}).map((_,i)=><S key={'t'+i} src="tick" at={holes0+i*4} vol={.5}/>)}
    {[0,1,2].map(i=><S key={'c'+i} src="click" at={CUT.rip+f(1.2)+i*f(.45)} vol={.6}/>)}
    <S src="needle" at={CUT.rip-4} vol={.35}/>
    <S src="impact" at={f(L.eleven.start)} vol={.55}/>
    <S src="whoosh_down" at={CUT.end-6} vol={.4}/>
  </AbsoluteFill>;
};
