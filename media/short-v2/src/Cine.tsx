// Edit B, "Cinematic": slow, dark, product-film. New Blender shots (c_*), real footage in slow motion, light serif titles.
import React from 'react';
import {AbsoluteFill,Audio,Img,OffthreadVideo,Sequence,staticFile,useCurrentFrame,useVideoConfig,interpolate,Easing,getStaticFiles} from 'remotion';
import vo from '../public/vo-cine.json';
import {useFonts,S} from './Short';

const FPS=30;const L:Record<string,any>={};for(const l of vo.lines)L[l.key]=l;
const f=(s:number)=>Math.round(s*FPS);
const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
const cineFonts=`
@font-face{font-family:'Serif';src:url('${staticFile('fonts/NotoSerif-Light.ttf')}');font-weight:300}
@font-face{font-family:'Serif';src:url('${staticFile('fonts/NotoSerif-LightItalic.ttf')}');font-weight:300;font-style:italic}
@font-face{font-family:'Thin';src:url('${staticFile('fonts/NotoSans-Light.ttf')}');font-weight:300}
@font-face{font-family:'Plex';src:url('${staticFile('fonts/PlexMono-Medium.ttf')}');font-weight:500}`;
const IVORY='#EDE6DA',AMBER='#E7B67A';

// a render shot if it exists, otherwise its stand-in
const has=(p:string)=>getStaticFiles().some(x=>x.name===p);
const shot=(name:string,fallback:string)=>has(`video/${name}.mp4`)?`video/${name}.mp4`:`video/${fallback}.mp4`;

// each scene: [start s, end s]; VO lines are placed inside them on their own
const SC:[string,number,number][]=[['sweep',0,5.6],['needle',5.6,10.0],['rack',10.0,14.6],['scan',14.6,19.4],['board',19.4,24.6],['float',24.6,30.0],['title',30.0,36.0]];
// where each VO line plays (seconds into the film)
const AT:Record<string,number>={groove:1.4,nochip:6.4,parts:10.9,layers:15.4,dr:20.2,kept:25.6,name:31.6};
export const CINE_TOTAL=f(36);

const Grade:React.FC<{children:React.ReactNode}>=({children})=>(
  <AbsoluteFill style={{filter:'contrast(1.08) saturate(.88) sepia(.08)'}}>{children}</AbsoluteFill>
);
// slow dissolves between scenes
const Dissolve:React.FC<{len:number;children:React.ReactNode}>=({len,children})=>{
  const fr=useCurrentFrame();const {durationInFrames:d}=useVideoConfig();
  const o=Math.min(interpolate(fr,[0,len],[0,1],clamp),interpolate(fr,[d-len,d],[1,0],clamp));
  return <AbsoluteFill style={{opacity:o}}>{children}</AbsoluteFill>;
};
const Vid:React.FC<{src:string;start?:number;rate?:number;pos?:string;scale?:[number,number];grade?:string}>=({src,start=0,rate=1,pos='50% 50%',scale=[1,1],grade=''})=>{
  const fr=useCurrentFrame();const {durationInFrames:d}=useVideoConfig();const s=scale[0]+(scale[1]-scale[0])*fr/d;
  return <AbsoluteFill style={{overflow:'hidden'}}><OffthreadVideo src={staticFile(src)} startFrom={Math.round(start*FPS)} playbackRate={rate} muted
    style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:pos,transform:`scale(${s})`,filter:grade}}/></AbsoluteFill>;
};
const Still:React.FC<{src:string;pos?:string;scale?:[number,number];blur?:[number,number]}>=({src,pos='50% 50%',scale=[1.05,1.18],blur=[0,0]})=>{
  const fr=useCurrentFrame();const {durationInFrames:d}=useVideoConfig();const u=fr/d;
  return <AbsoluteFill style={{overflow:'hidden'}}><Img src={staticFile(src)} style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:pos,
    transform:`scale(${scale[0]+(scale[1]-scale[0])*u})`,filter:`blur(${blur[0]+(blur[1]-blur[0])*Math.min(1,u*2)}px) brightness(.82)`}}/></AbsoluteFill>;
};
// light serif title, letter-spaced, fading in by word
const Title:React.FC<{text:string;at:number;y:number;size?:number;italic?:boolean;color?:string;track?:number}>=({text,at,y,size=64,italic=false,color=IVORY,track=.06})=>{
  const fr=useCurrentFrame();const words=text.split(' ');
  return <div style={{position:'absolute',left:70,right:70,top:y,textAlign:'center',fontFamily:'Serif',fontWeight:300,fontStyle:italic?'italic':'normal',fontSize:size,lineHeight:1.2,letterSpacing:`${track}em`,color}}>
    {words.map((w,i)=>{const o=interpolate(fr,[at+i*5,at+i*5+18],[0,1],{...clamp,easing:Easing.out(Easing.cubic)});
      return <span key={i} style={{display:'inline-block',opacity:o,transform:`translateY(${(1-o)*12}px)`,filter:`blur(${(1-o)*6}px)`,margin:'0 .16em',textShadow:'0 2px 24px rgba(0,0,0,.6)'}}>{w}</span>;})}
  </div>;
};
const Caps:React.FC<{text:string;at:number;y:number;size?:number;color?:string}>=({text,at,y,size=24,color='rgba(237,230,218,.7)'})=>{
  const fr=useCurrentFrame();const o=interpolate(fr,[at,at+24],[0,1],clamp);
  return <div style={{position:'absolute',left:0,right:0,top:y,textAlign:'center',fontFamily:'Thin',fontWeight:300,fontSize:size,letterSpacing:'.42em',color,opacity:o}}>{text}</div>;
};
// anamorphic streak + light leak
const Flare:React.FC<{x:number;y:number;at:number;len?:number;color?:string}>=({x,y,at,len=50,color='255,200,140'})=>{
  const fr=useCurrentFrame();const o=interpolate(fr,[at,at+len*.4,at+len],[0,1,0],clamp);
  return <AbsoluteFill style={{mixBlendMode:'screen',opacity:o}}>
    <div style={{position:'absolute',left:-200,right:-200,top:y-3,height:6,background:`linear-gradient(90deg,transparent,rgba(${color},.9) 50%,transparent)`,filter:'blur(2px)'}}/>
    <div style={{position:'absolute',left:x-260,top:y-260,width:520,height:520,borderRadius:'50%',background:`radial-gradient(circle,rgba(${color},.55),transparent 65%)`}}/>
  </AbsoluteFill>;
};
const Leak:React.FC=()=>{const fr=useCurrentFrame();const x=50+30*Math.sin(fr/90),y=20+15*Math.cos(fr/70);
  return <AbsoluteFill style={{mixBlendMode:'screen',opacity:.18,background:`radial-gradient(ellipse at ${x}% ${y}%,rgba(255,170,90,.8),transparent 55%)`}}/>;};
const Bars:React.FC=()=>(<>
  <div style={{position:'absolute',left:0,right:0,top:0,height:120,background:'#000'}}/>
  <div style={{position:'absolute',left:0,right:0,bottom:0,height:120,background:'#000'}}/>
</>);
const Grain:React.FC=()=>{const fr=useCurrentFrame();
  return <AbsoluteFill style={{opacity:.09,mixBlendMode:'overlay',backgroundImage:`url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='260' height='260'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='1.1' numOctaves='2' seed='${fr%9}'/></filter><rect width='260' height='260' filter='url(%23n)'/></svg>")`}}/>;};

const scenes:Record<string,React.ReactNode>={
  sweep:<><Vid src={shot('c_sweep','v_fly')}/><Title text="Every record is a groove." at={f(AT.groove-0)} y={1360} size={71} italic/><Flare x={540} y={760} at={f(2.2)} len={70}/></>,
  needle:<><Vid src="video/20261021_002515.mp4" start={4.0} rate={.5} pos="64% 45%" scale={[1.25,1.35]} grade="brightness(.8) contrast(1.1)"/>
    <Title text="Read without a converter chip." at={f(AT.nochip-5.6)} y={1360} size={66}/></>,
  rack:<><Vid src={shot('c_rack','v_led')}/>
    {['Op-amps.','Comparators.','Logic.'].map((w,i)=><Title key={w} text={w} at={f(AT.parts-10.0)+i*f(.62)} y={1250+i*90} size={75} italic={i===2}/>)}</>,
  scan:<><Vid src={shot('c_scan','v_orbit')}/><Caps text="FOUR COPPER LAYERS" at={f(AT.layers-14.6)} y={1380} size={30}/>
    <Title text="made by PCBWay" at={f(AT.layers-14.6)+f(1.0)} y={1440} size={73} italic color={AMBER}/></>,
  board:<><Vid src="video/20261021_001916.mp4" start={.8} rate={.55} scale={[1.08,1.18]} grade="brightness(.82) contrast(1.08) saturate(.85)"/>
    <AbsoluteFill style={{background:'radial-gradient(ellipse at 50% 70%,rgba(0,0,0,.0),rgba(0,0,0,.65) 75%)'}}/>
    <Title text="78.7" at={f(AT.dr-19.4)+f(.9)} y={520} size={230} track={-.01}/><Caps text="DECIBELS OF DYNAMIC RANGE" at={f(AT.dr-19.4)+f(1.6)} y={830} size={28}/></>,
  float:<><Vid src={shot('c_float','v_explode')}/><Title text="Your records, kept the way they sound." at={f(AT.kept-24.6)} y={1340} size={64} italic/><Flare x={540} y={900} at={f(1.0)} len={60} color="150,190,255"/></>,
  title:<><Vid src="video/20261021_002515.mp4" start={.5} rate={.45} pos="14% 50%" scale={[1.12,1.2]} grade="brightness(.35) contrast(1.1) saturate(.7)"/>
    <Title text="Vinyl ADC" at={f(AT.name-30.0)} y={760} size={138} track={.08}/>
    <Caps text="BOARDS BY PCBWAY" at={f(AT.name-30.0)+f(1.3)} y={940} size={30} color={AMBER}/>
    <Caps text="VINYL-ADC.MADSRUDOLPH.DEV" at={f(3.4)} y={1560} size={20}/>
    <Caps text="MUSIC  FLOATING CITIES  KEVIN MACLEOD  CC BY 4.0" at={f(3.6)} y={1600} size={14}/></>,
};

export const Cine:React.FC=()=>{
  useFonts();
  return <AbsoluteFill style={{background:'#000'}}>
    <style>{cineFonts}</style>
    {SC.map(([k,a,b])=><Sequence key={k} from={f(a)-(a?12:0)} durationInFrames={f(b)-f(a)+(a?12:0)+12}><Dissolve len={a?14:20}><Grade>{scenes[k]}</Grade></Dissolve></Sequence>)}
    <Leak/><Grain/><Bars/>
    <AbsoluteFill style={{background:'radial-gradient(ellipse at 50% 50%,transparent 50%,rgba(0,0,0,.6) 100%)'}}/>
    {/* VO lines, each placed on its own */}
    {vo.lines.map((l:any)=><Sequence key={l.key} from={f(AT[l.key])} durationInFrames={f(l.end-l.start+.4)} layout="none">
      <Audio src={staticFile('audio/vo-cine.wav')} startFrom={f(l.start)} endAt={f(l.end+.3)}/></Sequence>)}
    <Audio src={staticFile('audio/music_cine.wav')} volume={(fr)=>interpolate(fr,[0,f(2),CINE_TOTAL-f(3),CINE_TOTAL],[0,.32,.32,0],clamp)}/>
    <S src="riser" at={f(18.4)} vol={.18}/>
    <S src="impact" at={f(20.2)+f(.9)} vol={.35}/>
  </AbsoluteFill>;
};
