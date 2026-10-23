// Edit D, "Build story": first person, the real footage up front, Sept -> Oct, scribbles, a loupe and a before/after.
import React from 'react';
import {AbsoluteFill,Audio,Img,Sequence,staticFile,useCurrentFrame,useVideoConfig,interpolate,spring,Easing,random} from 'remotion';
import vo from '../public/vo-story.json';
import {useFonts,fontCss,S,KB,Clip,Punch,Flash,Vignette,Grain,Captions,pop,mono,shadow,ease,GREEN,RED,INK,COPPER} from './Short';

const FPS=30;const L:Record<string,any>={};for(const l of vo.lines)L[l.key]=l;
const f=(s:number)=>Math.round(s*FPS);
const YEL='#FFE15A';
const CUT:Record<string,number>={hook:0,sep:f(L.sep.start-.1),mess:f(L.mess.start-.05),oct:f(L.oct.start-.1),look:f(L.look.start-.1),
  holes:f(L.detail.start-.1),layers:f(L.detail.start+1.45),solder:f(L.solder.start-.1),pi:f(L.pi.start-.05),rip:f(L.pi.start+1.75),
  better:f(L.better.start-.1),thanks:f(L.thanks.start-.15)};
export const STORY_TOTAL=f(vo.duration+1.9);
const ORDER=['hook','sep','mess','oct','look','holes','layers','solder','pi','rip','better','thanks'];
const dur=(k:string)=>{const i=ORDER.indexOf(k);return (i+1<ORDER.length?CUT[ORDER[i+1]]:STORY_TOTAL)-CUT[k];};

// a hand-drawn ring that draws itself on
const Scribble:React.FC<{cx:number;cy:number;rx:number;ry:number;at:number;color?:string;seed?:string}>=({cx,cy,rx,ry,at,color=YEL,seed='s'})=>{
  const fr=useCurrentFrame();const d=ease(fr,at,at+10);
  let p='';for(let i=0;i<=64;i++){const a=i/64*2*Math.PI*1.12-0.4;const j=1+.06*(random(seed+i)-.5);p+=(i?'L':'M')+(cx+Math.cos(a)*rx*j).toFixed(1)+' '+(cy+Math.sin(a)*ry*j).toFixed(1);}
  return <svg width={1080} height={1920} style={{position:'absolute'}}><path d={p} fill="none" stroke={color} strokeWidth={9} strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1-d} style={{filter:'drop-shadow(0 3px 4px rgba(0,0,0,.5))'}}/></svg>;
};
const Note:React.FC<{text:string;x:number;y:number;at:number;rot?:number;color?:string;size?:number}>=({text,x,y,at,rot=-4,color=YEL,size=58})=>{
  const fr=useCurrentFrame();const {fps}=useVideoConfig();const s=spring({frame:fr-at,fps,config:{damping:11,stiffness:220}});
  return <div style={{position:'absolute',left:x,top:y,transform:`rotate(${rot}deg) scale(${s})`,transformOrigin:'left center',...pop,fontSize:size,color,textShadow:'0 4px 0 rgba(0,0,0,.55)'}}>{text}</div>;
};
// the Sept -> Oct ruler at the top
const Timeline:React.FC<{month:'SEP'|'OCT';at?:number}>=({month,at=0})=>{
  const fr=useCurrentFrame();const u=month==='SEP'?0:ease(fr,at,at+14);const show=ease(fr,0,8);
  return <div style={{position:'absolute',top:270,left:90,right:90,height:120,opacity:show,background:'rgba(0,0,0,.55)',borderRadius:24,padding:'0 30px'}}>
    <div style={{position:'absolute',top:40,left:30,right:30,height:6,background:'rgba(255,255,255,.35)',borderRadius:2}}/>
    {['SEP 2026','OCT 2026'].map((t,i)=><div key={t} style={{position:'absolute',left:i?'auto':0,right:i?0:'auto',top:62,...mono,fontSize:38,padding:'0 30px',color:(i?u>.5:u<.5)?INK:'rgba(255,255,255,.45)'}}>{t}</div>)}
    <div style={{position:'absolute',top:24,left:`calc(30px + ${u}*(100% - 60px) - 19px)`,width:38,height:38,borderRadius:19,background:month==='SEP'?COPPER:GREEN,boxShadow:'0 0 24px rgba(255,255,255,.4)'}}/>
  </div>;
};
// a magnifying loupe over a still
const Loupe:React.FC<{src:string;at:number}>=({src,at})=>{
  const fr=useCurrentFrame();const {fps}=useVideoConfig();const s=spring({frame:fr-at,fps,config:{damping:14}});
  const cx=560+150*Math.sin((fr-at)/20),cy=790+50*Math.cos((fr-at)/26);const R=250,Z=2.4;
  return <AbsoluteFill>
    <KB src={src} from={[1.0,50,46]} to={[1.08,50,46]}/>
    <AbsoluteFill style={{background:'rgba(0,0,0,.35)'}}/>
    <div style={{position:'absolute',left:cx-R,top:cy-R,width:2*R,height:2*R,borderRadius:'50%',overflow:'hidden',transform:`scale(${s})`,border:'10px solid #e9ecef',boxShadow:'0 30px 80px rgba(0,0,0,.7), inset 0 0 40px rgba(0,0,0,.4)'}}>
      <Img src={staticFile(src)} style={{position:'absolute',width:1080*Z,height:1920*Z,objectFit:'cover',objectPosition:'50% 46%',left:-(cx*Z-R),top:-(cy*Z-R)}}/>
    </div>
  </AbsoluteFill>;
};
const BeforeAfter:React.FC=()=>{
  const fr=useCurrentFrame();const {fps}=useVideoConfig();
  const div=interpolate(fr,[0,18,40],[1080,540,540],{extrapolateRight:'clamp',easing:Easing.bezier(.22,1,.36,1)});
  const b=spring({frame:fr-f(L.better.start+1.4)+CUT.better,fps,config:{damping:9,stiffness:230}});
  return <AbsoluteFill>
    <AbsoluteFill style={{filter:'grayscale(.75) brightness(.8)'}}><KB src="img/20261021_001723.jpg" from={[1.25,15,55]} to={[1.35,18,55]}/></AbsoluteFill>
    <AbsoluteFill style={{clipPath:`inset(0 0 0 ${div}px)`}}><KB src="img/20261021_001416.jpg" from={[1.05,60,55]} to={[1.15,60,55]}/></AbsoluteFill>
    <div style={{position:'absolute',left:div-4,top:0,bottom:0,width:8,background:'#fff',boxShadow:'0 0 30px rgba(0,0,0,.6)'}}/>
    <div style={{position:'absolute',left:40,top:330,...mono,fontSize:30,color:INK}}>BEFORE<br/><span style={{...pop,fontSize:64}}>67.9 dB</span></div>
    <div style={{position:'absolute',right:40,top:330,textAlign:'right',...mono,fontSize:30,color:GREEN,opacity:ease(fr,14,22)}}>AFTER<br/><span style={{...pop,fontSize:64,color:GREEN}}>78.7 dB</span></div>
    <div style={{position:'absolute',left:0,right:0,top:560,textAlign:'center',transform:`scale(${b}) rotate(-5deg)`}}>
      <span style={{...pop,fontSize:120,background:YEL,color:'#111',padding:'4px 34px',borderRadius:18,display:'inline-block',boxShadow:'0 12px 0 rgba(0,0,0,.35)'}}>+11 dB</span></div>
  </AbsoluteFill>;
};
const Ff:React.FC=()=>{const fr=useCurrentFrame();return <div style={{position:'absolute',right:70,top:300,...pop,fontSize:90,color:INK,opacity:fr%10<6?1:.4,textShadow:shadow}}>▶▶ ×4</div>;};

const Rec:React.FC=()=>{const fr=useCurrentFrame();return <div style={{position:'absolute',left:70,top:300,display:'flex',alignItems:'center',gap:16,background:'rgba(0,0,0,.6)',padding:'12px 24px',borderRadius:40}}>
  <div style={{width:30,height:30,borderRadius:15,background:RED,opacity:fr%24<14?1:.3}}/><span style={{...pop,fontSize:44,color:INK}}>REC · auto</span></div>;};

export const Story:React.FC=()=>{
  useFonts();
  const sc:Record<string,React.ReactNode>={
    hook:<><Punch amount={.3}><Clip src="video/20261021_002515.mp4" start={2.0} pos="2% 45%" scale={[1.02,1.22]}/></Punch>
      <Note text="NO ADC CHIP" x={150} y={360} at={f(L.hook.start+1.6)} rot={-6} size={96} color={YEL}/><Flash len={6}/></>,
    sep:<><Punch><KB src="img/20261021_001723.jpg" from={[1.15,18,55]} to={[1.3,20,50]} grade="saturate(.85) contrast(1.06) sepia(.1)"/></Punch><Timeline month="SEP"/></>,
    mess:<><KB src="img/20261021_001723.jpg" from={[1.9,22,40]} to={[2.1,24,42]} grade="saturate(.85) contrast(1.06) sepia(.1)"/>
      <Scribble cx={520} cy={760} rx={330} ry={230} at={4} seed="a"/><Note text="4 boards" x={120} y={420} at={4}/>
      <Note text="jumper wires!" x={460} y={1050} at={f(1.0)} rot={5}/>
      <Note text="2 days debugging" x={120} y={1150} at={f(2.2)} rot={-3} color={RED}/></>,
    oct:<><Flash len={8}/><Punch amount={.25}><Clip src="video/20261021_001916.mp4" start={.3} rate={1.15} scale={[1.05,1.15]}/></Punch><Timeline month="OCT" at={0}/></>,
    look:<Loupe src="img/20261021_001028.jpg" at={2}/>,
    holes:<><Punch><KB src="img/20261021_001213.jpg" from={[1.2,45,50]} to={[1.6,55,58]}/></Punch>
      <Scribble cx={540} cy={1000} rx={180} ry={180} at={10} seed="h"/><Note text="all plated" x={380} y={1220} at={16} rot={4}/></>,
    layers:<><AbsoluteFill style={{background:'#050605'}}/><AbsoluteFill style={{transform:'translateX(40px) translateY(60px) scale(1.12)'}}><Clip src="video/layers.mp4" start={.5} rate={1.6} grade="none"/></AbsoluteFill>
      <Note text="4 layers" x={120} y={330} at={4} rot={-4}/></>,
    solder:<><Clip src="video/20261021_001846.mp4" start={.2} rate={4} scale={[1.05,1.1]}/><Ff/></>,
    pi:<><Punch><Clip src="video/20261021_002125.mp4" start={1.8} rate={1.7} pos="44% 50%" scale={[1.08,1.18]}/></Punch></>,
    rip:<><Punch><Clip src="video/20261021_002515.mp4" start={0.6} pos="14% 50%" scale={[1.08,1.2]}/></Punch><Rec/></>,
    better:<BeforeAfter/>,
    thanks:<><KB src="img/20261021_001416.jpg" from={[1.0,50,50]} to={[1.12,50,58]}/>
      <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.7) 0%,rgba(0,0,0,0) 35%,rgba(0,0,0,0) 70%,rgba(0,0,0,.75) 100%)'}}/>
      <Note text="Thanks," x={140} y={300} at={4} rot={-5} size={110} color={INK}/><Note text="PCBWay" x={300} y={430} at={10} rot={-5} size={150} color={GREEN}/>
      <div style={{position:'absolute',bottom:250,left:0,right:0,textAlign:'center',...mono,fontSize:32,color:INK}}>vinyl-adc.madsrudolph.dev<br/><span style={{fontSize:22,opacity:.65}}>music: Funkorama · Kevin MacLeod · CC BY 4.0</span></div></>,
  };
  const pi0=CUT.pi;
  return <AbsoluteFill style={{background:'#000'}}>
    <style>{fontCss}</style>
    {ORDER.map(k=><Sequence key={k} from={CUT[k]} durationInFrames={dur(k)}><AbsoluteFill>{sc[k]}<Vignette strength={.5}/></AbsoluteFill></Sequence>)}
    <Grain/>
    <Captions data={vo} top={1300} size={74}/>
    <Audio src={staticFile('audio/vo-story.wav')}/>
    <Audio src={staticFile('audio/music_story.wav')} volume={(fr)=>fr>f(L.thanks.end)?interpolate(fr,[f(L.thanks.end),f(L.thanks.end)+6,STORY_TOTAL-10,STORY_TOTAL],[.17,.4,.4,0],{extrapolateRight:'clamp'}):.17}/>
    <S src="impact" at={0} vol={.7}/>
    {['sep','oct','look','holes','layers','solder','pi','better'].map(k=><S key={k} src="whoosh" at={CUT[k]-7} vol={.32}/>)}
    <S src="glitch" at={CUT.mess+f(2.2)} vol={.4}/>
    <S src="click" at={CUT.rip+2} vol={.6}/>
    <S src="impact" at={CUT.better+f(L.better.start+1.4)-CUT.better} vol={.55}/>
  </AbsoluteFill>;
};
