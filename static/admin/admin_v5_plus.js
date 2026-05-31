(function(){
  function data(){try{return JSON.parse(document.getElementById('adminChartData')?.textContent||'{}')||{}}catch(e){return{}}}
  function empty(c,w,h){c.fillStyle='#98a2b3';c.font='13px Segoe UI';c.textAlign='center';c.fillText('표시할 데이터가 없습니다',w/2,h/2);c.textAlign='left'}
  function line(canvas,d,area){
    const c=canvas.getContext('2d'),w=canvas.clientWidth||640,h=Number(canvas.getAttribute('height'))||220,r=window.devicePixelRatio||1;
    canvas.width=w*r;canvas.height=h*r;c.scale(r,r);c.clearRect(0,0,w,h);
    const labels=Array.isArray(d.labels)?d.labels:[],values=Array.isArray(d.values)?d.values.map(v=>Number(v||0)):[],max=Math.max(...values,1),p={l:34,r:18,t:18,b:30},cw=w-p.l-p.r,ch=h-p.t-p.b;
    c.strokeStyle='#e8edf4';c.fillStyle='#738198';c.font='11px Segoe UI';
    for(let i=0;i<=4;i++){const y=p.t+ch-ch*i/4;c.beginPath();c.moveTo(p.l,y);c.lineTo(w-p.r,y);c.stroke();c.fillText(String(Math.round(max*i/4)),4,y+4)}
    if(!values.some(Boolean)){empty(c,w,h);return}
    const pts=values.map((v,i)=>({x:p.l+cw*i/Math.max(values.length-1,1),y:p.t+ch-ch*v/max}));
    if(area){const g=c.createLinearGradient(0,p.t,0,h-p.b);g.addColorStop(0,'rgba(91,141,239,.28)');g.addColorStop(1,'rgba(75,185,159,0)');c.beginPath();pts.forEach((pt,i)=>i?c.lineTo(pt.x,pt.y):c.moveTo(pt.x,pt.y));c.lineTo(pts[pts.length-1].x,h-p.b);c.lineTo(pts[0].x,h-p.b);c.closePath();c.fillStyle=g;c.fill()}
    c.beginPath();pts.forEach((pt,i)=>i?c.lineTo(pt.x,pt.y):c.moveTo(pt.x,pt.y));c.strokeStyle='#287fdb';c.lineWidth=3;c.stroke();
    pts.forEach(pt=>{c.beginPath();c.arc(pt.x,pt.y,3,0,Math.PI*2);c.fillStyle='#4bb99f';c.fill()});
    labels.forEach((label,i)=>{if(i%Math.ceil(labels.length/7||1)===0){c.fillStyle='#738198';c.fillText(label,pts[i].x-12,h-10)}})
  }
  function redraw(){const all=data();document.querySelectorAll('canvas.admin-chart.line,canvas.admin-chart.area').forEach(canvas=>{try{line(canvas,all[canvas.dataset.chart]||{},canvas.classList.contains('area'))}catch(e){const c=canvas.getContext('2d');if(c)empty(c,canvas.clientWidth||320,Number(canvas.getAttribute('height'))||180)}})}
  function installStudentFilters(){const buttons=document.querySelectorAll('.js-student-filter');buttons.forEach(button=>button.addEventListener('click',()=>{buttons.forEach(x=>x.classList.remove('active'));button.classList.add('active');const f=button.dataset.filter||'all';document.querySelectorAll('.student-data-row').forEach(row=>{const a=row.dataset.hasAllergy==='1',r=row.dataset.hasRfid==='1';row.hidden=!(f==='all'||f==='allergy'&&a||f==='no-allergy'&&!a||f==='rfid'&&r||f==='no-rfid'&&!r)})}))}
  function installUploadName(){const input=document.getElementById('mealFileInput'),label=document.getElementById('mealFileName');if(!input||!label)return;input.addEventListener('change',()=>{const file=input.files&&input.files[0];if(!file){label.textContent='선택된 파일 없음';return}label.textContent=`${file.name} · ${Math.max(1,Math.round(file.size/1024))}KB`;label.classList.remove('muted');label.classList.add('info')})}
  document.addEventListener('DOMContentLoaded',()=>{installStudentFilters();installUploadName();setTimeout(redraw,40)});
  window.addEventListener('resize',()=>setTimeout(redraw,160));
})();
