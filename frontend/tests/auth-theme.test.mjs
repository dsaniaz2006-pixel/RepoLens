import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const text=p=>readFileSync(resolve(root,p),'utf8');

test('sign-up and login mount the shared React AuthComponent rather than a disconnected demo',()=>{
  for(const dir of ['login','signup']) {
    const html=text(`${dir}/index.html`);
    assert.match(html,/id="auth-root"/);
    assert.match(html,/src="\/src\/auth\.jsx"/);
    assert.doesNotMatch(html,/src="\/site\/app\.js"/);
  }
  assert.match(text('src/auth.jsx'),/AuthComponent/);
});

test('OAuth provider navigation is allowlisted and retains a valid join invitation',async()=>{
  const {oauthLoginUrl,postLoginRedirect}=await import('../src/components/ui/authFlow.mjs');
  assert.equal(oauthLoginUrl('google',''),'/api/auth/login/google');
  assert.equal(oauthLoginUrl('github','/join?token='+'a'.repeat(24)),'/api/auth/login/github?next='+encodeURIComponent('/join?token='+'a'.repeat(24)));
  assert.equal(oauthLoginUrl('google','https://evil.example/'),'/api/auth/login/google');
  assert.equal(postLoginRedirect('/join?token='+'a'.repeat(24)),'/join?token='+'a'.repeat(24));
  assert.equal(postLoginRedirect('//evil.example/'),'/dashboard/');
  assert.throws(()=>oauthLoginUrl('some-other-provider',''),/Unsupported provider/);
});

test('invalid provider metadata fails closed so unconfigured OAuth cannot be clicked',async()=>{
  const {getProviderAvailability}=await import('../src/components/ui/authFlow.mjs');
  assert.deepEqual(getProviderAvailability({providers:{google:true,github:false}}),{google:true,github:false});
  assert.throws(()=>getProviderAvailability({providers:{google:'yes',github:true}}));
  assert.throws(()=>getProviderAvailability({}));
});

test('auth UI stays in the charcoal-and-blue palette without the demo confetti flow',()=>{
  const css=text('src/components/ui/auth.css');
  const component=text('src/components/ui/sign-up.jsx');
  assert.match(css,/#121416/i);
  assert.match(css,/#222528/i);
  assert.match(css,/#28547a/i);
  assert.match(css,/prefers-reduced-motion/);
  assert.doesNotMatch(css,/#(?:ff00ff|ffff00|a855f7|ef4444|facc15)\b/i);
  assert.match(component,/\/api\/auth\/providers/);
  assert.match(component,/getProviderAvailability/);
  assert.doesNotMatch(component,/canvas-confetti|signing you up|passwords do not match/i);
});
