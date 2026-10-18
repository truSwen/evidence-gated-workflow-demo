import {test} from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import fixture from './review-fixtures.json' with {type:'json'};
import {canonical,digest,ReviewSession,DEFAULT_CONTEXT,buildPackage} from './review.js';
import {cases,runCase} from './tests/run-review-cases.js';
const python=JSON.parse(execFileSync('python3',['tests/run_review_cases.py'],{encoding:'utf8',maxBuffer:20*1024*1024}));
for(const spec of cases)test(`V2 states, write counts and full Python parity: ${spec.name}`,async()=>{
 const results=await runCase(spec);let i=0;
 for(const step of spec.steps){
  if(['mutate','tamper_return'].includes(step.op))continue;
  const actual=results[i++];
  assert.equal(actual.status,step.status);assert.equal(actual.code,step.code);assert.equal(actual.write_count,step.writes);
  if(step.issue)assert.ok(actual.reviews.at(-1).package.validation.issues.includes(step.issue));
  assert.equal(new Set(actual.events.map(e=>e.event_id)).size,actual.events.length);
 }
 assert.deepEqual(results,python[spec.name]);
});
test('canonical known vector and independently specified SHA-256',async()=>{
 assert.equal(canonical({z:[null,true,7],a:'quote"slash\\'}),'{"a":"quote\\"slash\\\\","z":[null,true,7]}');
 assert.equal(await digest({a:1}),'015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862');
});
test('ambiguous JSON values refused',()=>{
 for(const v of [1.5,NaN,Infinity,'é','\n',9007199254740992,undefined,new Date(),{x:undefined}])assert.throws(()=>canonical(v),/INVALID_INPUT/);
});
test('semantic collection order does not change package',async()=>{
 const d=structuredClone(fixture);const a=await buildPackage(d.request,d.sources,DEFAULT_CONTEXT,d.crm);
 d.request.claims.reverse();const b=await buildPackage(d.request,d.sources,Object.fromEntries(Object.entries(DEFAULT_CONTEXT).reverse()),d.crm);
 assert.deepEqual(a,b);
});
test('malformed claims produce structured refusal',async()=>{
 for(const value of [[],{},2,null]){const d=structuredClone(fixture);d.request.claims[0].field=value;assert.equal((await new ReviewSession(d.request,d.sources,DEFAULT_CONTEXT,d.crm).prepare()).code,'INVALID_CLAIM');}
});
test('async transitions and input swaps cannot race within the tab',async()=>{
 const d=structuredClone(fixture),s=new ReviewSession(d.request,d.sources,DEFAULT_CONTEXT,d.crm);
 const preparing=s.prepare();
 assert.throws(()=>s.replaceInputs({sources:[]}),/OPERATION_IN_PROGRESS/);
 await assert.rejects(()=>s.execute('review-0001'),/OPERATION_IN_PROGRESS/);
 const v=await preparing;assert.equal(v.status,'AWAITING_APPROVAL');assert.equal(v.write_count,0);
});
test('returned documents and constructor inputs are isolated copies',async()=>{
 const d=structuredClone(fixture),s=new ReviewSession(d.request,d.sources,DEFAULT_CONTEXT,d.crm);
 const v=await s.prepare(),original=structuredClone(v);
 d.sources[0].observed_at='2020-01-01';v.reviews[0].status='APPROVED';v.reviews[0].package.payload.company_id='synthetic-company-forged';
 assert.deepEqual(s.view(),original);assert.equal((await s.execute('review-0001')).write_count,0);
});
