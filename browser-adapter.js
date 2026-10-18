import {ReviewSession} from './review.js';
import {reviewFixture} from './review-fixtures.js';
import {runScenario} from './browser-workflow.js';
export function createBrowserAdapter(){
 let data,session;
 return {label:'Browser JavaScript · state lives in this tab',
  async reset(name){data=reviewFixture(name);session=new ReviewSession(data.request,data.sources,data.context,data.crm);return session.view();},
  async command(action,args={}){
   if(action==='prepare')return session.prepare();
   if(action==='approve'||action==='reject')return session.decide(args.review_id,action,args.reviewed_digest);
   if(action==='execute')return session.execute(args.review_id);
   if(action==='change_source'){
    if(!data.sources.length)throw new Error('No fixture source to change.');
    data.sources[0].observed_at=data.sources[0].observed_at==='2026-10-15'?'2026-10-16':'2026-10-15';
    session.replaceInputs({sources:data.sources});return session.view();
   }
   throw new Error('Unknown review command');
  },legacy:runScenario};
}
