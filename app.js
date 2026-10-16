const STORE_KEY = 'weather-dashboard:v2';
const CONFIG_URL = './config.json';
const API = 'https://api.open-meteo.com/v1/forecast';
const GEOCODE_API = 'https://geocoding-api.open-meteo.com/v1/search';
const AIR_QUALITY_API = 'https://air-quality-api.open-meteo.com/v1/air-quality';
const FALLBACK_CONFIG = {defaultLocation:null,locations:[]};
const hourlyWindow = window.DayglanceHourlyWindow;
const DEFAULT_PREFERENCES = {returnAfterSeconds:60,radarIdleTimeoutSeconds:60,temperatureUnit:'fahrenheit',measurementSystem:'imperial',clockFormat:'system',refreshMinutes:15,showBumpers:true,temperatureGraphRange:'day',autoScrollLocations:false,autoScrollIntervalSeconds:30};
const $ = selector => document.querySelector(selector);
const setup = $('#setup');
const dashboard = $('#dashboard');
const addPage = $('#add-page');
const details = $('#details');
const settingsScreen = $('#settings-screen');
const radarScreen = $('#radar-screen');
const loading = $('#loading');
const setupError = $('#setup-error');
let saved = {userLocations:[],overrides:{},forecasts:{},histories:{},resolved:{},preferences:{},stationAssociations:{}};
let preferences = {...DEFAULT_PREFERENCES};
let stationIntegrations = [];
let stationSamples = {};
let stationReceiverStatus = 'disabled';
let deviceSettings = {autoStart:false,kiosk:true,autostartInstalled:false,startupSupported:false};
let configuredLocations = [];
let locations = [];
let currentIndex = 0;
let currentForecast = null;
let showingAddPage = false;
let settingsReturn = false;
let editorMode = 'add';
let editingId = null;
let selectedResult = null;
let searchTimer;
let searchSequence = 0;
let detailTimer;
let autoScrollTimer;
let countdownTimer;
let detailScrollTimer;
const detailPointers=new Set();
let refreshTimer;
let touchStart = null;
let lastResumeRefresh = 0;

function readSaved(){try{return JSON.parse(localStorage.getItem(STORE_KEY)||'{}')}catch{return {}}}
function save(){const {forecasts,histories,...persistent}=saved;const serialized=JSON.stringify(persistent);if(localStorage.getItem(STORE_KEY)!==serialized)localStorage.setItem(STORE_KEY,serialized)}
function text(id,value){const el=document.getElementById(id);if(el)el.textContent=value}
function weatherType(code,isDay=true){
  let label='Weather',type=isDay?'sun':'moon';
  if(code===0){label='Clear sky';type=isDay?'sun':'moon'}
  else if(code===1){label='Mostly clear';type=isDay?'sun':'moon'}
  else if([2,3].includes(code)){label=code===2?'Partly cloudy':'Overcast';type='cloud'}
  else if([45,48].includes(code)){label='Foggy';type='fog'}
  else if([51,53,55,56,57,61,63,65,66,67,80,81,82].includes(code)){label=[51,53,55].includes(code)?'Drizzle':[56,57,66,67].includes(code)?'Freezing rain':'Rain';type='rain'}
  else if([71,73,75,77,85,86].includes(code)){label='Snow';type='snow'}
  else if([95,96,99].includes(code)){label='Thunderstorms';type='thunder'}
  return {label,icon:weatherIcon(type)};
}
function weatherIcon(type){
  const common=`class="weather-svg weather-${type}" viewBox="0 0 64 48" focusable="false"`;
  const sun='<circle cx="32" cy="20" r="10"/><path d="M32 2v6M32 32v6M14 20H8m48 0h-6M19.3 7.3l4.2 4.2m17 17 4.2 4.2m0-25.4-4.2 4.2m-17 17-4.2 4.2"/>';
  const cloud='<path d="M17 37h31a10 10 0 0 0 0-20 16 16 0 0 0-30-3 12 12 0 0 0-1 23Z"/>';
  const art={
    sun:`<svg ${common} aria-hidden="true">${sun}</svg>`, moon:`<svg ${common} aria-hidden="true"><path d="M42 34A18 18 0 0 1 26 6a18 18 0 1 0 16 28Z"/></svg>`,
    cloud:`<svg ${common} aria-hidden="true">${cloud}</svg>`, partly:`<svg ${common} aria-hidden="true"><circle cx="23" cy="17" r="9"/><path d="M23 2v5m0 20v5M8 17h5m20 0h5m-26-10 4 4m14 14 4 4m0-22-4 4"/>${cloud}</svg>`,
    fog:`<svg ${common} aria-hidden="true"><path d="M17 29h31a9 9 0 0 0 0-18 15 15 0 0 0-28-2"/><path d="M8 35h43M14 42h34"/></svg>`,
    rain:`<svg ${common} aria-hidden="true">${cloud}<path d="m23 39-3 6m15-6-3 6m15-6-3 6"/></svg>`,
    snow:`<svg ${common} aria-hidden="true">${cloud}<path d="M23 39v7m-3-3 6-1m10-3v7m-3-3 6-1m7-3v7m-3-3 6-1"/></svg>`,
    thunder:`<svg ${common} aria-hidden="true">${cloud}<path d="m34 36-8 8h7l-3 6 12-11h-7l4-3"/></svg>`
  };
  return art[type]||art.sun;
}
function formatDay(iso,options={weekday:'short'}){return new Intl.DateTimeFormat(undefined,options).format(new Date(`${iso}T12:00:00`))}
function localHour(iso){const hour=preferences.clockFormat==='system'?'numeric':preferences.clockFormat==='24'?'2-digit':'numeric';return new Intl.DateTimeFormat(undefined,{hour,hourCycle:preferences.clockFormat==='24'?'h23':preferences.clockFormat==='12'?'h12':undefined}).format(new Date(iso))}
function compass(degrees){return ['N','NE','E','SE','S','SW','W','NW'][Math.round((Number(degrees)||0)/45)%8]}
function safeNumber(value,decimals=0){return Number.isFinite(Number(value))?Number(value).toFixed(decimals):'—'}
function temperatureSuffix(){return preferences.temperatureUnit==='celsius'?'°C':'°F'}
function forecastInCurrentUnits(cached){
  if(!cached?.data)return null;
  const data=JSON.parse(JSON.stringify(cached.data));
  const fromTemperature=cached.temperatureUnit||'fahrenheit',fromSystem=cached.measurementSystem||'imperial';
  const convertTemperature=value=>fromTemperature===preferences.temperatureUnit?value:preferences.temperatureUnit==='celsius'?(value-32)*5/9:value*9/5+32;
  const convertWind=value=>fromSystem===preferences.measurementSystem?value:preferences.measurementSystem==='metric'?value*1.609344:value/1.609344;
  for(const key of ['temperature_2m','apparent_temperature'])if(Number.isFinite(Number(data.current?.[key])))data.current[key]=convertTemperature(data.current[key]);
  for(const key of ['temperature_2m','apparent_temperature'])if(Array.isArray(data.hourly?.[key]))data.hourly[key]=data.hourly[key].map(convertTemperature);
  for(const key of ['temperature_2m_max','temperature_2m_min'])if(Array.isArray(data.daily?.[key]))data.daily[key]=data.daily[key].map(convertTemperature);
  if(Number.isFinite(Number(data.current?.wind_speed_10m)))data.current.wind_speed_10m=convertWind(data.current.wind_speed_10m);
  if(Array.isArray(data.daily?.wind_speed_10m_max))data.daily.wind_speed_10m_max=data.daily.wind_speed_10m_max.map(convertWind);
  return data;
}
function setLoading(on,message='Loading forecast…'){
  loading.hidden=!on;text('loading-message',message);
  if(on)loading.setAttribute('aria-live','polite');
}
function setStatus(value){text('updated',value)}
function applyPreferences(){
  $('#setting-return-time').value=String(preferences.returnAfterSeconds);
  $('#setting-radar-timeout').value=String(preferences.radarIdleTimeoutSeconds);
  $('#setting-temperature').value=preferences.temperatureUnit;
  $('#setting-measurement').value=preferences.measurementSystem;
  $('#setting-clock').value=preferences.clockFormat;
  $('#setting-refresh').value=String(preferences.refreshMinutes);
  $('#setting-graph-range').value=preferences.temperatureGraphRange;
  $('#setting-auto-scroll').checked=preferences.autoScrollLocations;
  $('#setting-auto-scroll-interval').value=String(preferences.autoScrollIntervalSeconds);
  $('#setting-auto-scroll-interval').disabled=!preferences.autoScrollLocations;
  $('#setting-bumpers').checked=preferences.showBumpers;
  $('#hours-previous').hidden=$('#hours-next').hidden=!preferences.showBumpers;
  const summary=$('#current-temperature-unit');if(summary)summary.textContent=temperatureSuffix();
}
function savePreferences(){saved.preferences={...preferences};save();applyPreferences()}
function scheduleRefresh(){
  clearInterval(refreshTimer);
  refreshTimer=setInterval(()=>{if(locations.length&&!showingAddPage&&setup.hidden&&details.hidden&&settingsScreen.hidden)loadForecast({showSpinner:false})},Number(preferences.refreshMinutes)*60*1000);
}
async function loadDeviceSettings(){
  try{
    const response=await fetch('./api/device-settings',{cache:'no-store'});
    if(!response.ok)throw new Error('Device startup settings are not available from this server.');
    const data=await response.json();
    const localPage=['localhost','127.0.0.1','::1'].includes(location.hostname);
    deviceSettings={autoStart:Boolean(data.autoStart),kiosk:data.kiosk!==false,autostartInstalled:Boolean(data.autostartInstalled),startupSupported:Boolean(data.startupSupported)&&localPage};
    $('#setting-auto-start').disabled=$('#setting-kiosk').disabled=!deviceSettings.startupSupported;
    renderStartupControl();
    $('#setting-kiosk').checked=deviceSettings.kiosk;
    text('startup-status',deviceSettings.startupSupported?'Enabling auto-start installs the desktop login hook automatically. Changes apply at the next desktop login.':'Startup controls are available from Dayglance running locally on a Linux desktop or Raspberry Pi.');
  }catch(error){
    $('#setting-auto-start').disabled=true;$('#setting-kiosk').disabled=true;
    renderStartupControl();
    text('startup-status','Could not load device startup settings. Use Dayglance on the Pi itself.');
  }
}
function renderStartupControl(){
  const button=$('#setting-auto-start');
  const enabled=deviceSettings.autoStart;
  button.textContent=enabled?'Disable':'Enable';
  button.setAttribute('aria-pressed',String(enabled));
  text('startup-state',enabled?'Currently enabled':'Currently disabled');
}
async function saveDeviceSettings(autoStartValue=deviceSettings.autoStart){
  const status=$('#settings-status');
  const startupButton=$('#setting-auto-start');
  startupButton.disabled=true;
  try{
    const response=await fetch('./api/device-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({autoStart:autoStartValue,kiosk:$('#setting-kiosk').checked})});
    if(!response.ok)throw new Error('Could not save Pi startup settings. Use Dayglance on the Pi itself.');
    deviceSettings={...deviceSettings,...await response.json()};
    renderStartupControl();
    status.textContent='Saved. Startup options apply the next time the Dayglance launcher runs.';
  }catch(error){
    renderStartupControl();$('#setting-kiosk').checked=deviceSettings.kiosk;
    status.textContent=error.message;
  }finally{
    startupButton.disabled=!deviceSettings.startupSupported;
  }
}
function refreshAfterResume(){
  const now=Date.now();if(now-lastResumeRefresh<5000)return;lastResumeRefresh=now;
  const area=locations[currentIndex],cached=area&&saved.forecasts[area.id];
  if(area&&settingsScreen.hidden&&(!cached||now-cached.fetchedAt>10*60*1000))loadForecast({showSpinner:false});
  if(!radarScreen.hidden)window.DayglanceRadar.refresh();
}
function configSignature(config){return JSON.stringify([config.defaultLocation,...(config.locations||[])])}
function normalizeConfigLocation(area,index){
  const fallback=index===0?FALLBACK_CONFIG.defaultLocation:null;
  const source=area||fallback;
  if(!source)return null;
  return {id:source.id||`config-area-${index}`,name:source.name||source.query||'Weather location',query:source.query||'',countryCode:source.countryCode||'',latitude:Number.isFinite(Number(source.latitude))?Number(source.latitude):null,longitude:Number.isFinite(Number(source.longitude))?Number(source.longitude):null,source:'config'};
}
async function initialize(){
  let config=FALLBACK_CONFIG;
  try{const response=await fetch(CONFIG_URL,{cache:'no-store'});if(response.ok){const candidate=await response.json();if(candidate&&Object.hasOwn(candidate,'defaultLocation'))config=candidate}}catch{}
  stationIntegrations=Array.isArray(config.stationIntegrations)?config.stationIntegrations.filter(source=>source&&source.enabled===true&&((source.provider==='ambient-weather'&&['local-upload','cloud-api'].includes(source.connection))||(source.provider==='weather-underground'&&source.connection==='cloud-api'))&&typeof source.id==='string'):[];
  const configPreferences=config.preferences&&typeof config.preferences==='object'&&!Array.isArray(config.preferences)?Object.fromEntries(Object.entries(config.preferences).filter(([key])=>Object.hasOwn(DEFAULT_PREFERENCES,key))):{};
  configuredLocations=[normalizeConfigLocation(config.defaultLocation,0),...(config.locations||[]).map((area,index)=>normalizeConfigLocation(area,index+1))].filter(Boolean);
  const stored=readSaved(),signature=configSignature(config);
  const storedAssociations=stored.stationAssociations&&typeof stored.stationAssociations==='object'&&!Array.isArray(stored.stationAssociations)?stored.stationAssociations:{};
  const stationAssociations=Object.fromEntries(stationIntegrations.map(source=>[source.id,Object.hasOwn(storedAssociations,source.id)?storedAssociations[source.id]:(typeof source.locationId==='string'?source.locationId:'')]));
  saved={defaultLocation:stored.defaultLocation||null,userLocations:Array.isArray(stored.userLocations)?stored.userLocations:[],hiddenLocationIds:Array.isArray(stored.hiddenLocationIds)?stored.hiddenLocationIds:[],overrides:stored.overrides&&typeof stored.overrides==='object'?stored.overrides:{},forecasts:stored.forecasts&&typeof stored.forecasts==='object'?stored.forecasts:{},histories:stored.histories&&typeof stored.histories==='object'?stored.histories:{},resolved:stored.resolved&&typeof stored.resolved==='object'?stored.resolved:{},preferences:stored.preferences&&typeof stored.preferences==='object'?stored.preferences:{},stationAssociations,configSignature:signature};
  preferences={...DEFAULT_PREFERENCES,...configPreferences,...saved.preferences};
  delete preferences.scrollbarSize;
  delete saved.preferences.scrollbarSize;
  if(![0,15,30,60,90,120,300].includes(Number(preferences.returnAfterSeconds)))preferences.returnAfterSeconds=DEFAULT_PREFERENCES.returnAfterSeconds;else preferences.returnAfterSeconds=Number(preferences.returnAfterSeconds);
  if(![15,30,60,300].includes(Number(preferences.radarIdleTimeoutSeconds)))preferences.radarIdleTimeoutSeconds=DEFAULT_PREFERENCES.radarIdleTimeoutSeconds;else preferences.radarIdleTimeoutSeconds=Number(preferences.radarIdleTimeoutSeconds);
  if(!['fahrenheit','celsius'].includes(preferences.temperatureUnit))preferences.temperatureUnit=DEFAULT_PREFERENCES.temperatureUnit;
  if(!['imperial','metric'].includes(preferences.measurementSystem))preferences.measurementSystem=DEFAULT_PREFERENCES.measurementSystem;
  if(!['system','12','24'].includes(preferences.clockFormat))preferences.clockFormat=DEFAULT_PREFERENCES.clockFormat;
  if(![15,30,60].includes(Number(preferences.refreshMinutes)))preferences.refreshMinutes=DEFAULT_PREFERENCES.refreshMinutes;else preferences.refreshMinutes=Number(preferences.refreshMinutes);
  if(!['day','week','forecast16','history30'].includes(preferences.temperatureGraphRange))preferences.temperatureGraphRange=DEFAULT_PREFERENCES.temperatureGraphRange;
  preferences.autoScrollLocations=preferences.autoScrollLocations===true;
  if(![30,60,300,900].includes(Number(preferences.autoScrollIntervalSeconds)))preferences.autoScrollIntervalSeconds=DEFAULT_PREFERENCES.autoScrollIntervalSeconds;else preferences.autoScrollIntervalSeconds=Number(preferences.autoScrollIntervalSeconds);
  preferences.showBumpers=preferences.showBumpers!==false;
  // Preserve a location the owner explicitly edited in the earlier preset-based version.
  try{const previous=JSON.parse(stored.configSignature||'[]')[0];if(!config.defaultLocation&&!saved.defaultLocation&&previous?.id&&saved.overrides[previous.id])saved.defaultLocation={...saved.overrides[previous.id],source:'user'}}catch{}
  if(stored.configSignature&&stored.configSignature!==signature){
    for(const area of configuredLocations){delete saved.overrides[area.id];delete saved.resolved[area.id];delete saved.forecasts[area.id];delete saved.histories[area.id]}
  }
  save();rebuildLocations();currentIndex=0;showingAddPage=false;
  applyPreferences();await loadDeviceSettings();scheduleRefresh();
  if(stationIntegrations.length){await refreshStationData();setInterval(refreshStationData,30000)}
  if(!locations.length){setStatus('Choose your location');openEditor('initial');return}
  dashboard.hidden=false;setup.hidden=true;addPage.hidden=true;
  const cached=saved.forecasts[locations[0].id],cachedData=forecastInCurrentUnits(cached);
  if(cachedData){currentForecast=cachedData;render(cachedData,locations[0]);setStatus('Showing saved forecast · updating…')}
  updateAreaPosition();await loadForecast({showSpinner:!cachedData});scheduleAutoScroll();
}
function rebuildLocations(){
  const hidden=new Set(saved.hiddenLocationIds||[]);
  const primary=configuredLocations.map(area=>saved.overrides[area.id]||area).filter(area=>!hidden.has(area.id));
  locations=[...primary,...(saved.defaultLocation?[saved.defaultLocation]:[]),...saved.userLocations.filter(area=>!hidden.has(area.id))];
  $('#refresh').hidden=locations.length===0;
  $('#radar-open').hidden=locations.length===0;
  currentIndex=Math.max(0,Math.min(currentIndex,locations.length-1));
  updateAreaPosition();
}
function updateAreaPosition(){text('area-position',locations.length?`${Math.min(currentIndex+1,locations.length)} / ${locations.length}`:'')}
function makeForecastUrl(location){
  const metric=preferences.measurementSystem==='metric';
  const params=new URLSearchParams({latitude:location.latitude,longitude:location.longitude,current:'temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,wind_speed_10m,wind_direction_10m,pressure_msl,visibility,uv_index',hourly:'temperature_2m,apparent_temperature,precipitation_probability,weather_code',daily:'weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max,precipitation_probability_max,wind_speed_10m_max',temperature_unit:preferences.temperatureUnit,wind_speed_unit:metric?'kmh':'mph',precipitation_unit:metric?'mm':'inch',timezone:'auto',forecast_days:preferences.temperatureGraphRange==='forecast16'?'16':'7'});
  return `${API}?${params}`;
}
function makeAirQualityUrl(location){
  const params=new URLSearchParams({latitude:location.latitude,longitude:location.longitude,current:'us_aqi,pm2_5',timezone:'auto'});
  return `${AIR_QUALITY_API}?${params}`;
}
async function fetchAirQuality(location){
  try{
    const response=await fetch(makeAirQualityUrl(location),{cache:'no-store'});
    if(!response.ok)return null;
    const data=await response.json();
    return data.current||null;
  }catch{return null}
}
async function resolveLocation(area){
  if(Number.isFinite(area.latitude)&&Number.isFinite(area.longitude))return area;
  const cached=saved.resolved[area.id];if(cached)return {...area,...cached};
  const params=new URLSearchParams({name:area.query,count:'10',language:'en',format:'json'});
  if(area.countryCode)params.set('countryCode',area.countryCode);
  const response=await fetch(`${GEOCODE_API}?${params}`);
  if(!response.ok)throw new Error('Could not validate the configured location. Check your internet connection or edit config.json.');
  const data=await response.json(),results=data.results||[];
  if(!results.length)throw new Error(`No match found for ${area.query}. Edit config.json or add a location on screen.`);
  const exact=results.find(item=>item.postcodes?.includes(area.query));
  const match=exact||results[0];
  const resolved={latitude:Number(match.latitude),longitude:Number(match.longitude)};
  saved.resolved[area.id]=resolved;save();
  return {...area,...resolved,name:area.name||locationLabel(match)};
}
async function fetchForecast(area){
  const location=await resolveLocation(area);
  const [response,airQuality]=await Promise.all([fetch(makeForecastUrl(location),{cache:'no-store'}),fetchAirQuality(location)]);
  if(!response.ok)throw new Error('The forecast service is temporarily unavailable. Please try again.');
  const data=await response.json();
  if(!data.current||!data.daily||!data.hourly)throw new Error('The forecast service returned incomplete weather data.');
  data.airQuality=airQuality;
  saved.forecasts[area.id]={data,fetchedAt:Date.now(),temperatureUnit:preferences.temperatureUnit,measurementSystem:preferences.measurementSystem};save();
  currentForecast=data;render(data,location);setStatus(`Updated ${new Intl.DateTimeFormat(undefined,{hour:'numeric',minute:'2-digit'}).format(new Date())}`);
}
async function loadForecast({showSpinner=true}={}){
  const area=locations[currentIndex];if(!area)return;
  const cached=saved.forecasts[area.id];
  const cachedData=forecastInCurrentUnits(cached);
  if(cachedData){currentForecast=cachedData;render(cachedData,area)}
  if(showSpinner)setLoading(true,'Getting your local forecast…');
  try{await fetchForecast(area);dashboard.hidden=false;}
  catch(error){
    const fallback=forecastInCurrentUnits(cached);
    if(fallback){currentForecast=fallback;render(fallback,area);setStatus('Showing saved forecast · refresh to retry')}
    else{setStatus(error.message);setPlaceHeading(area);dashboard.hidden=false}
  }finally{setLoading(false)}
}
function stationForLocation(locationId){
  const now=Date.now();
  for(const source of stationIntegrations){
    if(saved.stationAssociations?.[source.id]!==locationId)continue;
    const sample=stationSamples[source.id];
    if(!sample?.available||!sample.observation)continue;
    const age=Number(sample.ageSeconds||0)+Math.max(0,Math.floor((now-sample.clientReceivedAt)/1000));
    const staleAfter=Number(sample.staleAfterSeconds||600);
    if(sample.fresh&&age<=staleAfter)return {source,sample,observation:sample.observation,age};
  }
  return null;
}
async function refreshStationData(){
  if(!stationIntegrations.length)return;
  try{
    const response=await fetch('./api/local-stations',{cache:'no-store'});
    if(!response.ok)throw new Error('Station status unavailable');
    const payload=await response.json(),receivedAt=Date.now();
    stationReceiverStatus=typeof payload.receiverStatus==='string'?payload.receiverStatus:'unknown';
    stationSamples=Object.fromEntries((Array.isArray(payload.integrations)?payload.integrations:[]).map(sample=>[sample.id,{...sample,clientReceivedAt:receivedAt}]));
    if(currentForecast&&locations[currentIndex])render(currentForecast,locations[currentIndex]);
    if(!settingsScreen.hidden)renderStationSettings();
  }catch{
    // A station receiver outage must not interrupt forecast display; the last sample ages out in memory.
    stationReceiverStatus='unreachable';
    if(currentForecast&&locations[currentIndex])render(currentForecast,locations[currentIndex]);
  }
}
function render(data,location){
  const current=data.current,daily=data.daily,hourly=data.hourly;
  const currentKind=weatherType(current.weather_code,Boolean(current.is_day));
  setPlaceHeading(location);text('today-date',new Intl.DateTimeFormat(undefined,{weekday:'long',month:'long',day:'numeric'}).format(new Date(`${daily.time[0]}T12:00:00`)));
  $('#current-icon').innerHTML=currentKind.icon;text('current-temperature',safeNumber(current.temperature_2m));$('#current-temperature-unit').textContent=temperatureSuffix();text('current-summary',currentKind.label);text('feels-like',`${safeNumber(current.apparent_temperature)}${temperatureSuffix()}`);
  text('sunrise',daily.sunrise?.[0]?localHour(daily.sunrise[0]):'—');text('sunset',daily.sunset?.[0]?localHour(daily.sunset[0]):'—');
  const metric=preferences.measurementSystem==='metric';
  text('wind-label','Wind');text('humidity-label','Humidity');text('pressure-label','Pressure');text('uv-label','UV index');
  text('wind',`${safeNumber(current.wind_speed_10m)} ${metric?'km/h':'mph'} ${compass(current.wind_direction_10m)}`);text('humidity',`${safeNumber(current.relative_humidity_2m)}%`);
  text('pressure',Number.isFinite(Number(current.pressure_msl))?metric?`${safeNumber(current.pressure_msl)} hPa`:`${(current.pressure_msl*0.029529983).toFixed(2)} inHg`:'—');text('uv',safeNumber(current.uv_index,1));
  text('visibility',Number.isFinite(Number(current.visibility))?metric?`${(current.visibility/1000).toFixed(1)} km`:`${(current.visibility/1609.344).toFixed(1)} mi`:'—');
  const localStation=stationForLocation(location.id),stationStatus=$('#station-observation-status');
  stationStatus.hidden=!localStation;
  if(localStation){
    const observation=localStation.observation,age=localStation.age;
    stationStatus.textContent=`Observed by ${localStation.source.name} · ${age<60?'just now':`${Math.floor(age/60)} min ago`}`;
    const hasStationTemperature=Number.isFinite(Number(observation.tempf));
    if(hasStationTemperature)text('current-temperature',safeNumber(metric?(Number(observation.tempf)-32)*5/9:Number(observation.tempf)));
    text('current-summary',hasStationTemperature?'Local station observation':`Forecast · ${currentKind.label}`);
    if(Number.isFinite(Number(observation.windspeedmph))){const speed=Number(observation.windspeedmph)*(metric?1.609344:1);text('wind',`${safeNumber(speed)} ${metric?'km/h':'mph'} ${compass(observation.winddir)}`);text('wind-label','Wind · station')}
    if(Number.isFinite(Number(observation.humidity))){text('humidity',`${safeNumber(observation.humidity)}%`);text('humidity-label','Humidity · station')}
    if(Number.isFinite(Number(observation.baromin))){const pressure=Number(observation.baromin)*(metric?33.8638867:1);text('pressure',metric?`${safeNumber(pressure)} hPa`:`${pressure.toFixed(2)} inHg`);text('pressure-label','Pressure · station')}
    if(Number.isFinite(Number(observation.uv))){text('uv',safeNumber(observation.uv,1));text('uv-label','UV · station')}
  }
  const air=window.DayglanceAirQuality.formatAirQuality(data.airQuality);
  text('air-quality-value',air.value);text('air-quality-pm',air.pm25);
  $('#air-quality-value').title=air.category;$('#air-quality-value').setAttribute('aria-label',air.ariaLabel);
  renderTrend(data,location);renderDays(daily);
}
function setPlaceHeading(location){
  const [city,...details]=String(location.name||'').split(',').map(part=>part.trim());
  text('place-name',city||location.name||'—');
  text('place-region',details.join(', ')||[location.postalCode,location.countryCode].filter(Boolean).join(' · '));
}
function renderTrend(data,location){
  const holder=$('#trend-chart'),range=preferences.temperatureGraphRange;
  const titles={day:'Next 24 hours',week:'7-day forecast',forecast16:'16-day outlook',history30:'Past 30 days'};
  text('trend-title',titles[range]);text('trend-legend-key',range==='day'?'Hourly temperature':'Daily high / low');
  if(range==='history30'){renderHistoricalTrend(location);return}
  if(range==='day'){
  const hourly=data.hourly,start=Math.max(0,hourly.time.findIndex(time=>time>=data.current.time));
  const temperatures=hourly.temperature_2m.slice(start,start+24);
  if(temperatures.length<2){holder.replaceChildren();return}
  const width=1000,height=112,left=8,right=992,top=12,bottom=82;
  const low=Math.min(...temperatures)-2,high=Math.max(...temperatures)+2,spread=Math.max(1,high-low);
  const pts=temperatures.map((value,index)=>[left+index*(right-left)/(temperatures.length-1),bottom-(value-low)/spread*(bottom-top)]);
  const line=pts.map((point,index)=>`${index?'L':'M'}${point[0].toFixed(1)} ${point[1].toFixed(1)}`).join(' ');
  const area=`${line} L${right} ${bottom+9} L${left} ${bottom+9} Z`;
  const labels=[0,6,12,18].map(offset=>{const i=Math.min(start+offset,hourly.time.length-1);const x=left+Math.min(offset,temperatures.length-1)*(right-left)/(temperatures.length-1);return `<text class="trend-label" x="${x}" y="106" text-anchor="middle">${localHour(hourly.time[i])}</text>`}).join('');
  const dots=pts.filter((_,i)=>i%6===0).map(([x,y])=>`<circle cx="${x}" cy="${y}" r="3" fill="#f9fbfa" stroke="#4b98a9" stroke-width="2"/>`).join('');
  holder.innerHTML=`<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Hourly temperature trend for the next 24 hours"><defs><linearGradient id="trend-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#a9d5df" stop-opacity=".68"/><stop offset="1" stop-color="#dcecef" stop-opacity=".18"/></linearGradient></defs><path d="${area}" fill="url(#trend-fill)"/><path d="${line}" fill="none" stroke="#4b98a9" stroke-width="2.5" vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round"/>${dots}${labels}</svg>`;
  return;
  }
  renderDailyTrend(data.daily,range==='week'?7:16,range==='week'?'7-day forecast':'16-day outlook');
}
function renderDailyTrend(daily,count,label){
  const dates=daily.time.slice(0,count),highs=daily.temperature_2m_max.slice(0,count),lows=daily.temperature_2m_min.slice(0,count);
  renderRangeTrend(dates,highs,lows,label,false);
}
function renderRangeTrend(dates,highs,lows,label,isHistory){
  const holder=$('#trend-chart');
  if(dates.length<2||highs.length!==dates.length||lows.length!==dates.length){holder.textContent='Temperature history is not available yet.';return}
  const width=1000,height=112,left=18,right=982,top=12,bottom=79;
  const values=[...highs,...lows].map(Number).filter(Number.isFinite),low=Math.min(...values)-2,high=Math.max(...values)+2,spread=Math.max(1,high-low);
  const x=index=>left+index*(right-left)/(dates.length-1),y=value=>bottom-(Number(value)-low)/spread*(bottom-top);
  const upper=highs.map((value,index)=>[x(index),y(value)]),lower=lows.map((value,index)=>[x(index),y(value)]);
  const highLine=upper.map(([px,py],index)=>`${index?'L':'M'}${px.toFixed(1)} ${py.toFixed(1)}`).join(' ');
  const lowLine=lower.map(([px,py],index)=>`${index?'L':'M'}${px.toFixed(1)} ${py.toFixed(1)}`).join(' ');
  const band=`${highLine} ${lower.slice().reverse().map(([px,py])=>`L${px.toFixed(1)} ${py.toFixed(1)}`).join(' ')} Z`;
  const stride=dates.length<=7?2:dates.length<=16?3:5;
  const labels=dates.map((date,index)=>index%stride===0||index===dates.length-1?`<text class="trend-label" x="${x(index).toFixed(1)}" y="106" text-anchor="middle">${formatDay(date,isHistory?{month:'numeric',day:'numeric'}:{weekday:'short'})}</text>`:'').join('');
  const aria=isHistory?'Daily high and low temperatures for the past 30 days':`Daily high and low temperatures for ${label}`;
  holder.innerHTML=`<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="${aria}"><path d="${band}" fill="#a9d5df" fill-opacity=".38"/><path d="${highLine}" fill="none" stroke="#d48d45" stroke-width="2.5" vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round"/><path d="${lowLine}" fill="none" stroke="#4b98a9" stroke-width="2.5" vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round"/>${labels}</svg>`;
}
async function renderHistoricalTrend(location){
  const holder=$('#trend-chart'),generation=++historyRequestSequence;
  const cached=saved.histories[location.id];
  if(cached?.data?.daily){
    const data=convertHistory(cached);renderRangeTrend(data.time,data.high,data.low,'past 30 days',true);
    if(cached.temperatureUnit===preferences.temperatureUnit&&Date.now()-cached.fetchedAt<6*60*60*1000)return;
  }
  try{
    const params=new URLSearchParams({latitude:location.latitude,longitude:location.longitude,daily:'temperature_2m_max,temperature_2m_min',temperature_unit:preferences.temperatureUnit,timezone:'auto',past_days:'29',forecast_days:'1'});
    const response=await fetch(`${API}?${params}`,{cache:'no-store'});
    if(!response.ok)throw new Error('History is temporarily unavailable.');
    const result=await response.json();
    if(generation!==historyRequestSequence||locations[currentIndex]?.id!==location.id||preferences.temperatureGraphRange!=='history30')return;
    if(!result.daily?.time||result.daily.time.length<2)throw new Error('The provider returned incomplete history.');
    const entry={data:{daily:result.daily},fetchedAt:Date.now(),temperatureUnit:preferences.temperatureUnit};saved.histories[location.id]=entry;save();
    renderRangeTrend(result.daily.time,result.daily.temperature_2m_max,result.daily.temperature_2m_min,'past 30 days',true);
  }catch(error){if(generation===historyRequestSequence){if(!cached)holder.textContent=error.message}}
}
let historyRequestSequence=0;
function convertHistory(cached){
  const daily=cached.data.daily,convert=value=>cached.temperatureUnit===preferences.temperatureUnit?value:preferences.temperatureUnit==='celsius'?(value-32)*5/9:value*9/5+32;
  return {time:daily.time,high:daily.temperature_2m_max.map(convert),low:daily.temperature_2m_min.map(convert)};
}
function renderDays(daily){
  const list=$('#day-list');list.replaceChildren();
  daily.time.slice(0,7).forEach((date,index)=>{
    const kind=weatherType(daily.weather_code[index]);
    const button=document.createElement('button');button.type='button';button.className=`day-card${index===0?' today':''}`;button.setAttribute('aria-label',`${index===0?'Today':formatDay(date,{weekday:'long'})}, ${kind.label}, high ${Math.round(daily.temperature_2m_max[index])}${temperatureSuffix()}, low ${Math.round(daily.temperature_2m_min[index])}${temperatureSuffix()}. Show hourly details.`);
    button.innerHTML=`<span class="day-name">${index===0?'Today':formatDay(date)}</span><span class="day-icon" aria-hidden="true">${kind.icon}</span><span class="day-condition">${kind.label}</span><span class="day-temps">${Math.round(daily.temperature_2m_max[index])}${temperatureSuffix()} <span>${Math.round(daily.temperature_2m_min[index])}${temperatureSuffix()}</span></span>`;
    button.addEventListener('click',()=>showDetails(index));list.append(button);
  });
}
function showDetails(dayIndex){
  if(!currentForecast)return;
  pauseAutoScroll();
  const data=currentForecast,day=data.daily.time[dayIndex],daily=data.daily,hourly=data.hourly,kind=weatherType(daily.weather_code[dayIndex]);
  text('details-date',dayIndex===0?'Today':formatDay(day,{weekday:'long',month:'long',day:'numeric'}));
  text('details-summary',`${kind.label} · High ${Math.round(daily.temperature_2m_max[dayIndex])}${temperatureSuffix()} · Low ${Math.round(daily.temperature_2m_min[dayIndex])}${temperatureSuffix()} · Rain chance ${safeNumber(daily.precipitation_probability_max[dayIndex])}%`);
  text('details-daylight',`Sunrise ${localHour(daily.sunrise[dayIndex])} · Sunset ${localHour(daily.sunset[dayIndex])} · UV ${safeNumber(daily.uv_index_max[dayIndex],1)}`);
  const currentHour=data.current.time.slice(0,13);
  const windowRange=hourlyWindow.getHourlyWindow(hourly.time,day,dayIndex===0,currentHour);
  if(!windowRange)return;
  const {start,end,initialIndex,includesTomorrow}=windowRange;
  const list=$('#hourly-list');list.replaceChildren();
  hourly.time.slice(start,end).forEach((time,index)=>{
    const i=start+index,weather=weatherType(hourly.weather_code[i],true),card=document.createElement('div');card.className='hour-card';
    const hourLabel=time.slice(0,10)!==day?`Tomorrow ${localHour(time)}`:dayIndex===0&&time.slice(0,13)===currentHour?'Now':localHour(time);
    card.innerHTML=`<span class="hour-time">${hourLabel}</span><span class="hour-icon" aria-hidden="true">${weather.icon}</span><span class="hour-temp">${Math.round(hourly.temperature_2m[i])}${temperatureSuffix()}</span><span class="hour-rain">Rain ${safeNumber(hourly.precipitation_probability[i])}%</span>`;list.append(card);
  });
  text('hourly-hint',dayIndex===0?(includesTomorrow?'Starts at the current hour and includes a few early hours tomorrow.':'Starts at the current hour; swipe or drag to see the rest of today.'):'Starts at 8 AM; swipe or drag to explore the full day.');
  details.hidden=false;
  requestAnimationFrame(()=>{
    const target=list.children[Math.max(0,initialIndex)];
    const firstCard=list.firstElementChild;
    const centeredLeft=target&&firstCard?target.offsetLeft-firstCard.offsetLeft-(list.clientWidth-target.clientWidth)/2:0;
    list.scrollTo({left:Math.max(0,centeredLeft),top:0,behavior:'instant'});updateHourlyBoundaries();
  });
  resetDetailTimer();
}
function resetDetailTimer(){
  if(details.hidden||detailPointers.size||detailScrollTimer)return;
  clearInterval(countdownTimer);clearTimeout(detailTimer);
  $('#return-idle').hidden=false;$('#return-paused').hidden=true;
  const duration=Number(preferences.returnAfterSeconds)*1000;
  if(!duration){$('#return-idle').hidden=true;$('#return-paused').hidden=true;$('#return-stays-open').hidden=false;$('#countdown-bar').parentElement.hidden=true;return}
  $('#return-idle').hidden=false;$('#return-stays-open').hidden=true;$('#countdown-bar').parentElement.hidden=false;
  const end=Date.now()+duration;
  const tick=()=>{const left=Math.max(0,end-Date.now());text('countdown',Math.ceil(left/1000));$('#countdown-bar').style.transform=`scaleX(${left/duration})`;if(left===0)closeDetails()};
  tick();countdownTimer=setInterval(tick,200);detailTimer=setTimeout(closeDetails,duration);
}
function pauseDetailTimer(){
  if(details.hidden)return;
  clearInterval(countdownTimer);clearTimeout(detailTimer);
  $('#return-idle').hidden=true;$('#return-stays-open').hidden=true;$('#return-paused').hidden=false;$('#countdown-bar').parentElement.hidden=true;
}
function detailScrollActivity(){
  if(details.hidden)return;
  pauseDetailTimer();clearTimeout(detailScrollTimer);
  detailScrollTimer=setTimeout(()=>{detailScrollTimer=null;resetDetailTimer()},250);
}
function closeDetails(){
  clearInterval(countdownTimer);clearTimeout(detailTimer);clearTimeout(detailScrollTimer);detailScrollTimer=null;detailPointers.clear();
  const list=$('#hourly-list');list.scrollTo({left:list.scrollLeft,behavior:'instant'});
  details.hidden=true;
  scheduleAutoScroll();
}
function locationLabel(item){return [item.name,item.admin1,item.country].filter((part,index,array)=>part&&array.indexOf(part)===index).join(', ')}
function escapeHtml(value){return String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]))}
function openEditor(mode='add',{locationId=null,returnToSettings=false}={}){
  pauseAutoScroll();
  editorMode=mode;editingId=mode==='edit'?(locationId||locations[currentIndex]?.id):null;selectedResult=null;settingsReturn=returnToSettings;
  const editingLocation=locations.find(area=>area.id===editingId)||locations[currentIndex];
  closeDetails();settingsScreen.hidden=true;dashboard.hidden=true;addPage.hidden=true;setup.hidden=false;
  text('setup-title',mode==='initial'?'Welcome to Dayglance':mode==='edit'?'Change this location':'Add a location');
  text('setup-copy','Enter a city or ZIP / postal code. Choose a country to narrow the matches, then tap your location.');
  text('search-submit',mode==='initial'?'Start Dayglance':mode==='edit'?'Save location':'Add location');
  $('#city-query').value=mode==='edit'?(editingLocation.postalCode||editingLocation.query||editingLocation.name.split(',')[0]):'';
  $('#country-code').value=mode==='edit'?(editingLocation.countryCode||''):'';
  $('#search-results').replaceChildren();setupError.textContent='';$('#search-submit').disabled=true;$('#cancel-location').hidden=mode==='initial';
  $('#city-query').focus({preventScroll:true});
  pauseAutoScroll();
  if(mode==='edit')scheduleSearch($('#city-query').value);
}
function closeEditor(){if(editorMode==='initial')return;setup.hidden=true;setupError.textContent='';if(settingsReturn){settingsReturn=false;settingsScreen.hidden=false;renderSettings()}else if(showingAddPage)addPage.hidden=false;else{dashboard.hidden=false;scheduleAutoScroll()}}
function scheduleSearch(query){
  clearTimeout(searchTimer);searchSequence++;selectedResult=null;$('#search-submit').disabled=true;setupError.textContent='';
  const host=$('#search-results');host.replaceChildren();
  if(query.trim().length<2){setupError.textContent='Type at least two characters to check a location.';return}
  setupError.textContent='Checking location matches…';searchTimer=setTimeout(()=>searchCity(query.trim()),350);
}
async function searchCity(query){
  const sequence=++searchSequence;selectedResult=null;$('#search-submit').disabled=true;
  try{
    const params=new URLSearchParams({name:query,count:'8',language:navigator.language?.slice(0,2)||'en',format:'json'});
    const country=$('#country-code').value;
    if(country)params.set('countryCode',country);
    const response=await fetch(`${GEOCODE_API}?${params}`);if(!response.ok)throw new Error('Location search is unavailable. Try again shortly.');
    const data=await response.json();if(sequence!==searchSequence)return;
    const results=data.results||[];setupError.textContent=results.length?'Choose a match to validate it.':'No matches yet. Try a city, region, or postal code.';
    const host=$('#search-results');host.replaceChildren();
    results.forEach(item=>{
      const codes=Array.isArray(item.postcodes)?item.postcodes:[];
      const typedPostal=query.trim().toUpperCase(),matchedPostal=codes.find(code=>String(code).toUpperCase()===typedPostal)||'';
      const locationName=locationLabel(item);
      const place={name:matchedPostal?`${locationName} (${matchedPostal})`:locationName,query:matchedPostal||item.name,postalCode:matchedPostal||'',latitude:Number(item.latitude),longitude:Number(item.longitude),countryCode:item.country_code||''};
      const postalInfo=matchedPostal
        ?`ZIP / postal match: ${matchedPostal}${codes.length>1?` · in an area with ${codes.length} listed codes`:''}`
        :codes.length?`${codes.length} ZIP / postal codes · ${codes.slice(0,4).join(', ')}${codes.length>4?`, +${codes.length-4} more. Enter a ZIP for an exact match`:''}`:'';
      const button=document.createElement('button');button.type='button';button.className='result-button';button.setAttribute('aria-selected','false');button.innerHTML=`${escapeHtml(place.name)}<small>${place.latitude.toFixed(2)}°, ${place.longitude.toFixed(2)}°${postalInfo?` · ${escapeHtml(postalInfo)}`:''}</small>`;
      button.addEventListener('click',()=>{
        selectedResult=place;$('#city-query').value=matchedPostal||item.name;$('#country-code').value=place.countryCode;host.querySelectorAll('.result-button').forEach(result=>result.setAttribute('aria-selected','false'));button.setAttribute('aria-selected','true');
        setupError.textContent=`Verified match: ${place.name}`;$('#search-submit').disabled=false;
      });host.append(button);
    });
  }catch(error){if(sequence===searchSequence)setupError.textContent=error.message}
}
function saveSelectedLocation(){
  if(!selectedResult)return;
  const editTarget=locations.find(area=>area.id===editingId);
  const selected={...selectedResult,id:editingId||`user-${Date.now()}-${Math.random().toString(36).slice(2,7)}`,source:editorMode==='edit'?(editTarget?.source||'user'):'user'};
  const returnToSettings=settingsReturn;
  if(editorMode==='initial'||(editorMode==='edit'&&locations[0]?.id===editingId&&editTarget?.source!=='config'))saved.defaultLocation=selected;
  else if(editorMode==='edit'&&configuredLocations.some(area=>area.id===editingId))saved.overrides[editingId]=selected;
  else if(editorMode==='edit')saved.userLocations=saved.userLocations.map(area=>area.id===editingId?selected:area);
  else saved.userLocations.push(selected);
  save();rebuildLocations();
  settingsReturn=false;
  if(returnToSettings){setup.hidden=true;dashboard.hidden=true;addPage.hidden=true;settingsScreen.hidden=false;renderSettings();return}
  const nextIndex=locations.findIndex(area=>area.id===selected.id);
  setup.hidden=true;showingAddPage=false;addPage.hidden=true;dashboard.hidden=false;
  if(nextIndex===currentIndex){currentForecast=null;setPlaceHeading(selected);loadForecast().then(scheduleAutoScroll)}
  else if(nextIndex>=0)showArea(nextIndex,nextIndex>=currentIndex?'next':'previous');
}
function resolveEditedLocation(){
  if(editorMode==='edit')return locations[currentIndex];
  return null;
}
function showAddPage(){
  if(showingAddPage)return;closeDetails();pauseAutoScroll();dashboard.classList.add('exit-left');
  setTimeout(()=>{dashboard.hidden=true;dashboard.classList.remove('exit-left');addPage.hidden=false;showingAddPage=true;addPage.classList.remove('page-enter');void addPage.offsetWidth;addPage.classList.add('page-enter')},180);
}
function showArea(index,direction='next'){
  if(index<0||index>=locations.length)return;
  pauseAutoScroll();
  clearTimeout(detailTimer);closeDetails();
  if(!showingAddPage&&index===currentIndex)return;
  if(showingAddPage){addPage.classList.add(direction==='next'?'exit-left':'exit-right')}
  else dashboard.classList.add(direction==='next'?'exit-left':'exit-right');
  setTimeout(()=>{
    currentIndex=index;showingAddPage=false;updateAreaPosition();
    addPage.hidden=true;addPage.classList.remove('exit-left','exit-right');dashboard.hidden=false;
    dashboard.classList.remove('exit-left','exit-right');dashboard.classList.add(direction==='next'?'enter-right':'enter-left');
    requestAnimationFrame(()=>requestAnimationFrame(()=>dashboard.classList.remove('enter-right','enter-left')));
    currentForecast=null;const cached=saved.forecasts[locations[currentIndex].id],cachedData=forecastInCurrentUnits(cached);
    if(cachedData){currentForecast=cachedData;render(cachedData,locations[currentIndex])}
    loadForecast({showSpinner:!cachedData});
    scheduleAutoScroll();
  },180);
}
function pauseAutoScroll(){clearTimeout(autoScrollTimer);autoScrollTimer=null}
function scheduleAutoScroll(){
  pauseAutoScroll();
  if(!preferences.autoScrollLocations||locations.length<2||!setup.hidden||!details.hidden||!settingsScreen.hidden||!radarScreen.hidden||showingAddPage||document.visibilityState==='hidden')return;
  autoScrollTimer=setTimeout(()=>{
    if(!preferences.autoScrollLocations||locations.length<2||!setup.hidden||!details.hidden||!settingsScreen.hidden||!radarScreen.hidden||showingAddPage||document.visibilityState==='hidden')return;
    const next=currentIndex<locations.length-1?currentIndex+1:0;
    showArea(next,'next');
  },preferences.autoScrollIntervalSeconds*1000);
}
function navigate(direction){
  if(!setup.hidden||!details.hidden)return;
  if(direction>0){if(showingAddPage)return;if(currentIndex<locations.length-1)showArea(currentIndex+1,'next');else showAddPage()}
  else if(showingAddPage)showArea(locations.length-1,'previous');
  else if(currentIndex>0)showArea(currentIndex-1,'previous');
}
function handleSwipeStart(event){touchStart={x:event.clientX,y:event.clientY}}
function handleSwipeEnd(event){
  if(!touchStart)return;const dx=event.clientX-touchStart.x,dy=event.clientY-touchStart.y;touchStart=null;
  if(Math.abs(dx)>58&&Math.abs(dx)>Math.abs(dy)*1.15)navigate(dx<0?1:-1);
}
function submitSearch(event){event.preventDefault();if(selectedResult)saveSelectedLocation();else setupError.textContent='Choose one of the verified location matches first.'}

function renderSettings(){
  const primary=locations[0];text('settings-default-name',primary?.name||'Choose a default location');
  const holder=$('#settings-locations');holder.replaceChildren();
  locations.slice(1).forEach(area=>{
    const row=document.createElement('div');row.className='settings-location-row';
    const label=document.createElement('div');label.className='settings-location-label';
    const name=document.createElement('strong');name.textContent=area.name;
    const source=document.createElement('small');source.textContent=area.source==='config'?'From config.json':'Saved on this device';
    label.append(name,source);
    const actions=document.createElement('div');actions.className='settings-location-actions';
    const edit=document.createElement('button');edit.type='button';edit.className='small-action';edit.textContent='Edit';edit.setAttribute('aria-label',`Edit ${area.name}`);edit.addEventListener('click',()=>openEditor('edit',{locationId:area.id,returnToSettings:true}));
    const remove=document.createElement('button');remove.type='button';remove.className='small-action remove-location';remove.textContent='Remove';remove.setAttribute('aria-label',`Remove ${area.name}`);remove.addEventListener('click',()=>removeLocation(area.id));
    actions.append(edit,remove);row.append(label,actions);holder.append(row);
  });
  if(locations.length<2){const empty=document.createElement('p');empty.className='settings-help';empty.textContent='No additional locations have been added.';holder.append(empty)}
  $('#station-settings').hidden=!stationIntegrations.length;
  renderStationSettings();
}
function renderStationSettings(){
  const holder=$('#station-integrations-list');if(!holder)return;holder.replaceChildren();
  for(const source of stationIntegrations){
    const row=document.createElement('div');row.className='station-integration-row';
    const label=document.createElement('div');label.className='station-integration-name';
    const name=document.createElement('strong');name.textContent=source.name||'Local weather station';
    const sample=stationSamples[source.id];
    const age=sample?.available?Number(sample.ageSeconds||0)+Math.max(0,Math.floor((Date.now()-sample.clientReceivedAt)/1000)):null;
    const fresh=sample?.fresh&&age<=Number(sample.staleAfterSeconds||600);
    const status=document.createElement('small');status.textContent=stationReceiverStatus.startsWith('error:')&&source.connection==='local-upload'?`Receiver error · ${stationReceiverStatus.slice(7)}`:stationReceiverStatus==='unreachable'?'Unable to read station receiver status':fresh?`Receiving data · ${age<60?'just now':`${Math.floor(age/60)} min ago`}`:sample?.available?'Last reading is stale':sample?.status||'Waiting for first reading';
    label.append(name,status);
    const select=document.createElement('select');select.setAttribute('aria-label',`City for ${source.name||'local weather station'}`);
    const unassigned=document.createElement('option');unassigned.value='';unassigned.textContent='Not assigned to a city';select.append(unassigned);
    const assigned=saved.stationAssociations[source.id]||'';
    for(const location of locations){
      const option=document.createElement('option');option.value=location.id;option.textContent=`${location.name}${location.id===locations[0]?.id?' · default':''}`;
      const usedByOther=stationIntegrations.some(other=>other.id!==source.id&&saved.stationAssociations[other.id]===location.id);
      option.disabled=usedByOther;select.append(option);
    }
    select.value=locations.some(location=>location.id===assigned)?assigned:'';
    select.addEventListener('change',()=>{saved.stationAssociations[source.id]=select.value;save();renderStationSettings();if(currentForecast&&locations[currentIndex])render(currentForecast,locations[currentIndex]);$('#settings-status').textContent='Station association saved on this device.'});
    row.append(label,select);holder.append(row);
  }
}
function openSettings(){
  if(!setup.hidden)return;
  if(!radarScreen.hidden)window.DayglanceRadar.close();
  closeDetails();pauseAutoScroll();showingAddPage=false;addPage.hidden=true;settingsScreen.hidden=false;$('#settings-status').textContent='';renderSettings();loadDeviceSettings();window.DayglanceRadar.refreshProviderStatus();
}
function closeSettings(){settingsScreen.hidden=true;if(locations.length){dashboard.hidden=false;showingAddPage=false;scheduleAutoScroll()}else openEditor('initial')}
function removeLocation(id){
  const area=locations.find(item=>item.id===id);if(!area||locations[0]?.id===id)return;
  const currentId=locations[currentIndex]?.id;
  if(configuredLocations.some(item=>item.id===id))saved.hiddenLocationIds=[...new Set([...saved.hiddenLocationIds,id])];
  if(saved.defaultLocation?.id===id)saved.defaultLocation=null;
  for(const [stationId,locationId] of Object.entries(saved.stationAssociations))if(locationId===id)saved.stationAssociations[stationId]='';
  saved.userLocations=saved.userLocations.filter(item=>item.id!==id);
  delete saved.overrides[id];delete saved.resolved[id];delete saved.forecasts[id];delete saved.histories[id];save();rebuildLocations();
  const newIndex=locations.findIndex(item=>item.id===currentId);currentIndex=newIndex>=0?newIndex:0;updateAreaPosition();renderSettings();
  if(locations[currentIndex]){const cached=saved.forecasts[locations[currentIndex].id],cachedData=forecastInCurrentUnits(cached);if(cachedData){currentForecast=cachedData;render(cachedData,locations[currentIndex])}else loadForecast({showSpinner:false})}
}
function changePreference(key,value,refreshForecast=false){
  preferences[key]=value;savePreferences();
  if(key==='radarIdleTimeoutSeconds')window.DayglanceRadar.setIdleTimeout(value);
  if(key==='refreshMinutes')scheduleRefresh();
  if(key==='autoScrollLocations'||key==='autoScrollIntervalSeconds')scheduleAutoScroll();
  if(refreshForecast){save();currentForecast=null;loadForecast()}
  else if(currentForecast&&locations[currentIndex])render(currentForecast,locations[currentIndex]);
  $('#settings-status').textContent='Saved on this device. Changes apply immediately.';
}
function changeGraphRange(value){
  preferences.temperatureGraphRange=value;savePreferences();
  if(value==='forecast16'&&currentForecast?.daily?.time?.length<16){currentForecast=null;loadForecast()}
  else if(currentForecast&&locations[currentIndex])render(currentForecast,locations[currentIndex]);
  $('#settings-status').textContent='Saved on this device. Changes apply immediately.';
}
function editDefaultLocation(){if(!locations[0])return;openEditor('edit',{locationId:locations[0].id,returnToSettings:true})}
async function toggleFullscreen(){
  try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen()}
  catch{text('settings-status','This browser or kiosk session does not allow full-screen switching.')}
}

$('#search-form').addEventListener('submit',submitSearch);
$('#city-query').addEventListener('input',event=>scheduleSearch(event.target.value));
$('#country-code').addEventListener('change',()=>scheduleSearch($('#city-query').value));
$('#cancel-location').addEventListener('click',closeEditor);
$('#add-location').addEventListener('click',()=>openEditor('add'));
$('#edit-location').addEventListener('click',()=>openEditor('edit'));
$('#today-details').addEventListener('click',()=>showDetails(0));
$('#refresh').addEventListener('click',()=>loadForecast());
$('#radar-open').addEventListener('click',()=>{
  const location=locations[currentIndex];
  if(!location)return;
  pauseAutoScroll();window.DayglanceRadar.setIdleTimeout(preferences.radarIdleTimeoutSeconds);window.DayglanceRadar.open(location);
});
window.addEventListener('dayglance-radar-close',scheduleAutoScroll);
$('#close-details').addEventListener('click',closeDetails);
$('#settings-toggle').addEventListener('click',openSettings);
$('#settings-close').addEventListener('click',closeSettings);
// Some small touch displays report finger gestures as mouse drags. Native
// touch-action scrolling still handles real touch input; this fills the gap for
// mouse-like panels without stealing taps on form controls or buttons.
let settingsPan=null;
let suppressSettingsClick=false;
settingsScreen.addEventListener('click',event=>{
  if(!suppressSettingsClick)return;
  suppressSettingsClick=false;
  event.preventDefault();event.stopImmediatePropagation();
},true);
settingsScreen.addEventListener('pointerdown',event=>{
  if(event.pointerType!=='mouse'||event.button!==0||event.target.closest('button,input,select,textarea,a,[role="button"]'))return;
  settingsPan={pointerId:event.pointerId,startY:event.clientY,startTop:settingsScreen.scrollTop,moved:false};
  settingsScreen.classList.add('settings-dragging');
});
settingsScreen.addEventListener('keydown',event=>{
  if(event.target.closest('button,input,select,textarea,a,[contenteditable="true"]'))return;
  const pageStep=Math.max(80,settingsScreen.clientHeight*.8),maxScroll=settingsScreen.scrollHeight-settingsScreen.clientHeight;
  const movement={ArrowDown:40,ArrowUp:-40,PageDown:pageStep,PageUp:-pageStep,' ':pageStep};
  if(event.key==='Home'){event.preventDefault();settingsScreen.scrollTop=0;return}
  if(event.key==='End'){event.preventDefault();settingsScreen.scrollTop=maxScroll;return}
  if(Object.hasOwn(movement,event.key)){event.preventDefault();settingsScreen.scrollTop=Math.max(0,Math.min(maxScroll,settingsScreen.scrollTop+movement[event.key]))}
});
window.addEventListener('pointermove',event=>{
  if(!settingsPan||event.pointerId!==settingsPan.pointerId)return;
  const delta=settingsPan.startY-event.clientY;
  if(!settingsPan.moved&&Math.abs(delta)<5)return;
  settingsPan.moved=true;
  settingsScreen.scrollTop=settingsPan.startTop+delta;
  event.preventDefault();
},{passive:false});
function finishSettingsPan(event){
  if(!settingsPan||event.pointerId!==settingsPan.pointerId)return;
  const dragged=settingsPan.moved;
  settingsScreen.classList.remove('settings-dragging');
  settingsPan=null;
  if(dragged){suppressSettingsClick=true;window.setTimeout(()=>{suppressSettingsClick=false},0)}
}
window.addEventListener('pointerup',finishSettingsPan,{passive:true});
window.addEventListener('pointercancel',finishSettingsPan,{passive:true});
$('#settings-edit-default').addEventListener('click',editDefaultLocation);
$('#settings-add-location').addEventListener('click',()=>openEditor('add',{returnToSettings:true}));
$('#setting-return-time').addEventListener('change',event=>changePreference('returnAfterSeconds',Number(event.target.value)));
$('#setting-radar-timeout').addEventListener('change',event=>changePreference('radarIdleTimeoutSeconds',Number(event.target.value)));
$('#setting-temperature').addEventListener('change',event=>changePreference('temperatureUnit',event.target.value,true));
$('#setting-measurement').addEventListener('change',event=>changePreference('measurementSystem',event.target.value,true));
$('#setting-clock').addEventListener('change',event=>changePreference('clockFormat',event.target.value));
$('#setting-refresh').addEventListener('change',event=>changePreference('refreshMinutes',Number(event.target.value)));
$('#setting-graph-range').addEventListener('change',event=>changeGraphRange(event.target.value));
$('#setting-auto-scroll').addEventListener('change',event=>changePreference('autoScrollLocations',event.target.checked));
$('#setting-auto-scroll-interval').addEventListener('change',event=>changePreference('autoScrollIntervalSeconds',Number(event.target.value)));
$('#setting-bumpers').addEventListener('change',event=>changePreference('showBumpers',event.target.checked));
$('#setting-auto-start').addEventListener('click',()=>saveDeviceSettings(!deviceSettings.autoStart));
$('#setting-kiosk').addEventListener('change',()=>saveDeviceSettings(deviceSettings.autoStart));
$('#fullscreen-now').addEventListener('click',toggleFullscreen);
// Hold the view open throughout a touch/drag and scrolling momentum, then start a fresh idle period.
details.addEventListener('pointerdown',event=>{detailPointers.add(event.pointerId);pauseDetailTimer()},{passive:true});
function finishDetailPointer(event){
  if(!detailPointers.delete(event.pointerId))return;
  resetDetailTimer();
}
window.addEventListener('pointerup',finishDetailPointer,{passive:true});
window.addEventListener('pointercancel',finishDetailPointer,{passive:true});
details.addEventListener('wheel',detailScrollActivity,{passive:true});
details.addEventListener('keydown',resetDetailTimer);
const hourlyList=$('#hourly-list');
function updateHourlyBoundaries(){
  const max=Math.max(0,hourlyList.scrollWidth-hourlyList.clientWidth);
  $('#hours-previous').disabled=hourlyList.scrollLeft<=1;
  $('#hours-next').disabled=hourlyList.scrollLeft>=max-1;
}
hourlyList.addEventListener('scroll',()=>{updateHourlyBoundaries();detailScrollActivity()},{passive:true});
window.addEventListener('resize',updateHourlyBoundaries);
for(const [id,direction] of [['hours-previous',-1],['hours-next',1]]){
  $(`#${id}`).addEventListener('click',()=>{
    resetDetailTimer();hourlyList.scrollBy({left:direction*hourlyList.clientWidth*.8,behavior:'smooth'});
  });
}
// Some touch panels report mouse events: support dragging the cards as well as native touch panning.
let hourlyDrag=null;
hourlyList.addEventListener('pointerdown',event=>{
  if(event.pointerType!=='mouse'||event.button!==0)return;
  hourlyDrag={id:event.pointerId,x:event.clientX,left:hourlyList.scrollLeft};
  hourlyList.setPointerCapture(event.pointerId);hourlyList.classList.add('dragging');event.preventDefault();
});
hourlyList.addEventListener('pointermove',event=>{
  if(!hourlyDrag||event.pointerId!==hourlyDrag.id)return;
  const max=Math.max(0,hourlyList.scrollWidth-hourlyList.clientWidth);
  hourlyList.scrollLeft=Math.max(0,Math.min(max,hourlyDrag.left+hourlyDrag.x-event.clientX));
});
function finishHourlyDrag(){hourlyDrag=null;hourlyList.classList.remove('dragging')}
hourlyList.addEventListener('pointerup',finishHourlyDrag);
hourlyList.addEventListener('pointercancel',finishHourlyDrag);
hourlyList.addEventListener('lostpointercapture',finishHourlyDrag);
dashboard.addEventListener('pointerdown',handleSwipeStart);dashboard.addEventListener('pointerup',handleSwipeEnd);
addPage.addEventListener('pointerdown',handleSwipeStart);addPage.addEventListener('pointerup',handleSwipeEnd);
dashboard.addEventListener('pointerdown',refreshAfterResume,{passive:true});
const appRoot=$('#app');
appRoot.addEventListener('pointerdown',pauseAutoScroll,{passive:true});
window.addEventListener('pointerup',scheduleAutoScroll,{passive:true});
appRoot.addEventListener('wheel',()=>{pauseAutoScroll();setTimeout(scheduleAutoScroll,500)},{passive:true});
appRoot.addEventListener('keydown',()=>{pauseAutoScroll();setTimeout(scheduleAutoScroll,500)});
addPage.addEventListener('pointerdown',refreshAfterResume,{passive:true});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'){refreshAfterResume();scheduleAutoScroll()}else pauseAutoScroll()});
window.addEventListener('pageshow',refreshAfterResume);
document.addEventListener('keydown',event=>{if(event.key==='Escape'){if(!radarScreen.hidden)window.DayglanceRadar.close();else if(!details.hidden)closeDetails();else if(!setup.hidden)closeEditor();else if(!settingsScreen.hidden)closeSettings()}});
const regionNames=new Intl.DisplayNames(['en'],{type:'region'});
const countryCodes='AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW'.split(' ');
countryCodes.map(code=>({code,name:regionNames.of(code)})).sort((a,b)=>a.name.localeCompare(b.name)).forEach(({code,name})=>$('#country-code').add(new Option(name,code)));
if('serviceWorker' in navigator)navigator.serviceWorker.register('./sw.js').catch(()=>{});
initialize();
