import fixture from '../review-fixtures.json' with {type:'json'};
import cases from './review-cases.json' with {type:'json'};
import {ReviewSession,DEFAULT_CONTEXT} from '../review.js';
export {cases};
export async function runCase(spec){
 const data={...structuredClone(fixture),context:structuredClone(DEFAULT_CONTEXT)};
 const session=new ReviewSession(data.request,data.sources,data.context,data.crm);
 let view=session.view();const results=[];
 for(const action of spec.steps){
  const op=action.op,rid=action.review_id??view.reviews.at(-1)?.review_id??'review-0001';
  if(op==='mutate'){let target=data;for(const key of action.path.slice(0,-1))target=target[key];target[action.path.at(-1)]=structuredClone(action.value);session.replaceInputs(data);continue;}
  if(op==='tamper_return'){view.reviews.at(-1).status='APPROVED';view.reviews.at(-1).package.evidence_snapshot.sources[0].facts.open_roles=100;continue;}
  if(op==='prepare')view=await session.prepare();
  else if(op==='approve'||op==='reject')view=await session.decide(rid,op,action.digest??view.reviews.at(-1)?.package?.approval_digest??'missing');
  else if(op==='execute')view=await session.execute(rid);
  else throw new Error('Unknown test action');
  results.push(view);
 }
 return results;
}
