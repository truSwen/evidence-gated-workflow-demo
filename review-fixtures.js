import fixture from './review-fixtures.json' with {type:'json'};
import {DEFAULT_CONTEXT} from './review.js';
export function reviewFixture(name){
 const data={...structuredClone(fixture),context:structuredClone(DEFAULT_CONTEXT)};
 if(name==='missing')data.sources=[];
 else if(name==='stale')data.sources[0].observed_at='2020-01-01';
 else if(name==='unknown')data.sources[0].facts.open_roles=null;
 else if(name==='conflict')data.sources.push({id:'fixture-source-002',source_url:'https://example.org/second-fixture',observed_at:'2026-10-16',facts:{open_roles:5}});
 else if(name!=='valid')throw new Error('Unknown review fixture');
 return data;
}
