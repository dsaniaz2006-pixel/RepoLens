import test from 'node:test';
import assert from 'node:assert/strict';
import {usageRows,usageLabels} from '../src/features/usage/usageDisplay.mjs';
test('usage panels display the three free plan actions',()=>{
 const rows=usageRows({usage:{analyze:{used:3,limit:5},ask:{used:12,limit:20},index:{used:1,limit:2}}});
 assert.deepEqual(rows.map(r=>r.percent),[60,60,50]);
 assert.deepEqual(rows.map(r=>r.remaining),[2,8,1]);
 assert.equal(rows[0].label,'Repository analysis');
});
test('usage rows clamp invalid totals and exhausted allowance',()=>{
 const rows=usageRows({usage:{analyze:{used:100,limit:5}}});
 assert.equal(rows[0].percent,100);
 assert.equal(rows[0].remaining,0);
 assert.deepEqual(usageRows(null),[]);
});
