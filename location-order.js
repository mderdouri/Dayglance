(function attachLocationOrder(root,factory){
  const api=factory();
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.DayglanceLocationOrder=api;
})(typeof globalThis!=='undefined'?globalThis:this,function createLocationOrder(){
  function arrange(items,defaultId,orderIds=[]){
    const rank=new Map(orderIds.map((id,index)=>[id,index]));
    const ordered=[...items].sort((a,b)=>{
      const aRank=rank.has(a.id)?rank.get(a.id):Number.MAX_SAFE_INTEGER;
      const bRank=rank.has(b.id)?rank.get(b.id):Number.MAX_SAFE_INTEGER;
      return aRank-bRank;
    });
    const defaultLocation=ordered.find(item=>item.id===defaultId)||ordered[0];
    return defaultLocation?[defaultLocation,...ordered.filter(item=>item.id!==defaultLocation.id)]:[];
  }

  function move(items,id,direction){
    const ordered=[...items];
    const index=ordered.findIndex(item=>item.id===id);
    const target=index+direction;
    if(index<1||target<1||target>=ordered.length)return ordered;
    [ordered[index],ordered[target]]=[ordered[target],ordered[index]];
    return ordered;
  }

  return {arrange,move};
});
