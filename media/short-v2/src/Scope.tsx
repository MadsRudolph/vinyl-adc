// Edit C, "Oscilloscope": the board told through its own measurements, on a green-phosphor CRT, cut to 160 BPM.
import React from 'react';
import {AbsoluteFill,Audio,Img,OffthreadVideo,Sequence,staticFile,useCurrentFrame,interpolate,Easing,random} from 'remotion';
import data from '../public/data.json';
import {useFonts,fontCss,S} from './Short';

const P='#8CFF9E',PD='rgba(140,255,158,.35)',BG='#020604';
const BEAT=30*60/160;                       // 11.25 frames
const bars=(n:number)=>Math.round(n*4*BEAT);
const OFF=1;                                // the track's first beat lands at 0.02 s
const SCENES:[string,number][]=[['on',2],['wave',2],['bits',2],['board',2],['holes',1],['layers',2],['fft',3],['tone',2],['resp',2],['dr',2],['end',2]];
const START:Record<string,number>={};let acc=OFF;for(const [k,b] of SCENES){START[k]=acc;acc+=bars(b);}
export const SCOPE_TOTAL=acc+20;

const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
const lin=(fr:number,a:number,b:number,x=0,y=1)=>interpolate(fr,[a,b],[x,y],clamp);
const glow=`drop-shadow(0 0 6px ${P}) drop-shadow(0 0 18px rgba(140,255,158,.45))`;
const font:React.CSSProperties={fontFamily:'Plex',fontWeight:500,color:P,textShadow:`0 0 8px ${P}, 0 0 22px rgba(140,255,158,.5)`};

// ---------------------------------------------------------------- CRT furniture
const Scan:React.FC=()=>{const fr=useCurrentFrame();return <>
  <AbsoluteFill style={{background:'repeating-linear-gradient(0deg,rgba(0,0,0,.28) 0 2px,transparent 2px 5px)',mixBlendMode:'multiply'}}/>
  <AbsoluteFill style={{background:`linear-gradient(180deg,transparent ${(fr*1.7)%120-20}%,rgba(140,255,158,.06) ${(fr*1.7)%120-10}%,transparent ${(fr*1.7)%120}%)`}}/>
  <AbsoluteFill style={{background:'radial-gradient(ellipse at 50% 50%,transparent 55%,rgba(0,0,0,.85) 100%)'}}/>
</>;};
const Type:React.FC<{text:string;at:number;x:number;y:number;size?:number;cps?:number;cursor?:boolean;align?:'left'|'center'}>=({text,at,x,y,size=40,cps=28,cursor=true,align='left'})=>{
  const fr=useCurrentFrame();const n=Math.max(0,Math.floor((fr-at)*cps/30));if(fr<at)return null;
  const shown=text.slice(0,n);const blink=Math.floor(fr/8)%2===0;
  return <div style={{position:'absolute',left:align==='center'?0:x,right:align==='center'?0:undefined,top:y,textAlign:align,whiteSpace:'pre',...font,fontSize:size}}>{shown}{cursor&&n<=text.length+20&&blink?'█':''}</div>;
};
const Grat:React.FC<{x:number;y:number;w:number;h:number;nx?:number;ny?:number}>=({x,y,w,h,nx=10,ny=8})=>(
  <g opacity={.5}>
    <rect x={x} y={y} width={w} height={h} fill="none" stroke={PD} strokeWidth={2}/>
    {Array.from({length:nx-1}).map((_,i)=><line key={'v'+i} x1={x+w*(i+1)/nx} x2={x+w*(i+1)/nx} y1={y} y2={y+h} stroke="rgba(140,255,158,.13)" strokeDasharray="2 8"/>)}
    {Array.from({length:ny-1}).map((_,i)=><line key={'h'+i} y1={y+h*(i+1)/ny} y2={y+h*(i+1)/ny} x1={x} x2={x+w} stroke="rgba(140,255,158,.13)" strokeDasharray="2 8"/>)}
  </g>);
// photos and renders turned into phosphor
const Phos:React.FC<{children:React.ReactNode;dither?:boolean}>=({children})=>(
  <AbsoluteFill style={{filter:'grayscale(1) contrast(1.35) brightness(.95) sepia(1) hue-rotate(68deg) saturate(3.2)'}}>{children}</AbsoluteFill>
);
const Rgb:React.FC<{at:number;children:React.ReactNode}>=({at,children})=>{
  const fr=useCurrentFrame();const k=Math.max(0,1-(fr-at)/6);const dx=k*14*(random('g'+Math.floor(fr/2))-.5)*2;
  return <AbsoluteFill style={{transform:`translateX(${dx}px)`,filter:k>0?`drop-shadow(${k*8}px 0 0 rgba(255,60,90,.6)) drop-shadow(${-k*8}px 0 0 rgba(60,140,255,.6))`:'none'}}>{children}</AbsoluteFill>;
};

// log-frequency plot of [f, dB] points, drawn on
const Plot:React.FC<{pts:number[][];f0:number;f1:number;d0:number;d1:number;x:number;y:number;w:number;h:number;draw:number;color?:string;width?:number}>=({pts,f0,f1,d0,d1,x,y,w,h,draw,color=P,width=4})=>{
  const X=(f:number)=>x+w*(Math.log10(f)-Math.log10(f0))/(Math.log10(f1)-Math.log10(f0));
  const Y=(d:number)=>y+h*(1-(Math.max(d0,Math.min(d1,d))-d0)/(d1-d0));
  const p=pts.filter(q=>q[0]>=f0&&q[0]<=f1).map((q,i)=>(i?'L':'M')+X(q[0]).toFixed(1)+' '+Y(q[1]).toFixed(1)).join(' ');
  return <path d={p} fill="none" stroke={color} strokeWidth={width} strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1-draw} style={{filter:glow}}/>;
};
const Axis:React.FC<{labels:[number,string][];f0:number;f1:number;x:number;w:number;y:number}>=({labels,f0,f1,x,w,y})=>(
  <>{labels.map(([f,t])=>{const xx=x+w*(Math.log10(f)-Math.log10(f0))/(Math.log10(f1)-Math.log10(f0));
    return <text key={t} x={xx} y={y} textAnchor="middle" style={{fontFamily:'Plex',fontSize:24,fill:PD}}>{t}</text>;})}</>
);

// ---------------------------------------------------------------- scenes
const On:React.FC=()=>{
  const fr=useCurrentFrame();
  const h=lin(fr,0,5,.004,1);const flash=lin(fr,0,6,1,0);
  return <AbsoluteFill style={{background:BG}}>
    <AbsoluteFill style={{transform:`scaleY(${h})`,background:`rgba(140,255,158,${.85*flash})`}}/>
    <Type text={'THIS ADC HAS'} at={3} x={0} y={640} size={92} cps={70} align="center" cursor={false}/>
    <Type text={'NO ADC CHIP.'} at={14} x={0} y={760} size={118} cps={60} align="center"/>
    <Type text={'> op-amps · comparators · logic'} at={44} x={0} y={960} size={40} cps={50} align="center" cursor={false}/>
    <Type text={'> rev D · made by PCBWay'} at={64} x={0} y={1030} size={40} cps={50} align="center" cursor={false}/>
  </AbsoluteFill>;
};
const Wave:React.FC=()=>{
  const fr=useCurrentFrame();const wv=data.tone_wave as number[];
  const x=90,y=560,w=900,h=520;const draw=lin(fr,4,40);
  const n=Math.floor(wv.length*draw);let p='';for(let i=0;i<n;i++){p+=(i?'L':'M')+(x+w*i/(wv.length-1)).toFixed(1)+' '+(y+h/2-wv[i]*h*.62).toFixed(1);}
  return <AbsoluteFill style={{background:BG}}>
    <svg width={1080} height={1920}><Grat x={x} y={y} w={w} h={h}/><path d={p} fill="none" stroke={P} strokeWidth={5} style={{filter:glow}}/></svg>
    <Type text={'CH1  1 kHz  -3 dBFS  ·  real capture'} at={0} x={90} y={500} size={30} cursor={false}/>
    <Type text={'THE SIGNAL GOES IN'} at={14} x={0} y={1200} size={60} align="center"/>
  </AbsoluteFill>;
};
const BITS=(()=>{const o:number[]=[];let a=0,y=0;for(let n=0;n<6000;n++){const x=.8*Math.sin(2*Math.PI*n/48);a+=x-y;y=a>=0?1:-1;o.push(a>=0?1:0);}return o;})();
const Bits:React.FC=()=>{
  const fr=useCurrentFrame();const x=90,w=900,N=110,bw=w/N;const off=fr*2.2;
  const rows=[620,820,1020];
  return <AbsoluteFill style={{background:BG}}>
    <svg width={1080} height={1920}>
      {rows.map((ry,r)=><g key={r}>{Array.from({length:N}).map((_,i)=>{const b=BITS[Math.floor(i+off+r*N)%BITS.length];
        return <rect key={i} x={x+i*bw+1} y={ry+(b?0:120)} width={bw-2} height={b?140:20} fill={b?P:'rgba(140,255,158,.18)'} style={b?{filter:glow}:{}}/>;})}</g>)}
    </svg>
    <Type text={'AND COMES OUT AS BITS'} at={4} x={0} y={420} size={60} align="center"/>
    <div style={{position:'absolute',top:1260,left:0,right:0,textAlign:'center',...font,fontSize:88}}>{Math.round(lin(fr,10,70,0,1536000)).toLocaleString('en-US')}</div>
    <Type text={'bits per second, per channel'} at={20} x={0} y={1370} size={34} align="center" cursor={false}/>
  </AbsoluteFill>;
};
const Board:React.FC<{img:string;title:string;sub:string;from?:number;to?:number;pos?:string}>=({img,title,sub,from=1.05,to=1.2,pos='50% 50%'})=>{
  const fr=useCurrentFrame();const s=from+(to-from)*lin(fr,0,90,0,1);
  return <AbsoluteFill style={{background:BG}}>
    <Phos><Img src={staticFile(img)} style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:pos,transform:`scale(${s})`}}/></Phos>
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(2,6,4,.85) 0%,rgba(2,6,4,0) 30%,rgba(2,6,4,0) 70%,rgba(2,6,4,.85) 100%)'}}/>
    <Type text={title} at={3} x={0} y={330} size={66} align="center"/>
    <Type text={sub} at={14} x={0} y={420} size={34} align="center" cursor={false}/>
  </AbsoluteFill>;
};
const Layers:React.FC=()=>(
  <AbsoluteFill style={{background:BG}}>
    <Phos><OffthreadVideo src={staticFile('video/layers.mp4')} startFrom={20} playbackRate={1.4} muted style={{width:'100%',height:'100%',objectFit:'cover'}}/></Phos>
    <Type text={'4 COPPER LAYERS'} at={3} x={0} y={330} size={66} align="center"/>
    <Type text={'one of them: solid ground'} at={18} x={0} y={420} size={34} align="center" cursor={false}/>
  </AbsoluteFill>
);
const Fft:React.FC=()=>{
  const fr=useCurrentFrame();const x=110,y=520,w=880,h=760;
  const L=data.bitpsd_L as number[][];const d=lin(fr,6,70,0,1,);
  const X=(f:number)=>x+w*(Math.log10(f)-Math.log10(50))/(Math.log10(768000)-Math.log10(50));
  const band=lin(fr,70,84);
  return <AbsoluteFill style={{background:BG}}>
    <svg width={1080} height={1920}>
      <Grat x={x} y={y} w={w} h={h} nx={8} ny={8}/>
      <rect x={X(20)} y={y} width={X(20000)-X(50)} height={h} fill="rgba(140,255,158,.08)" opacity={band}/>
      <Plot pts={L} f0={50} f1={768000} d0={-150} d1={-30} x={x} y={y} w={w} h={h} draw={d}/>
      <Axis labels={[[100,'100'],[1000,'1k'],[10000,'10k'],[100000,'100k']]} f0={50} f1={768000} x={x} w={w} y={y+h+40}/>
    </svg>
    <Type text={'NOISE, MOVED OUT OF EARSHOT'} at={2} x={0} y={330} size={50} align="center"/>
    <Type text={'raw bitstream · FFT · inputs shorted'} at={12} x={0} y={410} size={30} align="center" cursor={false}/>
    <Type text={'audio band:\nquiet'} at={74} x={150} y={1060} size={34} cursor={false}/>
    <Type text={'+66 dB/decade\nup here'} at={92} x={640} y={650} size={34} cursor={false}/>
  </AbsoluteFill>;
};
const Tone:React.FC=()=>{
  const fr=useCurrentFrame();const x=110,y=520,w=880,h=700;const d=lin(fr,4,50);
  const X=(f:number)=>x+w*(Math.log10(f)-Math.log10(20))/(Math.log10(24000)-Math.log10(20));
  const Y=(db:number)=>y+h*(1-(db+150)/150);
  const marks:[number,number,string][]=[[2000,-79,'2nd −76 dBc'],[3000,-84,'3rd −81 dBc']];
  return <AbsoluteFill style={{background:BG}}>
    <svg width={1080} height={1920}>
      <Grat x={x} y={y} w={w} h={h} nx={8} ny={10}/>
      <Plot pts={data.tone as number[][]} f0={20} f1={24000} d0={-150} d1={0} x={x} y={y} w={w} h={h} draw={d} width={3}/>
      {marks.map(([f,db,t],i)=>{const o=lin(fr,54+i*10,60+i*10);return <g key={t} opacity={o}>
        <circle cx={X(f)} cy={Y(db)} r={18} fill="none" stroke={P} strokeWidth={3} style={{filter:glow}}/>
        <text x={X(f)+26} y={Y(db)-26-i*60} style={{fontFamily:'Plex',fontSize:30,fill:P}}>{t}</text></g>;})}
      <Axis labels={[[100,'100'],[1000,'1k'],[10000,'10k']]} f0={20} f1={24000} x={x} w={w} y={y+h+40}/>
    </svg>
    <Type text={'1 kHz IN, ALMOST NOTHING ELSE'} at={2} x={0} y={330} size={48} align="center"/>
    <Type text={'THD 0.019 %  ·  AD3 generator'} at={14} x={0} y={410} size={30} align="center" cursor={false}/>
  </AbsoluteFill>;
};
const Resp:React.FC=()=>{
  const fr=useCurrentFrame();const x=110,y=640,w=880,h=420;const d=lin(fr,4,60);
  return <AbsoluteFill style={{background:BG}}>
    <svg width={1080} height={1920}>
      <Grat x={x} y={y} w={w} h={h} nx={8} ny={6}/>
      <line x1={x} x2={x+w} y1={y+h/2} y2={y+h/2} stroke={PD} strokeWidth={2}/>
      <Plot pts={data.response as number[][]} f0={20} f1={20000} d0={-1.5} d1={1.5} x={x} y={y} w={w} h={h} draw={d} width={6}/>
      <Axis labels={[[20,'20'],[200,'200'],[2000,'2k'],[20000,'20k']]} f0={20} f1={20000} x={x} w={w} y={y+h+40}/>
      <text x={x-14} y={y+10} textAnchor="end" style={{fontFamily:'Plex',fontSize:24,fill:PD}}>+1.5</text>
      <text x={x-14} y={y+h} textAnchor="end" style={{fontFamily:'Plex',fontSize:24,fill:PD}}>−1.5</text>
    </svg>
    <Type text={'FLAT, BASS TO TREBLE'} at={2} x={0} y={400} size={56} align="center"/>
    <Type text={'20 Hz to 16 kHz within 0.3 dB'} at={14} x={0} y={480} size={32} align="center" cursor={false}/>
  </AbsoluteFill>;
};
const Seg:React.FC<{v:string;size:number}>=({v,size})=><span style={{...font,fontFamily:'Plex',fontSize:size,letterSpacing:4}}>{v}</span>;
const Dr:React.FC=()=>{
  const fr=useCurrentFrame();const v=lin(fr,0,40,0,78.7);const ghost='88.8';
  return <AbsoluteFill style={{background:BG}}>
    <Type text={'DYNAMIC RANGE  ·  AES17'} at={0} x={0} y={560} size={40} align="center" cursor={false}/>
    <div style={{position:'absolute',top:660,left:0,right:0,textAlign:'center'}}>
      <span style={{position:'absolute',left:0,right:0,opacity:.08}}><Seg v={ghost} size={250}/></span>
      <Seg v={v.toFixed(1)} size={250}/></div>
    <Type text={'dB'} at={20} x={0} y={960} size={70} align="center" cursor={false}/>
    <Type text={'milled at home: 67.9 dB'} at={44} x={0} y={1130} size={38} align="center" cursor={false}/>
    <Type text={'+11 dB'} at={58} x={0} y={1210} size={96} align="center"/>
  </AbsoluteFill>;
};
const End:React.FC=()=>{
  const fr=useCurrentFrame();const off=lin(fr,64,76);
  return <AbsoluteFill style={{background:BG}}>
    <AbsoluteFill style={{transform:`scale(${1-off*.98},${Math.max(.003,1-off*1.2)})`,opacity:off>.99?0:1}}>
      <Phos><OffthreadVideo src={staticFile('video/v_orbit.mp4')} playbackRate={.8} muted style={{width:'100%',height:'100%',objectFit:'cover'}}/></Phos>
      <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(2,6,4,.9) 0%,rgba(2,6,4,0) 35%,rgba(2,6,4,0) 65%,rgba(2,6,4,.9) 100%)'}}/>
      <Type text={'PCBs BY PCBWay'} at={4} x={0} y={330} size={76} align="center"/>
      <Type text={'vinyl-adc.madsrudolph.dev'} at={26} x={0} y={1560} size={34} align="center" cursor={false}/>
      <Type text={'music: Cyborg Ninja · Kevin MacLeod · CC BY 4.0'} at={30} x={0} y={1620} size={22} align="center" cursor={false}/>
    </AbsoluteFill>
    <AbsoluteFill style={{display:'flex',alignItems:'center',justifyContent:'center'}}><div style={{width:14,height:14,borderRadius:7,background:P,boxShadow:`0 0 30px ${P}`,opacity:off>.95?lin(fr,76,88,1,0):0}}/></AbsoluteFill>
  </AbsoluteFill>;
};

export const Scope:React.FC=()=>{
  useFonts();
  const C:Record<string,React.ReactNode>={on:<On/>,wave:<Wave/>,bits:<Bits/>,
    board:<Board img="img/20261021_000924.jpg" title="MADE BY PCBWay" sub="4 layers · 140 × 136 mm"/>,
    holes:<Board img="img/20261021_001213.jpg" title="649 PLATED HOLES" sub="per board" from={1.25} to={1.5}/>,
    layers:<Layers/>,fft:<Fft/>,tone:<Tone/>,resp:<Resp/>,dr:<Dr/>,end:<End/>};
  return <AbsoluteFill style={{background:BG}}>
    <style>{fontCss}</style>
    {SCENES.map(([k,b])=><Sequence key={k} from={START[k]} durationInFrames={bars(b)}><Rgb at={0}>{C[k]}</Rgb></Sequence>)}
    <Scan/>
    <Audio src={staticFile('audio/music_scope.wav')} volume={.9}/>
    {SCENES.slice(1).map(([k])=><S key={k} src="glitch" at={START[k]-2} vol={.25}/>)}
    <S src="impact" at={START.dr} vol={.5}/>
  </AbsoluteFill>;
};
