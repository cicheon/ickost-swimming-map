'use strict';
const spots = JSON.parse(document.getElementById('spot-data').textContent).map((s, id) => ({...s, id, km: parseFloat(s.calculated_distance) || 0}));
const $ = id => document.getElementById(id);
const state = {region: '전체', selected: null, visible: []};
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const levelClass = level => level === '고급' ? 'hard' : level === '중급' ? 'medium' : '';
let map, layers, selectedLayer;
const markers = new Map();
const image = (src, alt, cls = '') => `<img class="${cls}" src="${escapeHTML(src)}" alt="${escapeHTML(alt)}" loading="lazy">`;

function initMap() {
  if (!window.L) {
    const error = document.createElement('p');
    error.className = 'map-error';
    error.textContent = '지도를 불러오지 못했어요. 인터넷 연결을 확인하고 새로고침해 주세요. 장소 목록은 계속 이용할 수 있습니다.';
    document.querySelector('.map-area').append(error);
    return;
  }
  map = L.map('map', {zoomControl: false, scrollWheelZoom: true}).setView([34.2, 127.6], 7);
  L.control.zoom({position: 'topright'}).addTo(map);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);
  layers = L.layerGroup().addTo(map);
  selectedLayer = L.layerGroup().addTo(map);
}
function pinIcon(active = false) {
  return L.divIcon({className: `map-pin${active ? ' active' : ''}`, html:'<div class="pin-body"><span>≈</span></div>', iconSize: active ? [38, 38] : [32, 32], iconAnchor: [16, 32]});
}
function routePoints(spot) { return (spot.route?.points || []).map(p => p.coords); }
function fitResults() {
  if (!map || !state.visible.length) return;
  const points = state.visible.flatMap(s => [s.coordinates, ...routePoints(s)]);
  map.fitBounds(L.latLngBounds(points), {paddingTopLeft: [45, 85], paddingBottomRight: [45, 100], maxZoom: 13, animate: false});
}
function renderMap() {
  if (!map) return;
  layers.clearLayers(); selectedLayer.clearLayers(); markers.clear();
  state.visible.forEach(spot => {
    const points = routePoints(spot);
    if (points.length > 1) L.polyline(points, {color: spot.route?.type === '편도' ? '#d28a44' : '#167d86', weight:3, opacity:.6}).addTo(layers);
    const marker = L.marker(spot.coordinates, {icon:pinIcon(), title:spot.title, alt:spot.title, keyboard:true}).addTo(layers);
    marker.bindTooltip(escapeHTML(spot.title), {direction:'top', offset:[0,-28]});
    marker.on('click', () => selectSpot(spot.id, true));
    markers.set(spot.id, marker);
  });
  fitResults();
}
function card(spot) {
  const selected = state.selected === spot.id;
  return `<button class="spot-card${selected ? ' selected' : ''}" data-id="${spot.id}" aria-pressed="${selected}" aria-label="${escapeHTML(spot.title)}, ${spot.calculated_distance}, ${spot.difficulty}">
    <span class="thumbnail">${image(spot.thumbnail, '')}<span class="duration">${escapeHTML(spot.duration)}</span></span>
    <span class="card-info"><span class="card-topline">${escapeHTML(spot.region)}<span>·</span><span class="difficulty ${levelClass(spot.difficulty)}">${escapeHTML(spot.difficulty)}</span></span>
    <h2>${escapeHTML(spot.title)}</h2><span class="card-description" style="display:block">${escapeHTML(spot.description)}</span>
    <span class="card-bottom"><strong>${escapeHTML(spot.calculated_distance)}</strong><span>${escapeHTML(spot.route?.type || '')}</span><span>영상 ${spot.video_count}</span><span class="rating">★ ${spot.rating.toFixed(1)}</span></span></span></button>`;
}
function update() {
  const query = $('search').value.trim().toLowerCase();
  const distance = $('distance').value;
  state.visible = spots.filter(s =>
    (state.region === '전체' || s.region === state.region) &&
    (!query || `${s.region} ${s.title} ${s.description}`.toLowerCase().includes(query)) &&
    (!$('difficulty').value || s.difficulty === $('difficulty').value) &&
    (!$('route-type').value || s.route?.type === $('route-type').value) &&
    (!distance || (distance === '2' ? s.km <= 2 : distance === '4' ? s.km > 2 && s.km <= 4 : s.km > 4))
  );
  const sort = $('sort').value;
  state.visible.sort((a,b) => sort === 'distance' ? a.km-b.km : sort === 'videos' ? b.video_count-a.video_count : b.rating-a.rating);
  closeDetail(false);
  $('spot-list').innerHTML = state.visible.map(card).join('');
  $('result-count').textContent = state.visible.length;
  $('empty').hidden = state.visible.length > 0;
  $('map-caption').textContent = state.visible.length ? `${state.region === '전체' ? '우리의 바다' : state.region}, ${state.visible.length}개의 출발점` : '검색 조건에 맞는 장소가 없습니다';
  $('announcement').textContent = `${state.visible.length}개의 수영 장소가 검색되었습니다.`;
  renderMap();
}
function setMapView(enabled) {
  document.body.classList.toggle('map-view', enabled);
  $('view-toggle').textContent = enabled ? '목록 보기 ☷' : '지도 보기 ↗';
  $('view-toggle').setAttribute('aria-pressed', String(enabled));
  if (map) requestAnimationFrame(() => {map.invalidateSize(); if (state.selected === null) fitResults();});
}
function selectSpot(id, fromMap = false) {
  const spot = spots.find(s => s.id === id);
  if (!spot) return;
  state.selected = id;
  $('spot-list').querySelectorAll('.spot-card').forEach(button => {
    const active = Number(button.dataset.id) === id;
    button.classList.toggle('selected', active); button.setAttribute('aria-pressed', String(active));
  });
  if (fromMap && !matchMedia('(max-width:760px)').matches) $('spot-list').querySelector(`[data-id="${id}"]`)?.scrollIntoView({block:'nearest'});
  $('detail-content').innerHTML = `${image(spot.thumbnail, spot.title, 'detail-cover')}<div class="detail-body"><span class="detail-region">${escapeHTML(spot.region)} · ${escapeHTML(spot.route?.type || '')}</span><h2>${escapeHTML(spot.title)}</h2><p class="detail-description">${escapeHTML(spot.description)}</p>
    <div class="detail-stats"><div><b>${escapeHTML(spot.calculated_distance)}</b><span>수영 거리</span></div><div><b>${escapeHTML(spot.estimated_time)}</b><span>예상 시간</span></div><div><b>${escapeHTML(spot.difficulty)}</b><span>난이도</span></div></div>
    <a class="detail-link" href="${escapeHTML(spot.detail_url)}">전체 경로·영상 보기 ↗</a><h3>이 바다의 수영 영상 <span>(${spot.video_count})</span></h3>
    ${spot.videos.map(video => `<a class="video-item" href="${escapeHTML(video.url)}" target="_blank" rel="noopener noreferrer">${image(video.thumbnail, '')}<span><strong>${escapeHTML(video.title)}</strong><small>${escapeHTML(video.duration)} · 조회수 ${escapeHTML(video.viewCount)}회</small></span></a>`).join('')}</div>`;
  $('detail').hidden = false; $('detail').scrollTop = 0;
  if (matchMedia('(max-width:760px)').matches) setMapView(true);
  if (map) {
    map.invalidateSize();
    markers.forEach((marker, key) => {marker.setIcon(pinIcon(key === id)); marker.setZIndexOffset(key === id ? 1000 : 0);});
    selectedLayer.clearLayers();
    const points = routePoints(spot);
    if (points.length > 1) {
      L.polyline(points, {color:'#fff', weight:9, opacity:.95}).addTo(selectedLayer);
      L.polyline(points, {color:spot.route?.type === '편도' ? '#d28a44' : '#167d86', weight:5, opacity:1}).addTo(selectedLayer);
      [points[0], points[points.length-1]].forEach(p => L.circleMarker(p, {radius:5,color:'#fff',weight:2,fillColor:'#167d86',fillOpacity:1}).addTo(selectedLayer));
    }
    const mobile = matchMedia('(max-width:760px)').matches;
    // Reserve space for the side panel / bottom sheet so the selected route stays visible.
    map.fitBounds(L.latLngBounds(points.length > 1 ? points : [spot.coordinates]), {
      paddingTopLeft:[35,85], paddingBottomRight:mobile ? [35,Math.min(map.getSize().y*.6,420)] : [Math.min(390,map.getSize().x*.57),70], maxZoom:15, animate:false
    });
  }
  $('announcement').textContent = `${spot.title} 경로와 상세 정보를 표시합니다.`;
}
function closeDetail(restoreFocus = true) {
  const previous = state.selected; state.selected = null;
  $('detail').hidden = true;
  if (selectedLayer) selectedLayer.clearLayers();
  markers.forEach(marker => {marker.setIcon(pinIcon()); marker.setZIndexOffset(0);});
  $('spot-list').querySelectorAll('.spot-card').forEach(button => {button.classList.remove('selected');button.setAttribute('aria-pressed','false');});
  if (restoreFocus && previous !== null && !document.body.classList.contains('map-view')) $('spot-list').querySelector(`[data-id="${previous}"]`)?.focus();
}
$('spot-list').addEventListener('click', e => {const button=e.target.closest('[data-id]');if(button) selectSpot(Number(button.dataset.id));});
document.querySelectorAll('[data-region]').forEach(button => button.addEventListener('click', () => {
  state.region = button.dataset.region;
  document.querySelectorAll('[data-region]').forEach(b => {b.classList.toggle('active', b === button);b.setAttribute('aria-pressed', String(b === button));}); update();
}));
$('search').addEventListener('input', update);
['difficulty','distance','route-type','sort'].forEach(id => $(id).addEventListener('change', update));
$('reset').addEventListener('click', () => {['search','difficulty','distance','route-type'].forEach(id => $(id).value='');state.region='전체';document.querySelector('[data-region="전체"]').click();});
$('close-detail').addEventListener('click', () => closeDetail());
$('fit-map').addEventListener('click', () => {closeDetail();fitResults();});
$('view-toggle').addEventListener('click', () => setMapView(!document.body.classList.contains('map-view')));
document.addEventListener('keydown', e => {if(e.key === 'Escape') closeDetail();if(e.key === '/' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();setMapView(false);$('search').focus();}});
// Replace unavailable high-resolution YouTube thumbnails with the standard size.
document.addEventListener('error', e => {const img=e.target;if(img.tagName === 'IMG' && img.src.includes('/maxresdefault.jpg')) img.src=img.src.replace('/maxresdefault.jpg','/hqdefault.jpg');},true);
initMap(); update();
