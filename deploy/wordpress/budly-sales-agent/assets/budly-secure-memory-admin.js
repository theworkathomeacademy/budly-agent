(()=>{'use strict';
const cfg=window.BudlyMemoryAdmin||{},root=document.querySelector('[data-budly-memory-admin]');
if(!root)return;
const message=root.querySelector('[data-admin-message]');
const show=value=>{message.textContent=value};
const renderAudit=items=>{
 const query=String(root.querySelector('[data-audit-conversation]')?.value||'').trim(),list=document.createElement('ol');
 items.filter(item=>!query||item.conversation_id===query).forEach(item=>{
  const row=document.createElement('li'),summary=document.createElement('span'),details=document.createElement('details'),toggle=document.createElement('summary'),metadata=document.createElement('pre');
  summary.textContent=item.created_at+' — '+item.event_type+' — '+item.result+' ('+item.severity+') — conversation: '+(item.conversation_id||'none');
  toggle.textContent='View metadata';
  metadata.textContent=JSON.stringify(item.metadata??{},null,2);
  details.append(toggle,metadata);row.append(summary,details);list.append(row);
 });
 if(!list.children.length){const row=document.createElement('li');row.textContent='No audit events match this conversation ID.';list.append(row)}
 root.querySelector('[data-admin-audit]').replaceChildren(list);
};
const call=async(path,method='GET',body)=>{
 const response=await fetch(String(cfg.restBase).replace(/\/$/,'')+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-WP-Nonce':cfg.nonce},body:body?JSON.stringify(body):undefined});
 const output=await response.json();
 if(!response.ok||!output.success)throw new Error(output?.error?.message||'Request failed');
 return output.data;
};
const load=async()=>{try{
 const health=await call('/admin/health'),box=root.querySelector('[data-admin-status]');
 box.textContent='Status: '+health.status+' | Schema: '+health.schema_version+' | Active sessions: '+health.metrics.active_sessions+' | Active memory: '+health.metrics.active_memory;
 const audit=await call('/admin/audit?per_page=100');
 root.auditItems=audit.items;renderAudit(root.auditItems);
 const memory=await call('/admin/commercial-memory?per_page=25'),memoryList=document.createElement('ol');
 memory.items.forEach(item=>{const row=document.createElement('li');row.textContent=item.memory_uuid+' — '+item.memory_type+' — confidence '+item.confidence+' — '+item.status;memoryList.append(row)});
 root.querySelector('[data-admin-commercial-memory]').replaceChildren(memoryList);
}catch(error){show(error.message)}};
root.addEventListener('submit',async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.target));try{
 if(event.target.matches('[data-audit-filter]')){renderAudit(root.auditItems||[]);show('Audit view filtered locally by conversation ID.');return;}
 if(event.target.matches('[data-revoke-session]'))await call('/admin/revoke-session','POST',data);
 if(event.target.matches('[data-revoke-all]'))await call('/admin/revoke-all','POST',data);
 if(event.target.matches('[data-test-email]'))await call('/admin/test-email','POST',data);
 if(event.target.matches('[data-run-cleanup]'))await call('/admin/run-cleanup','POST',{});
 if(event.target.matches('[data-memory-search]')){const query=new URLSearchParams(Object.entries(data).filter(([,value])=>value));const result=await call('/admin/commercial-memory?'+query),list=document.createElement('ol');result.items.forEach(item=>{const row=document.createElement('li');row.textContent=item.memory_uuid+' — '+item.memory_type+' — confidence '+item.confidence+' — '+item.status;list.append(row)});root.querySelector('[data-admin-commercial-memory]').replaceChildren(list);show('Commercial-memory search completed and audited.');return;}
 if(event.target.matches('[data-memory-action]')){const uuid=encodeURIComponent(data.memory_uuid),action=data.action;delete data.memory_uuid;delete data.action;if(action==='invalidate')await call('/admin/commercial-memory/'+uuid+'/invalidate','POST',data);if(action==='delete')await call('/admin/commercial-memory/'+uuid,'DELETE',data);if(action==='export'){const result=await call('/admin/commercial-memory/'+uuid+'/export','POST',data);const blob=new Blob([JSON.stringify(result,null,2)],{type:'application/json'}),link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='budly-commercial-memory-export.json';link.click();URL.revokeObjectURL(link.href);}}
 if(event.target.matches('[data-memory-correct]')){const uuid=encodeURIComponent(data.memory_uuid);delete data.memory_uuid;data.confidence=Number(data.confidence);await call('/admin/commercial-memory/'+uuid+'/correct','POST',data);}
 show('Administrative action completed and audited.');await load();
}catch(error){show(error.message)}});
load();
})();
