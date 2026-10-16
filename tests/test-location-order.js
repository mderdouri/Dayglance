const test=require('node:test');
const assert=require('node:assert/strict');
const {arrange,move}=require('../location-order.js');

const places=[{id:'dc'},{id:'boston'},{id:'nyc'}];

test('configured order remains the default when there is no saved default or custom order',()=>{
  assert.deepEqual(arrange(places,'dc').map(place=>place.id),['dc','boston','nyc']);
});

test('saved default becomes the first displayed location and other saved order is retained',()=>{
  assert.deepEqual(arrange(places,'nyc',['dc','nyc','boston']).map(place=>place.id),['nyc','dc','boston']);
});

test('unknown saved ids are ignored and newly added locations follow existing ordered locations',()=>{
  const withNew=[...places,{id:'philly'}];
  assert.deepEqual(arrange(withNew,'dc',['nyc','missing','boston']).map(place=>place.id),['dc','nyc','boston','philly']);
});

test('saved default falls back to the first available location when the selected one was removed',()=>{
  assert.deepEqual(arrange(places,'removed',['nyc','dc']).map(place=>place.id),['nyc','dc','boston']);
});

test('additional locations can move in either direction without moving the default',()=>{
  assert.deepEqual(move(places,'nyc',-1).map(place=>place.id),['dc','nyc','boston']);
  assert.deepEqual(move(places,'boston',1).map(place=>place.id),['dc','nyc','boston']);
});

test('movement stops at the first and last additional location',()=>{
  assert.deepEqual(move(places,'boston',-1).map(place=>place.id),['dc','boston','nyc']);
  assert.deepEqual(move(places,'nyc',1).map(place=>place.id),['dc','boston','nyc']);
});
