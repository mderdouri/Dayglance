(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.DayglanceAirQuality = api;
})(globalThis, function () {
  const categories = [
    {maximum:50,name:'Good',shortName:'Good'},
    {maximum:100,name:'Moderate',shortName:'Moderate'},
    {maximum:150,name:'Unhealthy for Sensitive Groups',shortName:'Sensitive'},
    {maximum:200,name:'Unhealthy',shortName:'Unhealthy'},
    {maximum:300,name:'Very Unhealthy',shortName:'Very unhealthy'},
    {maximum:Infinity,name:'Hazardous',shortName:'Hazardous'}
  ];

  function formatAirQuality(current) {
    if (current?.us_aqi == null || current.us_aqi === '') return {value:'Unavailable',category:'Air-quality estimate unavailable',ariaLabel:'U.S. AQI unavailable',pm25:'PM2.5 —'};
    const aqi = Number(current.us_aqi);
    if (!Number.isFinite(aqi) || aqi < 0) return {value:'Unavailable',category:'Air-quality estimate unavailable',ariaLabel:'U.S. AQI unavailable',pm25:'PM2.5 —'};
    const roundedAqi = Math.round(aqi);
    const category = categories.find(item => roundedAqi <= item.maximum);
    const particulate = current.pm2_5 == null ? NaN : Number(current.pm2_5);
    return {
      value:`${roundedAqi} · ${category.shortName}`,
      category:category.name,
      ariaLabel:`U.S. AQI ${roundedAqi}, ${category.name}`,
      pm25:Number.isFinite(particulate)?`PM2.5 ${particulate.toFixed(1)} μg/m³`:'PM2.5 —'
    };
  }

  return {formatAirQuality};
});
