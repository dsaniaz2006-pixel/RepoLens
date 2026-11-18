import test from 'node:test';
import assert from 'node:assert/strict';
import {buildFlowGraph} from '../src/features/knowledge/flowGraph.mjs';
test('diagram preserves actual branches and disconnected edges without inventing a chain',()=>{
 const edges=[{from:'main',to:'left',link_type:'CONFIRMED'},{from:'main',to:'right',link_type:'INFERRED'},{from:'other',to:'isolated',link_type:'CONFIRMED'}];
 const graph=buildFlowGraph(edges);
 assert.deepEqual(graph.links.map(({from,to})=>[from,to]),[['main','left'],['main','right'],['other','isolated']]);
 assert.equal(graph.nodes.length,5);
 assert.equal(graph.links[0].path.split(' C ')[0],graph.links[1].path.split(' C ')[0]);
 assert.notEqual(graph.links[0].path,graph.links[1].path);
});
test('recursive call gets a non-degenerate loop and empty graphs stay empty',()=>{
 const graph=buildFlowGraph([{from:'repeat',to:'repeat',link_type:'CONFIRMED'}]);
 assert.equal(graph.nodes.length,1);
 assert.match(graph.links[0].path,/ C /);
 assert.equal(buildFlowGraph([]).nodes.length,0);
});
