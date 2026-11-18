/** Preserve the tracer's actual directed edges, including branches and recursion. */
export function buildFlowGraph(edges) {
 const ids=[...new Set(edges.flatMap(edge=>[edge.from,edge.to]))];
 const nodes=ids.map((id,index)=>({id,x:170,y:30+index*100,width:420,height:50}));
 const byId=new Map(nodes.map(node=>[node.id,node]));
 const links=edges.map((edge,index)=>{
  const source=byId.get(edge.from),target=byId.get(edge.to);
  const x=590,y1=source.y+25,y2=target.y+25;
  const lane=630+(index%5)*16;
  const path=source===target?`M ${x} ${y1-10} C ${lane+25} ${y1-60}, ${lane+25} ${y1+60}, ${x} ${y1+10}`:`M ${x} ${y1} C ${lane} ${y1}, ${lane} ${y2}, ${x} ${y2}`;
  return {...edge,path,index,labelX:15,labelY:20+index*22};
 });
 return {nodes,links,width:740,height:Math.max(nodes.length*100+30,links.length*22+40)};
}
