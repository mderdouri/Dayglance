const test = require('node:test');
const assert = require('node:assert/strict');
const {formatAirQuality} = require('../air-quality.js');

test('formats a U.S. AQI and PM2.5 estimate', () => {
  assert.deepEqual(formatAirQuality({us_aqi:49,pm2_5:3.8}),{
    value:'49 · Good',category:'Good',ariaLabel:'U.S. AQI 49, Good',pm25:'PM2.5 3.8 μg/m³'
  });
});

test('uses EPA U.S. AQI category boundaries', () => {
  const cases = [[50,'Good'],[51,'Moderate'],[100,'Moderate'],[101,'Unhealthy for Sensitive Groups'],[151,'Unhealthy'],[201,'Very Unhealthy'],[301,'Hazardous']];
  for (const [us_aqi,category] of cases) assert.equal(formatAirQuality({us_aqi}).category,category);
});

test('rounds fractional AQI and handles missing particulate data', () => {
  assert.deepEqual(formatAirQuality({us_aqi:50.6,pm2_5:null}),{
    value:'51 · Moderate',category:'Moderate',ariaLabel:'U.S. AQI 51, Moderate',pm25:'PM2.5 —'
  });
});

test('reports an unavailable estimate for absent or invalid AQI', () => {
  for (const current of [null,{}, {us_aqi:null}, {us_aqi:'unavailable'}]) {
    assert.deepEqual(formatAirQuality(current),{
      value:'Unavailable',category:'Air-quality estimate unavailable',ariaLabel:'U.S. AQI unavailable',pm25:'PM2.5 —'
    });
  }
});

