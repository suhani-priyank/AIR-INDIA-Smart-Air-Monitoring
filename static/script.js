let map, mapMarkers = {}, selectedStation = null, trendChart, heatLayer;
let stationPoints = [], routeLayers = [];
const $ = id => document.getElementById(id);

const colors = {Good:'#00a65a',Satisfactory:'#8bc34a',Moderate:'#ff9800',Poor:'#f44336','Very Poor':'#9c27b0',Severe:'#111'};
function statusColor(s){ return colors[s] || '#607d8b'; }
function fmt(v,d=1){ return v === null || v === undefined ? '--' : Number(v).toFixed(d); }
async function getJSON(url){ const r=await fetch(url); if(!r.ok) throw new Error(await r.text()); return r.json(); }

function initMap(){
  map = L.map('map').setView([22.9734,78.6569],5);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors'}).addTo(map);
}
function markerIcon(aqi){
  const color=statusColor(aqiStatus(aqi));
  return L.divIcon({className:'aqi-marker',html:`<div style="background:${color}">${aqi ?? '?'}</div>`,iconSize:[42,42],iconAnchor:[21,21]});
}
function aqiStatus(a){ if(a<=50)return'Good'; if(a<=100)return'Satisfactory'; if(a<=200)return'Moderate'; if(a<=300)return'Poor'; if(a<=400)return'Very Poor'; return'Severe'; }

async function loadMap(){
  const data=await getJSON('/api/map');
  stationPoints=data;
  Object.values(mapMarkers).forEach(m=>map.removeLayer(m)); mapMarkers={};
  data.forEach(s=>{
    const m=L.marker([s.latitude,s.longitude],{icon:markerIcon(s.aqi)}).addTo(map);
    m.bindPopup(`<b>${s.name}</b><br>${s.city}, ${s.state}<br>AQI: <b>${s.aqi ?? '--'}</b> (${s.aqi_status ?? 'No data'})`);
    m.on('click',()=>selectStationById(s.id)); mapMarkers[s.id]=m;
  });
  updateHeatmap();
}
function updateHeatmap(){
  if(heatLayer) map.removeLayer(heatLayer);
  const points=stationPoints.filter(s=>s.aqi!==null && s.aqi!==undefined).map(s=>[s.latitude,s.longitude,Math.max(.15,Math.min(1,Number(s.aqi)/500))]);
  heatLayer=L.heatLayer(points,{radius:34,blur:25,maxZoom:9,minOpacity:.25,gradient:{0.15:'#2ecc71',0.35:'#f1c40f',0.55:'#e67e22',0.75:'#e74c3c',1:'#8e44ad'}});
  if($('toggleHeatBtn').dataset.on==='1') heatLayer.addTo(map);
}

async function loadSelectors(){ const states=await getJSON('/api/states'); $('stateSelect').innerHTML=states.map(s=>`<option value="${s.id}">${s.name}</option>`).join(''); if(states[0]) await loadCities(states[0].id); }
async function loadCities(stateId){ const cities=await getJSON('/api/cities/'+stateId); $('citySelect').innerHTML=cities.map(c=>`<option value="${c.id}">${c.name}</option>`).join(''); if(cities[0]) await loadStations(cities[0].id); }
async function loadStations(cityId){ const stations=await getJSON('/api/stations/'+cityId); $('stationSelect').innerHTML=stations.map(s=>`<option value="${s.id}">${s.name}</option>`).join(''); if(stations[0]) await selectStation(stations[0].id); }
async function selectStationById(id){ $('stationSelect').value=id; await selectStation(id); }

async function selectStation(id){
  selectedStation=Number(id); localStorage.setItem('station',selectedStation);
  try{
    const data=await getJSON('/api/latest/'+selectedStation); renderLatest(data);
    await Promise.all([loadHistory(),loadSmart(),loadPrediction()]);
    const m=mapMarkers[selectedStation]; if(m){map.setView(m.getLatLng(),12);m.openPopup();}
  }catch(e){console.error(e);}
}
function renderLatest(d){
  $('aqiValue').textContent=d.aqi; $('status').textContent=d.status; $('status').style.background=statusColor(d.status);
  $('aqiMessage').textContent=d.message; $('temperature').textContent=fmt(d.temperature); $('humidity').textContent=fmt(d.humidity); $('wind').textContent=fmt(d.wind_speed);
  $('stationName').textContent=d.station; $('locationName').textContent=`${d.city}, ${d.state}`; $('lastUpdated').textContent=new Date(d.timestamp).toLocaleString();
  document.title=`${d.station} | AIR INDIA`;
}

async function loadHistory(){
  const limit=$('rangeSelect').value; const rows=await getJSON(`/api/history/${selectedStation}?limit=${limit}`);
  const labels=rows.map(r=>new Date(r.timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}));
  const ds=(key,label)=>({label,data:rows.map(r=>r[key]),borderWidth:2,tension:.3,fill:false});
  if(trendChart) trendChart.destroy();
  trendChart=new Chart($('trendChart'),{type:'line',data:{labels,datasets:[ds('mq2','MQ2'),ds('mq3','MQ3'),ds('mq135','MQ135')]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{position:'top'}},scales:{y:{beginAtZero:true,title:{display:true,text:'Sensor Value'}},x:{title:{display:true,text:'Time'}}}}});
}

async function loadPrediction(){
  const d=await getJSON('/api/predict/'+selectedStation);
  $('predictions') && ($('predictions').innerHTML=d.predictions.map(p=>`<div><span>+${p.hours_ahead}h</span><b>${p.predicted_aqi}</b><small style="color:${statusColor(p.status)}">${p.status}</small></div>`).join(''));
}

async function loadSmart(){
  const d=await getJSON('/api/smart/'+selectedStation);
  $('airSafeScore').textContent=d.airsafe.score;
  $('airSafeStatus').textContent=d.airsafe.status;
  $('airSafeBar').style.width=d.airsafe.score+'%';
  $('healthMq2').textContent=d.sensor_health.mq2+'%'; $('healthMq3').textContent=d.sensor_health.mq3+'%'; $('healthMq135').textContent=d.sensor_health.mq135+'%'; $('healthOverall').textContent=d.sensor_health.overall;
  $('eventBox').innerHTML=d.events.length ? d.events.map(e=>`<div class="smart-item danger"><b>${e.sensor}</b><span>+${e.change_percent}% above recent baseline</span><small>${e.severity} event signal</small></div>`).join('') : '<div class="ok-state">✓ No unusual pollution event signal detected.</div>';
  $('anomalyBox').innerHTML=d.anomalies.length ? d.anomalies.map(a=>`<div class="smart-item warn"><b>${a.sensor}</b><span>${a.type}</span><small>Value: ${a.value}</small></div>`).join('') : '<div class="ok-state">✓ Sensors are behaving normally.</div>';
  $('bestTime').innerHTML=d.best_windows.length ? d.best_windows.map((w,i)=>`<div class="time-row"><strong>${i===0?'⭐ ':''}${w.label}</strong><span>Avg AQI ${w.avg_aqi}</span></div>`).join('') : '<p>Not enough historical data yet.</p>';
  renderExplanation(d.explanation);
}
function renderExplanation(e){
  $('explanation').innerHTML=`<div class="explain-main"><b>AQI ${e.aqi}</b><span class="status-mini" style="background:${statusColor(e.status)}">${e.status}</span></div><p>${e.message}</p><div class="trend-chip">Recent average: ${e.recent_average} · Trend: <b>${e.trend}</b></div>`;
}
async function explainNow(){ if(!selectedStation)return; const d=await getJSON('/api/smart/'+selectedStation); renderExplanation(d.explanation); $('explanation').scrollIntoView({behavior:'smooth',block:'center'}); }

async function loadSummary(){ const d=await getJSON('/api/summary'); $('statesCount').textContent=d.totals.states; $('citiesCount').textContent=d.totals.cities; $('stationsCount').textContent=d.totals.stations; $('onlineCount').textContent=d.totals.online_stations; }
async function loadAlerts(){ const a=await getJSON('/api/alerts'); $('alertsList').innerHTML=a.length?a.map(x=>`<div class="alert"><b>${x.alert_type}</b><span>${x.city}, ${x.state}</span><small>${new Date(x.timestamp).toLocaleString()}</small><p>${x.message}</p></div>`).join(''):'<div class="ok-state">✓ No recent alerts.</div>'; }

async function buildCompare(){ const stations=await getJSON('/api/map'); $('compareList').innerHTML=stations.slice(0,40).map(s=>`<label><input type="checkbox" value="${s.id}"> ${s.city} — ${s.name}</label>`).join(''); }
async function compare(){
  const ids=[...document.querySelectorAll('#compareList input:checked')].slice(0,5).map(x=>x.value);
  if(!ids.length){$('compareResult').innerHTML='<p>Select up to 5 stations.</p>';return;}
  const rows=await getJSON('/api/compare?stations='+ids.join(','));
  $('compareResult').innerHTML='<table><tr><th>Station</th><th>City</th><th>AQI</th><th>MQ2</th><th>MQ3</th><th>MQ135</th></tr>'+rows.map(r=>`<tr><td>${r.station}</td><td>${r.city}</td><td>${r.aqi}</td><td>${fmt(r.mq2)}</td><td>${fmt(r.mq3)}</td><td>${fmt(r.mq135)}</td></tr>`).join('')+'</table>';
}

function haversine(a,b){const R=6371,rad=Math.PI/180;const dLat=(b.lat-a.lat)*rad,dLon=(b.lng-a.lng)*rad;const x=Math.sin(dLat/2)**2+Math.cos(a.lat*rad)*Math.cos(b.lat*rad)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.sqrt(x));}
async function geocode(q){const r=await fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=in&q='+encodeURIComponent(q));const d=await r.json();if(!d.length)throw new Error('Location not found: '+q);return {lat:Number(d[0].lat),lng:Number(d[0].lon),name:d[0].display_name};}
function clearRoutes(){routeLayers.forEach(x=>map.removeLayer(x));routeLayers=[];}
function routeExposure(coords){
  let total=0,count=0;
  for(let i=0;i<coords.length;i+=Math.max(1,Math.floor(coords.length/20))){
    const p={lat:coords[i][1],lng:coords[i][0]}; let nearest=Infinity,aqi=100;
    stationPoints.forEach(s=>{const d=haversine(p,{lat:Number(s.latitude),lng:Number(s.longitude)});if(d<nearest){nearest=d;aqi=Number(s.aqi||100);}});
    if(nearest<12){total+=aqi;count++;} else {total+=100;count++;}
  }
  return count?Math.round(total/count):100;
}
async function findCleanRoute(){
  const from=$('routeFrom').value.trim(),to=$('routeTo').value.trim();
  if(!from||!to){$('routeResult').innerHTML='<p>Please enter both locations.</p>';return;}
  const btn=$('routeBtn');btn.disabled=true;btn.textContent='Calculating...';clearRoutes();
  try{
    const [a,b]=await Promise.all([geocode(from),geocode(to)]);
    const url=`https://router.project-osrm.org/route/v1/driving/${a.lng},${a.lat};${b.lng},${b.lat}?overview=full&geometries=geojson&alternatives=true`;
    const data=await (await fetch(url)).json();
    if(!data.routes?.length)throw new Error('No road route found.');
    const ranked=data.routes.map((r,i)=>({r,i,exposure:routeExposure(r.geometry.coordinates)})).sort((x,y)=>x.exposure-y.exposure);
    const best=ranked[0];
    ranked.forEach((item,index)=>{const line=L.geoJSON(item.r.geometry,{style:{weight:index===0?7:4,opacity:index===0?.9:.45,dashArray:index===0?null:'7 8'}}).addTo(map);routeLayers.push(line);});
    map.fitBounds(L.geoJSON(best.r.geometry).getBounds(),{padding:[30,30]});
    $('routeResult').innerHTML=`<div class="route-best"><span>🌿 Cleaner-route candidate</span><b>${(best.r.distance/1000).toFixed(1)} km · ${(best.r.duration/60).toFixed(0)} min</b><small>Estimated exposure indicator: ${best.exposure} · based on nearby station AQI</small></div><div class="route-note">This is a project-defined route indicator, not a medical or official pollution exposure measurement.</div>`;
  }catch(e){$('routeResult').innerHTML='<p class="error">'+e.message+'</p>';}finally{btn.disabled=false;btn.textContent='Find Cleaner Route';}
}

async function askAI(question){
  question=question||$('aiQuestion').value.trim(); if(!question)return;
  $('chatMessages').innerHTML+=`<div class="user-msg">${escapeHtml(question)}</div>`; $('aiQuestion').value='';
  try{const d=await fetch('/api/assistant',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,station_id:selectedStation})}).then(r=>r.json());$('chatMessages').innerHTML+=`<div class="bot-msg">${escapeHtml(d.answer)}</div>`;$('chatMessages').scrollTop=$('chatMessages').scrollHeight;}catch(e){$('chatMessages').innerHTML+=`<div class="bot-msg">Sorry, I could not read the station data.</div>`;}
}
function escapeHtml(s){return String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}

$('stateSelect').addEventListener('change',e=>loadCities(e.target.value));
$('citySelect').addEventListener('change',e=>loadStations(e.target.value));
$('stationSelect').addEventListener('change',e=>selectStation(e.target.value));
$('rangeSelect').addEventListener('change',loadHistory); $('compareBtn').addEventListener('click',compare);
$('explainBtn').addEventListener('click',explainNow); $('routeBtn').addEventListener('click',findCleanRoute);
$('aiSend').addEventListener('click',()=>askAI()); $('aiQuestion').addEventListener('keydown',e=>{if(e.key==='Enter')askAI();});
document.querySelectorAll('.quick-questions button').forEach(b=>b.addEventListener('click',()=>askAI(b.dataset.q)));
$('toggleHeatBtn').addEventListener('click',()=>{const on=$('toggleHeatBtn').dataset.on==='1';if(on){map.removeLayer(heatLayer);$('toggleHeatBtn').dataset.on='0';$('toggleHeatBtn').textContent='🔥 Show Heatmap';}else{heatLayer.addTo(map);$('toggleHeatBtn').dataset.on='1';$('toggleHeatBtn').textContent='🗺️ Hide Heatmap';}});
$('myLocationBtn').addEventListener('click',()=>navigator.geolocation?.getCurrentPosition(pos=>{let nearest=null,dist=1e9;Object.entries(mapMarkers).forEach(([id,m])=>{const p=m.getLatLng(),d=haversine({lat:pos.coords.latitude,lng:pos.coords.longitude},{lat:p.lat,lng:p.lng});if(d<dist){dist=d;nearest=id;}});if(nearest)selectStation(nearest)},()=>alert('Location permission was not granted.')));
function clock(){ $('clock').textContent=new Date().toLocaleString('en-IN'); } setInterval(clock,1000); clock();

(async function(){try{initMap();await loadSelectors();await loadMap();await loadSummary();await loadAlerts();await buildCompare();}catch(e){console.error(e);}})();
