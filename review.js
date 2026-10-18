// V2 synthetic state machine. Public return values are copies, never authorization state.
export const DEFAULT_CONTEXT = Object.freeze({policy_version:'evidence-review-v2.1',reference_date:'2026-10-17',max_age_days:30,allowed_tool:'crm.apply_local',synthetic:true});
const FIELDS=['company_name','country','open_roles'];
const LIMITS=[
 'All companies, sources, values and CRM records are synthetic; URLs are never fetched.',
 'Consistency with fixture records does not establish real-world truth.',
 'The decision is interactive; the reviewer identity is simulated, not authenticated or signed.',
 'In-memory sequential execution only: no durable ledger, atomic transaction or concurrency guarantee.'
];
export class InvalidInput extends Error {}
const plain=v=>v!==null&&typeof v==='object'&&!Array.isArray(v)&&Object.getPrototypeOf(v)===Object.prototype;
const ascii=v=>typeof v==='string'&&v.length<=500&&/^[\x20-\x7e]*$/.test(v);
export function canonical(value,depth=0){
 if(depth>12)throw new InvalidInput('INVALID_INPUT');
 if(value===null||typeof value==='boolean')return JSON.stringify(value);
 if(typeof value==='number'&&Number.isSafeInteger(value))return JSON.stringify(value);
 if(ascii(value))return JSON.stringify(value);
 if(Array.isArray(value)&&value.length<=100)return '['+value.map(v=>canonical(v,depth+1)).join(',')+']';
 if(plain(value)&&Object.keys(value).length<=100){
  const keys=Object.keys(value).sort();
  if(keys.some(k=>!k||!ascii(k)))throw new InvalidInput('INVALID_INPUT');
  return '{'+keys.map(k=>JSON.stringify(k)+':'+canonical(value[k],depth+1)).join(',')+'}';
 }
 throw new InvalidInput('INVALID_INPUT');
}
export async function digest(value){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(value)));return [...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,'0')).join('');}
const exact=(v,keys)=>plain(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
const identifier=(v,prefix)=>typeof v==='string'&&new RegExp('^'+prefix+'[A-Za-z0-9-]{1,60}$').test(v);
const validDate=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&v.slice(0,4)!=='0000'&&Number.isFinite(Date.parse(v+'T00:00:00Z'))&&new Date(v+'T00:00:00Z').toISOString().slice(0,10)===v;
const validValue=(field,v)=>v===null||(field==='open_roles'?Number.isInteger(v)&&v>=0&&v<=10000:typeof v==='string'&&v.length>0&&v.length<=100);
const validRecord=v=>plain(v)&&Object.keys(v).every(k=>FIELDS.includes(k)&&validValue(k,v[k]));
const sourceUrl=v=>/^https:\/\/example\.org\/[A-Za-z0-9/_-]{1,120}$/.test(v);
const age=(reference,observed)=>(Date.parse(reference+'T00:00:00Z')-Date.parse(observed+'T00:00:00Z'))/86400000;
export async function buildPackage(request,sources,context,crm){
 canonical({request,sources,context,crm});
 if(!exact(request,['request_id','company_id','requested_tool','claims'])||!identifier(request.request_id,'demo-request-')||!identifier(request.company_id,'synthetic-company-'))throw new InvalidInput('INVALID_REQUEST');
 if(!exact(context,Object.keys(DEFAULT_CONTEXT))||context.synthetic!==true||!validDate(context.reference_date)||!Number.isInteger(context.max_age_days)||context.max_age_days<0||context.max_age_days>90||typeof context.policy_version!=='string'||!context.policy_version||context.allowed_tool!=='crm.apply_local')throw new InvalidInput('INVALID_CONTEXT');
 if(!Array.isArray(sources)||sources.length>10||!Array.isArray(request.claims)||request.claims.length<1||request.claims.length>3)throw new InvalidInput('INVALID_REQUEST');
 const claims=structuredClone(request.claims);
 if(claims.some(c=>!exact(c,['field','value','source_id'])||!FIELDS.includes(c.field)||!validValue(c.field,c.value)||!identifier(c.source_id,'fixture-source-')))throw new InvalidInput('INVALID_CLAIM');
 claims.sort((a,b)=>a.field<b.field?-1:a.field>b.field?1:0);
 if(new Set(claims.map(c=>c.field)).size!==claims.length)throw new InvalidInput('DUPLICATE_FIELD');
 if(sources.some(s=>!exact(s,['id','source_url','observed_at','facts'])||!identifier(s.id,'fixture-source-')||typeof s.source_url!=='string'||typeof s.observed_at!=='string'||!validRecord(s.facts)))throw new InvalidInput('INVALID_SOURCE');
 if(new Set(sources.map(s=>s.id)).size!==sources.length)throw new InvalidInput('DUPLICATE_SOURCE');
 if(!plain(crm)||Object.entries(crm).some(([k,v])=>!identifier(k,'synthetic-company-')||!validRecord(v)))throw new InvalidInput('INVALID_CRM');
 const payload={...structuredClone(request),claims};
 const snapshot={sources:structuredClone(sources).sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0),previous_record:structuredClone(crm[request.company_id]??{})};
 const rows=[],issues=[];
 if(request.requested_tool!==context.allowed_tool)issues.push('TOOL_DENIED');
 const byId=new Map(sources.map(s=>[s.id,s]));
 for(const c of claims){
  const source=byId.get(c.source_id);let code='SUPPORTED';
  if(!source)code='MISSING_SOURCE';
  else if(!sourceUrl(source.source_url))code='INVALID_SOURCE_URL';
  else if(!validDate(source.observed_at))code='INVALID_SOURCE_DATE';
  else if(age(context.reference_date,source.observed_at)<0||age(context.reference_date,source.observed_at)>context.max_age_days)code='STALE_EVIDENCE';
  else if(c.value===null||source.facts[c.field]==null)code='UNKNOWN_VALUE';
  else if(source.facts[c.field]!==c.value)code='UNSUPPORTED_CLAIM';
  const relevant=snapshot.sources.filter(s=>Object.hasOwn(s.facts,c.field));
  for(const other of relevant){
   if(code!=='SUPPORTED')break;
   if(!sourceUrl(other.source_url))code='INVALID_SOURCE_URL';
   else if(!validDate(other.observed_at))code='INVALID_SOURCE_DATE';
   else if(age(context.reference_date,other.observed_at)<0||age(context.reference_date,other.observed_at)>context.max_age_days)code='STALE_EVIDENCE';
   else if(other.facts[c.field]===null)code='UNKNOWN_VALUE';
   else if(other.facts[c.field]!==c.value)code='CONFLICTING_EVIDENCE';
  }
  if(code!=='SUPPORTED')issues.push(code);
  rows.push({field:c.field,previous_value:snapshot.previous_record[c.field]??null,proposed_value:c.value,source_id:c.source_id,source_url:source?.source_url??null,observed_at:source?.observed_at??null,source_value:source?.facts[c.field]??null,validation:code,supporting_assertions:relevant});
 }
 const binding={payload,evidence_snapshot:snapshot,validation_context:structuredClone(context)};
 return {synthetic:true,...binding,payload_digest:await digest(payload),evidence_digest:await digest(snapshot),context_digest:await digest(context),approval_digest:await digest(binding),fields:rows,validation:{valid:!issues.length,issues:[...new Set(issues)].sort()},scope:'Apply exactly the proposed fields to this synthetic company once; preserve other fields. No external action.',limitations:[...LIMITS]};
}

export class ReviewSession{
 #request;#sources;#context;#crm;#ledger={};#reviews=new Map();#events=[];#decisions=0;#writes=0;#last={status:'READY',code:'NOT_PREPARED'};#busy=false;
 constructor(request,sources,context=DEFAULT_CONTEXT,crm={}){this.#request=structuredClone(request);this.#sources=structuredClone(sources);this.#context=structuredClone(context);this.#crm=structuredClone(crm);}
 replaceInputs({request,sources,context,crm}={}){
  if(this.#busy)throw new InvalidInput('OPERATION_IN_PROGRESS');
  if(request!==undefined)this.#request=structuredClone(request);
  if(sources!==undefined)this.#sources=structuredClone(sources);
  if(context!==undefined)this.#context=structuredClone(context);
  if(crm!==undefined)this.#crm=structuredClone(crm);
 }
 #event(review_id,status,code){this.#events.push({event_id:`event-${String(this.#events.length+1).padStart(4,'0')}`,review_id,status,code});this.#last={status,code};return this.view();}
 async #package(){return buildPackage(this.#request,this.#sources,this.#context,this.#crm);}
 // WebCrypto is async. Serialize all public transitions and refuse input swaps
 // during a transition to keep this in-tab sequential demonstration coherent.
 async #exclusive(fn){if(this.#busy)throw new InvalidInput('OPERATION_IN_PROGRESS');this.#busy=true;try{return await fn();}finally{this.#busy=false;}}
 async prepare(){return this.#exclusive(async()=>{
  const rid=`review-${String(this.#reviews.size+1).padStart(4,'0')}`;let pack;
  try{pack=await this.#package();}catch(e){if(!(e instanceof InvalidInput))throw e;this.#reviews.set(rid,{review_id:rid,status:'BLOCKED',package:null,decision:null});return this.#event(rid,'BLOCKED',e.message);}
  const previous=this.#ledger[pack.payload.request_id],conflict=previous&&previous.approval_digest!==pack.approval_digest;
  const status=conflict||!pack.validation.valid?'BLOCKED':'AWAITING_APPROVAL';
  this.#reviews.set(rid,{review_id:rid,status,package:pack,decision:null});
  return this.#event(rid,status,conflict?'IDEMPOTENCY_CONFLICT':status==='AWAITING_APPROVAL'?'REVIEW_READY':'EVIDENCE_BLOCKED');
 });}
 #invalidate(review,code){review.status='INVALIDATED';if(review.decision)review.decision.status='INVALIDATED';return this.#event(review.review_id,'INVALIDATED',code);}
 async #matches(review){try{const current=await this.#package();return current.validation.valid&&current.approval_digest===review.package.approval_digest;}catch(e){if(!(e instanceof InvalidInput))throw e;return false;}}
 async decide(review_id,choice,reviewed_digest){return this.#exclusive(async()=>{
  const review=this.#reviews.get(review_id);
  if(!review||review.status!=='AWAITING_APPROVAL'||!['approve','reject'].includes(choice))return this.#event(review_id,'BLOCKED','INVALID_TRANSITION');
  if(reviewed_digest!==review.package.approval_digest||!(await this.#matches(review)))return this.#invalidate(review,'REVIEW_CHANGED');
  const status=choice==='approve'?'APPROVED':'REJECTED';review.status=status;
  review.decision={decision_id:`decision-${String(++this.#decisions).padStart(4,'0')}`,review_id,status,choice,approval_digest:reviewed_digest,actor:'simulated-interactive-reviewer'};
  return this.#event(review_id,status,choice==='approve'?'EXPLICIT_APPROVAL':'EXPLICIT_REJECTION');
 });}
 async execute(review_id){return this.#exclusive(async()=>{
  const review=this.#reviews.get(review_id);
  if(!review||!['APPROVED','APPLIED'].includes(review.status))return this.#event(review_id,'BLOCKED','APPROVAL_REQUIRED');
  const pack=review.package,previous=this.#ledger[pack.payload.request_id];
  if(previous){
   let matches=false;
   try{const current=await this.#package(),original=structuredClone(current);original.evidence_snapshot.previous_record=pack.evidence_snapshot.previous_record;const binding={payload:original.payload,evidence_snapshot:original.evidence_snapshot,validation_context:original.validation_context};matches=current.validation.valid&&(await digest(binding))===pack.approval_digest&&canonical(this.#crm[pack.payload.company_id])===canonical(previous.record);}catch(e){if(!(e instanceof InvalidInput))throw e;}
   if(previous.approval_digest!==pack.approval_digest||!matches)return this.#invalidate(review,'IDEMPOTENCY_CONFLICT');
   return this.#event(review_id,'REPLAYED','ALREADY_APPLIED');
  }
  if(!(await this.#matches(review)))return this.#invalidate(review,'REVIEW_CHANGED');
  const request=pack.payload,record=structuredClone(this.#crm[request.company_id]??{});
  for(const c of request.claims)record[c.field]=c.value;
  this.#crm[request.company_id]=record;
  this.#ledger[request.request_id]={approval_digest:pack.approval_digest,decision_id:review.decision.decision_id,record:structuredClone(record)};
  this.#writes++;review.status='APPLIED';review.decision.status='CONSUMED';return this.#event(review_id,'APPLIED','LOCAL_WRITE_ONLY');
 });}
 view(){return structuredClone({...this.#last,synthetic:true,write_count:this.#writes,local_crm:this.#crm,ledger:this.#ledger,reviews:[...this.#reviews.values()],events:this.#events});}
}
