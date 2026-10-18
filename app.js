// Shared UI for both adapters. No auto-approval, automatic execution or HTML injection.
export async function mount(adapter){
 const el=id=>document.getElementById(id);
 let view=null,busy=false,reviewedDigest=null;
 const latest=()=>view?.reviews.at(-1);
 function controls(){
  const review=latest(),waiting=review?.status==='AWAITING_APPROVAL';
  for(const id of ['reset','prepare','run-legacy','fixture','scenario'])el(id).disabled=busy;
  el('reviewed').disabled=busy||!waiting;
  el('approve').disabled=busy||!waiting||reviewedDigest!==review?.package?.approval_digest;
  el('reject').disabled=busy||!waiting;
  el('execute').disabled=busy||!['APPROVED','APPLIED'].includes(review?.status);
  el('change-source').disabled=busy||!review?.package?.evidence_snapshot.sources.length;
 }
 function text(tag,value,cls){const node=document.createElement(tag);node.textContent=value;if(cls)node.className=cls;return node;}
 const showValue=v=>v===null?'Unknown / no prior value':JSON.stringify(v);
 function render(){
  el('status').textContent=view.status;
  el('status').className='status '+(['BLOCKED','INVALIDATED','REJECTED'].includes(view.status)?'bad':['APPLIED','APPROVED','REPLAYED'].includes(view.status)?'ok':'warn');
  el('writes').textContent=view.write_count;el('crm').textContent=JSON.stringify(view.local_crm,null,2);el('raw').textContent=JSON.stringify(view,null,2);
  const notes={NOT_PREPARED:'Prepare a package to inspect the proposed change. No write has occurred.',REVIEW_READY:'Review the exact field changes and sources below. No approval and no write yet.',EXPLICIT_APPROVAL:'Approval recorded for this package. No write yet: execute explicitly to recheck and apply.',EXPLICIT_REJECTION:'Rejected. This review cannot be approved later; no write occurred.',LOCAL_WRITE_ONLY:'Exactly one in-memory synthetic change was applied.',ALREADY_APPLIED:'The approved request was already applied; no second write occurred.',REVIEW_CHANGED:'Blocked: current inputs differ from the reviewed snapshot or are no longer valid. Prepare a new package and make a new decision.',EVIDENCE_BLOCKED:'Not approvable: at least one field has missing, unknown, invalid, stale or contradictory evidence.',IDEMPOTENCY_CONFLICT:'Blocked: this request ID is bound to a different snapshot, or the replay inputs changed.',APPROVAL_REQUIRED:'Blocked: this review has no executable approval.',INVALID_TRANSITION:'Blocked: this review does not allow that decision or transition.'};
  el('result-note').textContent=notes[view.code]??`Blocked: ${view.code}`;
  el('events').replaceChildren(...view.events.map(e=>text('li',`${e.event_id} · ${e.review_id} · ${e.status} · ${e.code}`)));
  el('history').textContent=JSON.stringify(view.reviews.slice(0,-1),null,2);
  const review=latest(),pack=review?.package;el('package').hidden=!pack;
  if(pack){
   const company=pack.payload.claims.find(c=>c.field==='company_name')?.value??'Synthetic company';
   el('company').textContent=`${company} · ${pack.payload.company_id}`;
   el('request-id').textContent=`${pack.payload.request_id} / ${review.review_id}`;
   el('action').textContent=pack.payload.requested_tool;
   el('fields').replaceChildren(...pack.fields.map(row=>{
    const card=text('article','', 'field');card.append(text('h4',row.field));
    card.append(text('div',`${showValue(row.previous_value)} → ${showValue(row.proposed_value)}`,'change'));
    card.append(text('p',`Cited source: ${row.source_id} | source value: ${showValue(row.source_value)}`));
    card.append(text('p',`URL label (not fetched): ${row.source_url??'Missing'}`));
    card.append(text('p',`Observed: ${row.observed_at??'Missing'} | validation: ${row.validation}`,row.validation==='SUPPORTED'?'':'issue'));
    for(const assertion of row.supporting_assertions)card.append(text('p',`Supplied assertion ${assertion.id}: ${showValue(assertion.facts[row.field])} | ${assertion.observed_at} | ${assertion.source_url}`));
    return card;
   }));
   el('validation').textContent=pack.validation.valid?'SUPPORTED: every proposed field matches usable, current fixture evidence. No conflicting supplied assertion. These are consistency checks only.':`NOT APPROVABLE: ${pack.validation.issues.join(', ')}. No write is permitted.`;
   el('limitations').replaceChildren(...pack.limitations.map(s=>text('li',s)));
   el('scope').textContent=pack.scope;
   const c=pack.validation_context;el('context').textContent=`Policy ${c.policy_version} · reference date ${c.reference_date} · freshness ${c.max_age_days} days · only ${c.allowed_tool}`;
   el('digests').replaceChildren();
   for(const name of ['payload_digest','evidence_digest','context_digest','approval_digest'])el('digests').append(text('dt',name),text('dd',pack[name]));
   el('raw-package').textContent=JSON.stringify(pack,null,2);
   el('receipt').textContent=review.decision?`${review.decision.decision_id} · ${review.decision.status} · ${review.decision.actor} · bound to ${review.decision.approval_digest}`:'No decision recorded for this review.';
  }
  controls();
 }
 async function perform(fn,{newPackage=false}={}){
  if(busy)return;busy=true;el('error').textContent='';controls();
  try{view=await fn();if(newPackage){reviewedDigest=null;el('reviewed').checked=false;}render();}
  catch(error){el('error').textContent=error.message;}
  finally{busy=false;controls();}
 }
 async function reset(){el('change-note').textContent='After preparing or approving, change a source date to test invalidation. The reviewed package below stays unchanged.';await perform(()=>adapter.reset(el('fixture').value),{newPackage:true});}
 el('runtime').textContent=adapter.label;
 el('reset').addEventListener('click',reset);
 el('prepare').addEventListener('click',()=>perform(()=>adapter.command('prepare'),{newPackage:true}));
 el('reviewed').addEventListener('change',()=>{reviewedDigest=el('reviewed').checked?latest()?.package?.approval_digest:null;controls();});
 el('approve').addEventListener('click',()=>{if(reviewedDigest===latest()?.package?.approval_digest&&el('reviewed').checked)perform(()=>adapter.command('approve',{review_id:latest().review_id,reviewed_digest:reviewedDigest}));});
 el('reject').addEventListener('click',()=>perform(()=>adapter.command('reject',{review_id:latest().review_id,reviewed_digest:latest().package.approval_digest})));
 el('execute').addEventListener('click',()=>perform(()=>adapter.command('execute',{review_id:latest().review_id})));
 el('change-source').addEventListener('click',()=>perform(async()=>{const v=await adapter.command('change_source');el('change-note').textContent='Live fixture date changed. The displayed review package is retained unchanged. Approve or Execute will recheck; prepare again for a fresh review.';return v;}));
 el('run-legacy').addEventListener('click',async()=>{if(busy)return;busy=true;controls();el('error').textContent='';try{el('legacy-result').textContent=JSON.stringify(await adapter.legacy(el('scenario').value),null,2);}catch(e){el('error').textContent=e.message;}finally{busy=false;controls();}});
 await reset();
}
