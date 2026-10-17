import data from './fixtures.json' with {type:'json'};
export const SCENARIOS={approval_required:'Approval required',approved:'Approved local write',missing_source:'Missing source',unsupported_claim:'Unsupported claim',forbidden_tool:'Out-of-scope tool',stale_evidence:'Stale evidence',retry_success:'Transient failure, then recovery',retry_exhausted:'Retry limit reached',replay:'Idempotent replay',approval_mismatch:'Approval does not match payload',conflict:'Request ID reused with changed payload'};
const allowed={researcher:['evidence.lookup'],verifier:['evidence.validate'],operator:['crm.apply_local']};
function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
export async function digest(v){const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(v)));return [...new Uint8Array(hash)].map(b=>b.toString(16).padStart(2,'0')).join('');}
export async function workflow(request,sources,{approval=null,ledger={},crm={},transient_failures=0,max_attempts=2}={}){
 const trace=[],fingerprint=await digest(request),result={status:'REQUESTED',code:'',trace,payload_digest:fingerprint,request,reference_date:'2026-10-17',write_count:0,evidence:sources,synthetic:true};
 const step=(role,event,detail)=>trace.push({role,event,detail});
 const stop=(status,code,detail)=>{result.status=status;result.code=code;step('controller',status,detail);result.local_crm=structuredClone(crm);result.ledger_entries=Object.keys(ledger).length;return result;};
 step('controller','REQUESTED','Fixed synthetic request received; no external action.');
 if(!allowed.operator.includes(request.requested_tool))return stop('BLOCKED','TOOL_DENIED','Requested tool is outside the operator allowlist.');
 step('controller','SCOPED','Only evidence lookup, validation and a local fixture write are allowed.');
 if(max_attempts<1||max_attempts>3)return stop('BLOCKED','INVALID_RETRY_POLICY','Retry budget must be between 1 and 3.');
 let found=false;for(let attempt=1;attempt<=max_attempts;attempt++){step('researcher','LOOKUP_ATTEMPT',`Synthetic lookup attempt ${attempt}/${max_attempts}.`);if(attempt>transient_failures){found=true;break;}}
 if(!found)return stop('BLOCKED','RETRY_EXHAUSTED','No write: evidence lookup exhausted its retry budget.');
 step('researcher','COLLECTED','Loaded local fixture records; no websites were fetched.');
 for(const claim of request.claims){const source=sources.find(s=>s.id===claim.source_id);if(!source||!source.source_url?.startsWith('https://'))return stop('BLOCKED','SOURCE_MISSING','A claim has no usable fixture source reference.');
 const time=Date.parse(source.observed_at+'T00:00:00Z');if(!Number.isFinite(time)||new Date(time).toISOString().slice(0,10)!==source.observed_at)return stop('BLOCKED','INVALID_SOURCE_DATE','The fixture source date is invalid.');
 const age=(Date.parse('2026-10-17T00:00:00Z')-time)/86400000;if(age<0||age>30)return stop('BLOCKED','STALE_EVIDENCE','Evidence is outside the 30-day demo freshness window.');
 if(source.facts[claim.field]!==claim.value)return stop('BLOCKED','UNSUPPORTED_CLAIM','Claim does not match its cited fixture field.');}
 step('verifier','VALIDATED','References, field values and fixture dates match. This is consistency, not real-world truth validation.');
 if(!approval)return stop('AWAITING_APPROVAL','APPROVAL_REQUIRED','Validation passed; the local fixture write remains blocked.');
 if(approval.payload_digest!==fingerprint||!approval.actor)return stop('BLOCKED','APPROVAL_MISMATCH','Approval is not bound to this exact payload.');
 step('controller','APPROVED','Local demo approval matches the payload digest; no identity authentication is performed.');
 if(Object.hasOwn(ledger,request.request_id)){if(ledger[request.request_id].digest!==fingerprint)return stop('BLOCKED','IDEMPOTENCY_CONFLICT','This request ID already belongs to a different payload.');return stop('REPLAYED','ALREADY_APPLIED','The same request was already applied; no second write.');}
 const record=Object.fromEntries(request.claims.map(c=>[c.field,c.value]));crm[request.company_id]=record;ledger[request.request_id]={digest:fingerprint,record};result.write_count=1;
 step('operator','APPLIED','One write to an in-memory synthetic CRM record. No external CRM was contacted.');return stop('APPLIED','LOCAL_WRITE_ONLY','Completed within the local demo boundary.');
}
export async function runScenario(name){
 if(!Object.hasOwn(SCENARIOS,name))throw new Error('Unknown scenario');
 let{request,sources}=structuredClone(data);const ledger={},crm={},options={};
 if(name==='missing_source')sources[0].source_url='';if(name==='unsupported_claim')request.claims[1].value=999;if(name==='forbidden_tool')request.requested_tool='email.send';if(name==='stale_evidence')sources[0].observed_at='2020-01-01';if(name==='retry_success'||name==='retry_exhausted')options.transient_failures=name==='retry_success'?1:3;
 let approval=name==='approval_required'?null:{actor:'synthetic-demo-reviewer',payload_digest:await digest(request)};
 if(name==='approval_mismatch')approval.payload_digest='does-not-match';
 let first=null;if(name==='replay'||name==='conflict'){first=await workflow(request,sources,{approval,ledger,crm});if(name==='conflict'){request=structuredClone(request);request.company_id='synthetic-company-002';approval={actor:'synthetic-demo-reviewer',payload_digest:await digest(request)};}}
 const result=await workflow(request,sources,{approval,ledger,crm,...options});result.scenario=name;result.title=SCENARIOS[name];result.total_writes=(first?.write_count||0)+result.write_count;if(first)result.previous_run={status:first.status,write_count:first.write_count};return result;
}
