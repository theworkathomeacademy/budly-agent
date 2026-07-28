(()=>{'use strict';
const cfg=window.BudlyMemoryAdmin||{},root=document.querySelector('[data-budly-memory-admin]');
if(!root)return;
const message=root.querySelector('[data-admin-message]');
const show=value=>{message.textContent=value};
const call=async(path,method='GET',body)=>{
 const response=await fetch(String(cfg.restBase).replace(/\/$/,'')+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-WP-Nonce':cfg.nonce},body:body?JSON.stringify(body):undefined});
 const output=await response.json();
 if(!response.ok||!output.success)throw new Error(output?.error?.message||'Request failed');
 return output.data;
};
const load=async()=>{try{
 const health=await call('/admin/health'),box=root.querySelector('[data-admin-status]');
 box.textContent='Status: '+health.status+' | Schema: '+health.schema_version+' | Active sessions: '+health.metrics.active_sessions+' | Active memory: '+health.metrics.active_memory;
 const audit=await call('/admin/audit?per_page=25'),list=document.createElement('ol');
 audit.items.forEach(item=>{const row=document.createElement('li');row.textContent=item.created_at+' — '+item.event_type+' — '+item.result+' ('+item.severity+')';list.append(row)});
 root.querySelector('[data-admin-audit]').replaceChildren(list);
}catch(error){show(error.message)}};
root.addEventListener('submit',async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.target));try{
 if(event.target.matches('[data-revoke-session]'))await call('/admin/revoke-session','POST',data);
 if(event.target.matches('[data-revoke-all]'))await call('/admin/revoke-all','POST',data);
 if(event.target.matches('[data-test-email]'))await call('/admin/test-email','POST',data);
 if(event.target.matches('[data-run-cleanup]'))await call('/admin/run-cleanup','POST',{});
 show('Administrative action completed and audited.');await load();
}catch(error){show(error.message)}});
load();
})();
