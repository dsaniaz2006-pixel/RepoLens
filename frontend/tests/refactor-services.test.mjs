import test from 'node:test';
import assert from 'node:assert/strict';
import {WORKSPACE_PAGES,isWorkspacePage,nextWorkspacePage} from '../src/state/workspaceNavigation.mjs';
import {serverErrorMessage} from '../src/services/errors.mjs';
import {postJSON as publicPostJSON} from '../src/apiClient.js';
import {postJSON as servicePostJSON} from '../src/services/apiClient.js';

test('workspace navigation state preserves valid views and rejects unknown pages',()=>{
 assert.deepEqual(WORKSPACE_PAGES,['Home','Analyze Repo','Knowledge Hub','Conversations','Past Analyses','Settings','Public Gallery']);
 assert.equal(isWorkspacePage('Knowledge Hub'),true);
 assert.equal(isWorkspacePage('billing'),false);
 assert.equal(nextWorkspacePage('Home','Settings'),'Settings');
 assert.equal(nextWorkspacePage('Home','unknown URL'),'Home');
 assert.equal(nextWorkspacePage('Home','/login/'),'Home');
});

test('API service offers the same stable public import',()=>{
 assert.equal(publicPostJSON,servicePostJSON);
});

test('HTTP error formatter prioritizes bounded server detail without exposing HTML',()=>{
 assert.match(serverErrorMessage(502,'<!doctype html>',''),/HTTP 502.*non-JSON/);
 assert.doesNotMatch(serverErrorMessage(502,'<html>private response</html>',''),/private response/);
 assert.equal(serverErrorMessage(403,'','Access denied'),'Access denied');
 assert.equal(serverErrorMessage(422,'',[{msg:'Invalid URL'}]),'Invalid URL');
 assert.equal(serverErrorMessage(500,'','x'.repeat(4000)).length,1000);
});
