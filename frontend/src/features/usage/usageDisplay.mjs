export const usageLabels={analyze:'Repository analysis',ask:'AI chat questions',index:'RAG indexing'};
export function usageRows(payload){
  if(!payload || typeof payload.usage!=='object')return [];
  return ['analyze','ask','index'].map(key=>{
    const value=payload.usage[key]||{};
    const limit=Math.max(0,Number(value.limit)||0);
    const used=Math.max(0,Number(value.used)||0);
    return {key,label:usageLabels[key],used,limit,remaining:Math.max(0,limit-used),
      percent:limit>0?Math.min(100,Math.round(100*used/limit)):100};
  });
}
