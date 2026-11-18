import React,{useId} from 'react';
import {buildFlowGraph} from './flowGraph.mjs';
export default function FlowDiagram({edges}) {
 const arrowId=useId().replaceAll(':','')+'-call-arrow';
 const graph=buildFlowGraph(edges);
 if(!graph.nodes.length)return null;
 return <div style={{overflow:'auto',maxHeight:900}}><svg role="img" aria-label="Source call-flow diagram" viewBox={`0 0 ${graph.width} ${graph.height}`} style={{width:'100%',minWidth:650}}>
  <defs><marker id={arrowId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#7ee2b8"/></marker></defs>
  {graph.links.map(edge=><g key={edge.index}><path d={edge.path} fill="none" stroke="#7ee2b8" strokeDasharray={edge.link_type!=='CONFIRMED'?'5 4':undefined} markerEnd={`url(#${arrowId})`}><title>{edge.from} → {edge.to} ({edge.link_type})</title></path><text x={edge.labelX} y={edge.labelY} fill="currentColor" fontSize="11">{edge.index+1}: {edge.link_type}</text></g>)}
  {graph.nodes.map(node=><g key={node.id}><rect x={node.x} y={node.y} width={node.width} height={node.height} rx="8" fill="#183e32" stroke="#7ee2b8"/><text x={node.x+node.width/2} y={node.y+30} textAnchor="middle" fill="white" fontSize="12">{node.id.length>55?node.id.slice(0,52)+'…':node.id}<title>{node.id}</title></text></g>)}
 </svg><p className="muted">Arrows follow recorded caller → callee relationships. Dashed arrows require source review. The evidence table below lists each connection.</p></div>;
}
