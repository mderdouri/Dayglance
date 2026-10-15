const test = require('node:test');
const assert = require('node:assert/strict');
const {getHourlyWindow} = require('../detail-hours.js');

function hourlyTimes(days) {
  return days.flatMap(day => Array.from({length:24}, (_,hour) => `${day}T${String(hour).padStart(2,'0')}:00`));
}

const times = hourlyTimes(['2026-10-15','2026-10-16','2026-10-17']);

test('today begins at the current hour and omits earlier hours', () => {
  assert.deepEqual(getHourlyWindow(times,'2026-10-15',true,'2026-10-15T14'),{start:14,end:24,initialIndex:0,includesTomorrow:false});
});

test('today adds four hours from tomorrow when six or fewer hours remain', () => {
  assert.deepEqual(getHourlyWindow(times,'2026-10-15',true,'2026-10-15T20'),{start:20,end:28,initialIndex:0,includesTomorrow:true});
});

test('today does not add tomorrow when more than six hours remain', () => {
  assert.deepEqual(getHourlyWindow(times,'2026-10-15',true,'2026-10-15T17'),{start:17,end:24,initialIndex:0,includesTomorrow:false});
});

test('future days keep all 24 hours and select 8 AM as the initial center', () => {
  assert.deepEqual(getHourlyWindow(times,'2026-10-16',false,'2026-10-15T14'),{start:24,end:48,initialIndex:8,includesTomorrow:false});
});

test('returns null when hourly data does not contain the selected day', () => {
  assert.equal(getHourlyWindow(times,'2026-10-20',false,'2026-10-15T14'),null);
});

