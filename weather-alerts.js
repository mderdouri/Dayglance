(function attachWeatherAlertHelpers(root){
  function identifier(feature){
    const properties=feature?.properties||{};
    const known=feature?.id||properties.id||properties['@id'];
    if(typeof known==='string'&&known.trim())return known.trim();
    return [properties.event,properties.areaDesc,properties.effective||properties.onset,properties.headline]
      .map(value=>String(value||'').trim()).join('|');
  }

  function unseen(features,seenIds){
    if(!(seenIds instanceof Set))return [];
    const unseen=[];
    for(const feature of Array.isArray(features)?features:[]){
      const id=identifier(feature);
      if(!id.replace(/\|/g,''))continue;
      if(seenIds.has(id))continue;
      if(!unseen.includes(id))unseen.push(id);
    }
    return unseen;
  }

  function markSeen(ids,seenIds){
    if(!(seenIds instanceof Set))return;
    for(const id of Array.isArray(ids)?ids:[]){
      seenIds.add(id);
      if(seenIds.size>512)seenIds.delete(seenIds.values().next().value);
    }
  }

  function markForCurrentLocation(locationId,currentLocationId,record,visibleFeatures,seenIds,isDocumentVisible=true){
    if(!isDocumentVisible||locationId!==currentLocationId||record?.stale)return [];
    return unseen(visibleFeatures,seenIds);
  }

  root.DayglanceAlertWake={identifier,unseen,markSeen,markForCurrentLocation};
})(window);
