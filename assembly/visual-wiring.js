/* Read-only bench instructions. No instrument-control API is used here. */
(() => {
  'use strict';
  const root = document.getElementById('visual-wiring');
  if (!root) return;
  const e = v => String(v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const P = (board, ref, pin, net) => ({board, ref, pin:String(pin), net});
  const I = (label, color, stripe=false) => ({label, color, stripe});
  const leads = {
    red:I('KORAD red (+)', '#ff7772'), black:I('KORAD black (−)', '#a9b1b9'),
    ground:I('W1 coax shield / ground', '#a9b1b9'), w1:I('W1 coax centre / signal', '#f6d660'),
    vp:I('AD3 V+ · red', '#ff7772'),
    c1:I('Scope 1 probe TIP', '#ffad61'), c1n:I('Scope 1 GROUND CLIP', '#ffad61', true),
    c2:I('Scope 2 probe TIP', '#75b6ff'), c2n:I('Scope 2 GROUND CLIP', '#75b6ff', true),
  };
  const W = (lead, to, note='') => ({from:leads[lead], to, color:leads[lead].color, stripe:leads[lead].stripe, note});
  const link = (from, to, label, color='#c1ed8f') => ({from, to, label, color, note:'Insulated jumper wire. Install only with all supplies and W1 off.'});
  const powerGrounds = () => [
    W('black',P('power','J3',1,'GND')), W('ground',P('power','J3',3,'GND')),
    W('c1n',P('power','J3',5,'GND')), W('c2n',P('power','J3',7,'GND')),
  ];
  const digitalGrounds = () => [
    W('black',P('digital','J2',2,'GND')), W('ground',P('digital','J4',1,'GND')),
    W('c1n',P('digital','J4',3,'GND')), W('c2n',P('digital','J4',5,'GND')),
  ];
  const modeLink = () => link(P('digital','J1',2,'Net-(J1-Pin_2)'),P('digital','J1',3,'GPCLK0'),'J1 shunt · pins 2–3','#e6c3ff');
  const ties = (ql=0,qr=0) => [
    link(P('digital','J4',12,'QL'),P('digital','J4',ql?2:11,ql?'+5V':'GND'),`QL tie → ${ql?'+5V':'GND'}`),
    link(P('digital','J4',14,'QR'),P('digital','J4',qr?2:13,qr?'+5V':'GND'),`QR tie → ${qr?'+5V':'GND'}`),
  ];
  const digitalBase = (ql=0,qr=0) => [
    ...digitalGrounds(), W('red',P('digital','J2',1,'+5V')),
    W('vp',P('digital','J2',3,'+3V3')), W('w1',P('digital','J2',7,'GPCLK0')),
    modeLink(), ...ties(ql,qr),
  ];
  const scopePairs = [
    ['Clock input / MCLK',P('digital','U4',10,'CLK6M'),P('digital','J4',8,'MCLK'),'CH1: 6.144 MHz / 5 V logic. CH2: 1.536 MHz / 5 V logic.','100 ns/div'],
    ['BCLK / Pi BCLK',P('digital','U4',9,'BCLK'),P('digital','J2',4,'PI_BCLK'),'CH1: 3.072 MHz / 5 V logic. CH2: 3.072 MHz / 3.3 V logic. Same polarity.','100 ns/div'],
    ['LRCLK / Pi LRCLK',P('digital','U4',4,'LRCLK'),P('digital','J2',5,'PI_LRCLK'),'CH1: 48 kHz / 5 V logic. CH2: 48 kHz / 3.3 V logic. Same polarity.','5 µs/div'],
    ['Clock input / pump',P('digital','U4',10,'CLK6M'),P('digital','J4',10,'PUMP'),'CH1: 6.144 MHz / 5 V logic. CH2: 192 kHz / 5 V logic.','2 µs/div'],
  ];
  const steps = [
    {id:'probe-check', phase:'Power',title:'Connect and compensate your two BNC probes', boards:[],
      brief:'Connect probes to Scope 1 and Scope 2, and the coax to Wavegen W1. No PCB connected. Use the proper breakout at the free coax end.',
      settings:[['BNC adapter','Both scope coupling jumpers = DC'],['W1 adapter jumper','0 Ω source impedance · no 50 Ω terminator'],['Probe switches + software','Both physical probes 10×; WaveForms CH1 and CH2 attenuation 10×'],['W1','Square · 1 kHz · amplitude 0.5 V · offset +0.5 V']],
      on:'Korad off and disconnected. W1 RUN; both Scope channels DC, roughly 0.2 V/div and 200 µs/div. V+ and V− off. If a probe has compensation adjustment, tune for a flat square-wave top using its instructions.',
      expected:'Both channels read about 0–1 V at 1 kHz. Rounded or peaked tops indicate compensation to adjust. A reading wrong by 10× usually means the physical probe and software attenuation disagree. Stop W1 before the next step.',
      wires:()=>[W('c1',leads.w1),W('c1n',leads.ground),W('c2',leads.w1),W('c2n',leads.ground)],help:'bnc-setup'},

    {id:'pump-check', phase:'Power',title:'Check the Wavegen coax output', boards:[],
      brief:'No PCB connected. Connect the probe tip and ground clip to the coax breakout as shown and verify the pump clock.',
      settings:[['Korad','OFF · disconnected'],['W1','Square · 192 kHz · 50%'],['Amplitude / offset','2.5 V / +2.5 V → 0–5 V'],['Scope','CH1 · DC · 1 V/div · 2 µs/div']],
      on:'With no PCB connected, run W1 and Scope. V+, V−, W2 and all digital outputs stay off.',
      expected:'CH1: about 192 kHz, low near 0 V, high near +5 V. Stop W1 before connecting the power board.',
      wires:()=>[W('c1',leads.w1),W('c1n',leads.ground)], help:'vw-power-limits'},
    {id:'power-rails', phase:'Power', title:'Connect the power board', boards:['power'],
      brief:'The Korad supplies +5 V. W1 clocks the charge pump. The Scope 2 probe tip measures the generated negative rail.',
      settings:[['Korad','5.00 V · limit 0.100 A'],['W1','Square · 192 kHz · 50%'],['Amplitude / offset','2.5 V / +2.5 V → 0–5 V'],['Scope','DC · 1 V/div · Auto trigger']],
      on:'After inspecting all wires: Korad ON, confirm CV, then start W1 promptly. V+, V− and W2 stay off.',
      expected:'CH1: +4.75…+5.25 V. CH2: −5.25…−3.50 V. A negative number is correct. Persistent CC or heating: switch off.',
      wires:()=>[...powerGrounds(),W('red',P('power','J3',2,'+5V')),W('w1',P('power','J3',10,'PUMP')),W('c1',P('power','C1',1,'+5V'),'Probe C1 positive lead/pad. Do not bridge to its other pad.'),W('c2',P('power','J3',16,'-5V'))],help:'vw-power-limits'},
    {id:'power-refs', phase:'Power',title:'Move just the two probe tips', boards:['power'],
      brief:'Switch off first. Keep the six supply, ground and pump wires. Move the Scope 1 and Scope 2 probe tips to the reference outputs.',
      settings:[['Korad','5.00 V · limit 0.100 A'],['W1','192 kHz · 0–5 V · unchanged'],['Scope','CH1 and CH2 · DC · 1 V/div'],['Other AD3 outputs','V+, V−, W2 and DIO outputs OFF']],
      on:'Korad ON → confirm CV → W1 RUN. Wait about one second before reading.',
      expected:'CH1: +2.35…+2.65 V. CH2: −2.65…−2.35 V. Each should be within 3% of ±half your measured +5 V supply.',
      wires:()=>[...powerGrounds(),W('red',P('power','J3',2,'+5V')),W('w1',P('power','J3',10,'PUMP')),W('c1',P('power','J3',4,'VREF_P')),W('c2',P('power','J3',6,'VREF_N'))],help:'vw-power-limits'},
    {id:'clock-check', phase:'Digital',title:'Check the temporary oscillator and 3.3 V supply', boards:[],
      brief:'Disconnect the power board completely. No PCB is connected while checking these AD3 outputs.',
      settings:[['Korad','OFF · disconnected'],['W1','Square · 6.144 MHz · 50%'],['Amplitude / offset','1.65 V / +1.65 V → 0–3.3 V'],['AD3 Supplies','V+ = +3.30 V · V− OFF']],
      on:'With no PCB connected, run W1, enable V+ and run Scope (≥50 MS/s, about 50 ns/div, DC). Stop W1 and V+ before wiring the board.',
      expected:'CH1: 6.144 MHz, lows below 0.8 V, highs above 2 V, overall approximately 0–3.3 V. Rounded edges are possible. CH2: steady +3.15…+3.45 V.',
      wires:()=>[W('c1',leads.w1),W('c1n',leads.ground),W('c2',leads.vp),W('c2n',leads.ground)],help:'vw-digital-limits'},
    {id:'digital-rails', phase:'Digital',title:'Connect the digital board — X1 stays empty',boards:['digital'],
      brief:'Fit J1 across pins 2–3. Keep QL and QR tied low. The Korad and AD3 V+ supply different rails.',
      settings:[['Korad','5.00 V · limit 0.100 A'],['AD3 V+','+3.30 V'],['W1','6.144 MHz · 0–3.3 V'],['Scope','Both channels DC · 1 V/div']],
      on:'AD3 V+ ON → Korad ON, confirm CV → W1 RUN promptly. V−, W2 and all DIO outputs remain off.',
      expected:'CH1 at C9: +4.75…+5.25 V. CH2 at C15: +3.15…+3.45 V. Record current; stop for CC or heating.',
      wires:()=>[...digitalBase(),W('c1',P('digital','C9',1,'+5V')),W('c2',P('digital','C15',1,'+3V3'))],help:'vw-digital-limits'},
    {id:'digital-clocks',phase:'Digital',title:'Check four clock pairs',boards:['digital'],
      brief:'Choose a clock pair below. Only the two probe tips move; the supplies, W1, J1 and QL/QR ties remain.',
      settings:[['Korad / V+','5.00 V / +3.30 V'],['W1','6.144 MHz · 0–3.3 V'],['Scope','DC · ≥50 MS/s · 1 V/div']],
      on:'After each unpowered probe change: V+ ON → Korad ON → W1 RUN. Scope Auto trigger; adjust timebase for the selected pair.',
      expected:()=>scopePairs[pair][3]+' Frequency screen ±2%; duty 35–65%. Pi output highs must be 2.7–3.6 V.',
      wires:()=>[...digitalBase(),W('c1',scopePairs[pair][1]),W('c2',scopePairs[pair][2])],help:'vw-digital-limits'},
    {id:'digital-mux',phase:'Digital',title:'Check the four data combinations',boards:['digital'],
      brief:'Select each QL/QR case. The diagram changes the jumper endpoints. No channel boards may be connected.',
      settings:[['Korad / V+','5.00 V / +3.30 V'],['W1','6.144 MHz · 0–3.3 V'],['Scope','DC · ≥50 MS/s · 200 ns/div']],
      on:'All power off for each jumper or probe change. Then V+ ON → Korad ON → W1 RUN. Check all four cases for both raw and Pi data.',
      expected:()=>`CH1 is MCLK. CH2 (${raw?'raw DIN, 5 V logic':'PI_DIN, 3.3 V logic'}) should ${['stay LOW','follow MCLK','invert MCLK','stay HIGH'][mux]}. Judge after the switching edges.`,
      wires:()=>[...digitalBase(...[[0,0],[1,0],[0,1],[1,1]][mux]),W('c1',P('digital','J4',8,'MCLK')),W('c2',raw?P('digital','U6',4,'DIN'):P('digital','J2',6,'PI_DIN'))],help:'vw-digital-limits'},
    {id:'together-rails',phase:'Together',title:'Connect the tested boards with three jumper wires',boards:['digital','power'],
      brief:'Digital now drives PUMP. W1 connects to digital J2.7 only—remove the old W1-to-power-J3.10 connection.',
      settings:[['Korad / V+','5.00 V, 0.100 A / +3.30 V'],['W1','6.144 MHz · 0–3.3 V'],['Scope','DC · 1 V/div · Auto trigger']],
      on:'Use the three illustrated bus wires; do not also stack the boards for this fixture. V+ ON → Korad ON → W1 RUN. Channels and Pi remain disconnected.',
      expected:'CH1: +4.75…+5.25 V. CH2: −5.25…−3.50 V. The negative rail is now generated using the digital board’s pump output.',
      wires:()=>combined(false),help:'vw-power-limits'},
    {id:'together-refs',phase:'Together',title:'Check the references with both boards connected',boards:['digital','power'],
      brief:'Keep all supply, clock and inter-board wires. Move only the two probe tips after powering off.',
      settings:[['Korad / V+','5.00 V, 0.100 A / +3.30 V'],['W1','6.144 MHz · 0–3.3 V'],['Scope','DC · 1 V/div · Auto trigger']],
      on:'V+ ON → Korad ON → W1 RUN. Record references and supply current, then shut down. Stop here until channel decoupling is complete.',
      expected:'CH1: +2.35…+2.65 V. CH2: −2.65…−2.35 V. This does not yet prove full-stereo load capacity or audio conversion.',
      wires:()=>combined(true),help:'vw-power-limits'},
  ];
  function combined(refs) {
    return [...digitalBase(),
      link(P('digital','J4',7,'GND'),P('power','J3',1,'GND'),'Bus wire · GND', '#a9b1b9'),
      link(P('digital','J4',2,'+5V'),P('power','J3',2,'+5V'),'Bus wire · +5 V', '#ff7772'),
      link(P('digital','J4',10,'PUMP'),P('power','J3',10,'PUMP'),'Bus wire · PUMP', '#f6d660'),
      W('c1',refs?P('power','J3',4,'VREF_P'):P('power','C1',1,'+5V')),
      W('c2',refs?P('power','J3',6,'VREF_N'):P('power','J3',16,'-5V'))];
  }
  let boards, step=0, active=0, pair=0, mux=0, raw=false;
  const label = p => p.board ? `${p.board==='power'?'Power':'Digital'} ${p.ref}.${p.pin}` : p.label;
  const pad = p => boards[p.board].parts.find(x=>x.ref===p.ref)?.pads.find(x=>x.pin===p.pin);
  const current = () => steps[step];
  function validate(wires) {
    for(const w of wires) for(const p of [w.from,w.to]) if(p.board) {
      const found=pad(p); if(!found || found.net!==p.net) throw Error(`PCB data mismatch at ${label(p)}. Do not use this wiring diagram.`);
    }
  }
  function render() {
    const s=current(), wires=s.wires(); validate(wires); active=Math.min(active,wires.length-1);
    root.innerHTML=`<div class="vw-phase" role="group" aria-label="Test phase">${['Power','Digital','Together'].map(p=>`<button data-vw-phase="${p}" class="${p===s.phase?'selected':''}">${p==='Power'?'1 · Power board':p==='Digital'?'2 · Digital board':'3 · Both boards'}</button>`).join('')}</div>
      <div class="vw-stepbar"><label>Test step <select id="vw-step">${steps.map((x,i)=>`<option value="${i}" ${i===step?'selected':''}>${i+1}. ${e(x.title)}</option>`).join('')}</select></label><span>${step+1} / ${steps.length}</span></div>
      <h2 class="vw-title">${e(s.title)}</h2><p class="vw-brief">${e(s.brief)}</p>
      <div class="vw-off"><strong>WIRE ONLY WITH EVERYTHING OFF</strong><span>Korad POWER off → W1 stopped → V+ off → verify rails discharged. Clicking this guide does not control your equipment.</span></div>
      ${s.id==='digital-clocks'?`<label class="vw-variant">Probe pair <select id="vw-pair">${scopePairs.map((p,i)=>`<option value="${i}" ${pair===i?'selected':''}>${e(p[0])}</option>`).join('')}</select> Start at ${scopePairs[pair][4]}. Power off before moving probes.</label>`:''}
      ${s.id==='digital-mux'?`<div class="vw-variant"><label>QL / QR <select id="vw-mux">${['0 / 0','1 / 0','0 / 1','1 / 1'].map((v,i)=>`<option value="${i}" ${mux===i?'selected':''}>${v}</option>`).join('')}</select></label><label>Measure <select id="vw-raw"><option value="pi" ${!raw?'selected':''}>Pi data · 3.3 V</option><option value="raw" ${raw?'selected':''}>Raw data · 5 V</option></select></label><strong>Power off before changing ties.</strong></div>`:''}
      <div class="vw-work"><div class="vw-leads"><p class="eyebrow">COMPLETE WIRING FOR THIS STEP</p><p class="muted">Select a wire to see both ends.</p>${wires.map((w,i)=>`<button class="vw-lead ${i===active?'selected':''}" data-vw-wire="${i}" aria-pressed="${i===active}"><span class="vw-number" style="--wire:${w.color}">${i+1}</span><span><strong>${e(w.label||label(w.from))}</strong><small>→ ${e(label(w.to))}${w.to.net?' · '+e(w.to.net):''}</small></span></button>`).join('')}</div>
      <div class="vw-drawing"><div class="vw-maphead"><strong>${s.boards.length?'COMPONENT SIDE · LOOK DOWN FROM ABOVE':'AD3 LEADS ONLY · NO PCB'}</strong><span>${s.boards.length?'Same X/Y orientation as KiCad. Do not flip the board.':'Match the printed lead labels.'}</span></div><div id="vw-map"></div><div id="vw-selected"></div></div></div>
      <div class="vw-bottom"><button id="vw-prev-wire" ${active===0?'disabled':''}>← Previous wire</button><strong>Wire ${active+1} / ${wires.length}</strong><button id="vw-next-wire" ${active===wires.length-1?'disabled':''}>Next wire →</button></div>
      <div class="vw-instructions"><div><h3>Set WaveForms and the Korad</h3><dl>${s.settings.map(([a,b])=>`<dt>${e(a)}</dt><dd>${e(b)}</dd>`).join('')}</dl></div><div><h3>Once every connection is checked</h3><p>${e(s.on)}</p><h3>What you should see</h3><p class="vw-expect">${e(typeof s.expected==='function'?s.expected():s.expected)}</p><p class="muted">Screening limits are provisional. “Next test” does not record a hardware PASS.</p></div></div>
      <div class="vw-testnav"><button id="vw-prev" ${step===0?'disabled':''}>← Previous test</button><a href="#${s.help}">Measurement limits</a><button id="vw-next" ${step===steps.length-1?'disabled':''}>Next test →</button></div>
      <p class="vw-footnote">Use <strong>WaveForms manually</strong> with this guide. Do not run the Step 10 SDK tests at the same time. Orange = Scope 1, blue = Scope 2 in this drawing (not necessarily your probe body colours). Dashed lines are probe ground clips. Yellow = coax centre conductor. Grey = coax shield or Korad return. All clips/shields go to circuit GND, never to −5 V.</p>`;
    draw(wires);
  }
  function boardSVG(name, x,y,size, wires) {
    const b=boards[name], [bx,by,bw,bh]=b.bounds, scale=size/Math.max(bw,bh), xy=a=>[x+(a[0]-bx)*scale,y+(a[1]-by)*scale];
    let out=`<g><rect x="${x}" y="${y}" width="${bw*scale}" height="${bh*scale}" rx="4" fill="#132920" stroke="#729280" stroke-width="2"/><text x="${x}" y="${y-15}" class="vw-svg-title">${name==='power'?'POWER BOARD':'DIGITAL BOARD'}</text>`;
    out+=b.tracks.map(t=>{const a=xy(t.a),c=xy(t.b);return `<path d="M${a} L${c}" stroke="${t.layer==='top'?'#74533d':'#305747'}" stroke-width="1" fill="none" opacity=".55"/>`}).join('');
    for(const p of b.parts) {
      if(!p.pads.length)continue;
      const pts=p.pads.map(q=>xy(q.at)),xs=pts.map(a=>a[0]),ys=pts.map(a=>a[1]);
      if(p.kind!=='mount')out+=`<rect x="${Math.min(...xs)-4}" y="${Math.min(...ys)-4}" width="${Math.max(...xs)-Math.min(...xs)+8}" height="${Math.max(...ys)-Math.min(...ys)+8}" rx="2" fill="${p.kind==='socket'?'#15221d':'none'}" stroke="#4a6355" stroke-width=".6"/>`;
      p.pads.forEach((q,i)=>{
        const a=pts[i], r=p.kind==='mount'?1.6*scale:Math.max(1.7,.55*scale);
        const selected=[wires[active].from,wires[active].to].some(z=>z.board===name&&z.ref===p.ref&&z.pin===q.pin);
        out+=q.pin==='1'?`<rect x="${a[0]-r}" y="${a[1]-r}" width="${2*r}" height="${2*r}" fill="#a3b4a1"/>`:`<circle cx="${a[0]}" cy="${a[1]}" r="${r}" fill="#a3b4a1"/>`;
        out+=`<circle cx="${a[0]}" cy="${a[1]}" r="${p.kind==='mount'?r*.8:Math.max(.65,.23*scale)}" fill="#0d1711"/>`;
        if(selected)out+=`<circle cx="${a[0]}" cy="${a[1]}" r="9" fill="none" stroke="${wires[active].color}" stroke-width="2.5"/>`;
      });
      if(p.kind!=='wire')out+=`<text x="${Math.min(...xs)}" y="${Math.min(...ys)-7}" class="vw-svg-ref">${e(p.ref)}</text>`;
    }
    out+=`<text x="${x}" y="${y+size+20}" class="vw-svg-note">Pad locations from your KiCad PCB · outline ${bw.toFixed(1)} × ${bh.toFixed(1)} mm</text></g>`;
    return {svg:out,xy};
  }
  function draw(wires) {
    const s=current(), dual=s.boards.length===2, has=s.boards.length>0;
    const width=dual?1100:900, height=has?Math.max(555,wires.length*30+75):400;
    const maps={}; let bsvg='';
    s.boards.forEach((b,i)=>{const result=boardSVG(b,dual?400+i*345:410,70,dual?310:425,wires);bsvg+=result.svg;maps[b]=result.xy;});
    const points=new Map(); let sources='';
    // Each wire gets a labelled source row, even if it is an inter-board jumper.
    wires.forEach((w,i)=>{
      const yy=has?65+i*30:85+i*72;
      const xx=has?20:35, ww=has?265:300;
      points.set(w,{start:[xx+ww,yy+12]});
      sources+=`<g data-vw-wire="${i}" class="vw-svg-source"><rect x="${xx}" y="${yy-2}" width="${ww}" height="28" rx="5" fill="${i===active?'#2a3a30':'#17231e'}" stroke="${i===active?w.color:'#3a4b41'}"/><text x="${xx+9}" y="${yy+17}" class="vw-svg-label">${i+1} · ${e(w.label||label(w.from))}</text><circle cx="${xx+ww}" cy="${yy+12}" r="4" fill="${w.color}"/></g>`;
      if(!has){
        const xx2=585;points.get(w).end=[xx2,yy+12];
        sources+=`<rect x="${xx2}" y="${yy-2}" width="280" height="28" rx="5" fill="#17231e" stroke="${w.color}"/><text x="${xx2+12}" y="${yy+17}" class="vw-svg-label">${e(label(w.to))}</text>`;
      }
    });
    let paths='';
    [...wires.map((w,i)=>({w,i})).filter(x=>x.i!==active),{w:wires[active],i:active}].forEach(({w,i})=>{
      const row=points.get(w), to=w.to.board?maps[w.to.board](pad(w.to).at):row.end;
      const from=w.from.board?maps[w.from.board](pad(w.from).at):row.start;
      const d=w.from.board?`M${from} Q${(from[0]+to[0])/2},${Math.min(from[1],to[1])-38} ${to}`:`M${from} C${from[0]+65},${from[1]} ${to[0]-65},${to[1]} ${to}`;
      paths+=`<g opacity="${i===active?1:.15}"><path d="${d}" stroke="#07110c" stroke-width="${i===active?7:4}" fill="none"/><path d="${d}" stroke="${w.color}" stroke-width="${i===active?3.5:2}" fill="none"/>${w.stripe?`<path d="${d}" stroke="white" stroke-width="1.5" stroke-dasharray="6 5" fill="none"/>`:''}<circle cx="${to[0]}" cy="${to[1]}" r="5" fill="${w.color}" stroke="#0c170f" stroke-width="2"/>${w.from.board?`<circle cx="${from[0]}" cy="${from[1]}" r="5" fill="${w.color}"/>`:''}</g>`;
    });
    document.getElementById('vw-map').innerHTML=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${e(s.title)}: highlighted wire ${active+1}, ${e(label(wires[active].from))} to ${e(label(wires[active].to))}">${bsvg}${paths}${sources}${!has?'<text x="35" y="32" class="vw-svg-title">SCOPE LEAD</text><text x="585" y="32" class="vw-svg-title">AD3 OUTPUT / GROUND LEAD</text>':''}</svg>`;
    const w=wires[active];
    const shared=w.to.board&&wires.filter(x=>[x.from,x.to].some(z=>z.board===w.to.board&&z.ref===w.to.ref&&z.pin===w.to.pin)).length>1;
    document.getElementById('vw-selected').innerHTML=`<div class="vw-connection" style="--wire:${w.color}"><span>WIRE ${active+1}</span><strong>${e(label(w.from))} <b>→</b> ${e(label(w.to))}</strong>${w.note?`<p>${e(w.note)}</p>`:''}${shared?'<p>This pad is shared in this fixture. Use a secure insulated fan-out or grabber on the existing connection; do not force multiple sockets onto one pin or bridge neighbouring pins.</p>':''}</div><div class="vw-zooms">${endpoint(w.from,w.color,'START HERE')}${endpoint(w.to,w.color,'CONNECT HERE')}</div>`;
  }
  function endpoint(p,color,title) {
    if(!p.board){
      const tip=p.label.includes('probe TIP'),clip=p.label.includes('GROUND CLIP'),coax=p.label.includes('coax');
      let picture, note;
      if(tip){
        picture=`<path d="M10 104 H70" stroke="#69766e" stroke-width="9"/><rect x="65" y="80" width="126" height="46" rx="17" fill="#34443b" stroke="#9dad9f" stroke-width="2"/><rect x="81" y="80" width="8" height="46" fill="${color}"/><path d="M191 88 L245 98 L245 108 L191 118 Z" fill="#687c6e"/><path d="M245 103 H283" stroke="#d5d9c1" stroke-width="4"/><path d="M280 103 v-14 h-8" fill="none" stroke="${color}" stroke-width="3"/><text x="78" y="109" class="vw-svg-label">10× PROBE</text><path d="M135 126 C140 155 200 148 210 170" fill="none" stroke="#829084" stroke-width="3"/><text x="17" y="44" class="vw-svg-title">HOOK / TIP = SIGNAL</text><path d="M275 58 V80" stroke="${color}" stroke-width="2"/><text x="100" y="197" class="vw-svg-note">Ground clip is a separate connection.</text>`;
        note='The hook/tip contacts the highlighted pad or component lead. The short ground clip stays on the separately shown GND pad. Use the 10× setting on the probe and in WaveForms.';
      }else if(clip){
        picture=`<path d="M15 100 H110" stroke="#84978a" stroke-width="5"/><rect x="105" y="85" width="85" height="32" rx="6" fill="#35473b" stroke="#91a58f"/><path d="M190 87 L271 101 L190 101 Z M190 118 L271 108 L190 105 Z" fill="#b9c5b4"/><path d="M227 105 L236 111 L245 105 L254 111" fill="none" stroke="#536654" stroke-width="2"/><circle cx="149" cy="101" r="6" fill="${color}"/><text x="20" y="44" class="vw-svg-title">GROUND CLIP = GND ONLY</text>`;
        note='This is the short alligator clip attached to the probe body. It is internally connected to AD3/BNC ground. Never clip it to the negative rail or a clock output.';
      }else if(coax){
        picture=`<path d="M10 105 H115" stroke="#65786a" stroke-width="18"/><rect x="110" y="83" width="65" height="44" rx="6" fill="#a4b5a6"/><path d="M175 105 H265" stroke="#f6d660" stroke-width="4"/><path d="M170 122 C205 135 228 154 265 157" stroke="#adb7ad" stroke-width="4" fill="none"/><circle cx="265" cy="105" r="6" fill="#f6d660"/><circle cx="265" cy="157" r="6" fill="#adb7ad"/><text x="18" y="45" class="vw-svg-title">W1 COAX BREAKOUT</text><text x="186" y="91" class="vw-svg-label">centre: signal</text><text x="184" y="183" class="vw-svg-label">shield: GND</text><circle cx="265" cy="${p.label.includes('shield')?157:105}" r="13" stroke="${color}" stroke-width="3" fill="none"/>`;
        note='Use a suitable BNC breakout at the board end. The picture identifies electrical conductors, not an instruction to cut the cable. Centre = W1; outer shield = GND.';
      }else{
        picture=`<path d="M18 110 H175" stroke="${color}" stroke-width="8"/><rect x="166" y="96" width="70" height="29" rx="4" fill="#34473b" stroke="${color}" stroke-width="3"/><path d="M236 110 H279" stroke="#d3dccb" stroke-width="4"/><text x="18" y="54" class="vw-svg-title">${e(p.label)}</text>`;
        note=p.label.includes('V+')?'Use the remaining V+ flywire from the adapter pass-through. Set AD3 V+ to 3.30 V for the digital board.':'This is a Korad DC output lead. Red is +5 V; black is the circuit GND return. The green earth terminal is not a second supply output.';
      }
      return `<div class="vw-end"><p class="eyebrow">${title}</p><h3>${e(p.label)}</h3><svg viewBox="0 0 310 215" role="img" aria-label="${e(p.label)} illustration">${picture}</svg><p>${e(note)}</p></div>`;
    }
    const part=boards[p.board].parts.find(x=>x.ref===p.ref), pads=part.pads, dest=pad(p);
    const xs=pads.map(a=>a.at[0]),ys=pads.map(a=>a.at[1]),minx=Math.min(...xs),miny=Math.min(...ys),w=Math.max(...xs)-minx,h=Math.max(...ys)-miny;
    const scale=Math.min(38,330/(w+5),180/(h+5));
    const sx=a=>65+(a[0]-minx)*scale, sy=a=>52+(a[1]-miny)*scale;
    const vh=h*scale+115,vw=Math.max(230,w*scale+130);
    let svg=`<svg viewBox="0 0 ${vw} ${vh}" role="img" aria-label="${e(label(p))} close-up, component side, pin ${p.pin} highlighted"><rect x="42" y="28" width="${w*scale+46}" height="${h*scale+48}" rx="7" fill="#172b20" stroke="#658471"/>`;
    pads.forEach(a=>{const xx=sx(a.at),yy=sy(a.at),hit=a.pin===p.pin,r=8;
      svg+=a.pin==='1'?`<rect x="${xx-r}" y="${yy-r}" width="16" height="16" fill="${hit?color:'#9aab98'}"/>`:`<circle cx="${xx}" cy="${yy}" r="8" fill="${hit?color:'#9aab98'}"/>`;
      svg+=`<circle cx="${xx}" cy="${yy}" r="2.8" fill="#0c1710"/><text x="${xx}" y="${yy-14}" text-anchor="middle" class="vw-pin-label">${e(a.pin)}</text>`;
      if(hit)svg+=`<circle cx="${xx}" cy="${yy}" r="14" fill="none" stroke="${color}" stroke-width="3"/><path d="M${xx},${yy+43} L${xx},${yy+18} m-5,7 5,-7 5,7" fill="none" stroke="${color}" stroke-width="3"/>`;
    });
    svg+='</svg>';
    return `<div class="vw-end"><p class="eyebrow">${title} · ${e(p.board.toUpperCase())} BOARD</p><h3>${e(p.ref)} <span>pin ${e(p.pin)} · ${e(p.net)}</span></h3>${svg}<p><strong>Square pad = pin 1.</strong> Same orientation as the full board above. Highlighted pad: KiCad X ${dest.at[0]}, Y ${dest.at[1]} mm.</p></div>`;
  }
  root.addEventListener('click',event=>{
    const wire=event.target.closest('[data-vw-wire]'), phase=event.target.closest('[data-vw-phase]');
    let scroll=false;
    if(wire)active=Number(wire.dataset.vwWire);
    else if(phase){step=steps.findIndex(x=>x.phase===phase.dataset.vwPhase);active=0;scroll=true;}
    else if(event.target.id==='vw-next-wire')active++;
    else if(event.target.id==='vw-prev-wire')active--;
    else if(event.target.id==='vw-next'){step++;active=0;scroll=true;}
    else if(event.target.id==='vw-prev'){step--;active=0;scroll=true;}
    else return;
    render();if(scroll)root.scrollIntoView({block:'start'});
  });
  root.addEventListener('change',event=>{
    if(event.target.id==='vw-step'){step=Number(event.target.value);active=0;}
    else if(event.target.id==='vw-pair'){pair=Number(event.target.value);active=10;}
    else if(event.target.id==='vw-mux'){mux=Number(event.target.value);active=8;}
    else if(event.target.id==='vw-raw'){raw=event.target.value==='raw';active=11;}
    else return;render();
  });
  document.addEventListener('click',event=>{
    if(!event.target.closest('[data-vw-resume="digital-mux"]') || !boards)return;
    step=steps.findIndex(s=>s.id==='digital-mux');mux=1;raw=false;active=8;
    render();root.scrollIntoView({block:'start'});
  });
  fetch('generated/boards.json').then(r=>{if(!r.ok)throw Error('Cannot load the PCB data');return r.json();}).then(d=>{
    boards=d.boards;
    // Validate every variant before allowing any graphical instructions.
    for(const s of steps)for(pair=0;pair<scopePairs.length;pair++)for(mux=0;mux<4;mux++)for(const v of [false,true]){raw=v;validate(s.wires());}
    pair=0;mux=0;raw=false;render();
    root.dataset.ready='true';
  }).catch(error=>{root.innerHTML=`<div class="warning"><strong>Wiring guide unavailable.</strong> ${e(error.message)} Reload the local server and verify the PCB revision before wiring.</div>`;console.error(error);});
})();
