(()=>{'use strict';
const cfg=window.BudlyEntryConfig||{};
document.querySelectorAll('[data-budly-entry]').forEach(link=>link.addEventListener('click',()=>{
 const session=(globalThis.crypto?.randomUUID?.()||String(Date.now())+'-'+Math.random().toString(16).slice(2));
 const body=new URLSearchParams({action:'budly_sales_track',nonce:cfg.nonce||'',event:'budly_button_clicked',session,metadata:location.pathname});
 fetch(cfg.ajaxUrl,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body,keepalive:true}).catch(()=>{});
}));
})();
