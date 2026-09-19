(()=>{'use strict';
const cfg=window.BudlySalesConfig||{};
const journeys={
 wellness:{label:'Consumer wellness',signals:['cbd','wellness','tincture','body butter','topical','combo','product','budget','compare'],cats:['CBD','Selfcare'],questions:['Are you comparing a topical, oil, or bundle?','Do you prefer a one-time purchase or monthly delivery?','What budget feels comfortable?']},
 culinary:{label:'Culinary',signals:['cooking oil','culinary','cook','infused oil'],cats:['Culinary'],questions:['Are you looking for a cooking ingredient or educational guide?','What package size or budget fits?','Are you new to infused cooking?']},
 education:{label:'Books and courses',signals:['book','guide','learn','course','class','grow','botanical'],cats:['Education'],questions:['Do you want self-paced reading, botanical art, or a class?','Is your focus culinary, cultivation, or both?','Do you prefer full payment or a listed payment plan?']},
 membership:{label:'NFT memberships',signals:['nft','membership','bronze','copper','titanium','platinum'],cats:['Membership'],questions:['Which character interests you?','Which membership tier are you considering?','Would you like the current price range before choosing?']},
 wholesale:{label:'Wholesale',signals:['wholesale','bulk','white label','resell','business'],cats:['bulk'],questions:['Which website product or custom request interests you?','What quantity do you need?','What destination and timeline apply?']}
};
const allowed=new Set(['wakenbake-lounge-cannabis-botanical-collection-volume-1','infused-basics','therapeutic-oil-tincture-monthly','therapeutic-oil-tincture-1-time','therapeutic-body-butter-monthly','therapeutic-body-butter','therapeutic-combo-monthly-subscription','therapeutic-combo-one-time-purchase','white-label-oil-per-1oz-min-10oz','white-label-cbd-combo-per-1oz','white-label-butter-per-1oz-min-16oz','bulk-butter','infused-cooking-oil-4oz','infused-cooking-oil-8oz','infused-cooking-oil-12oz','infused-cooking-oil-16oz','culinary-cannabis-payment-plan','grow-cannabis-home-payment-plan','cook-grow-with-me-payment-plan','culinary-cannabis','grow-cannabis-home','cook-grow-with-me','azurea-skye','cookie-cutter','dizel','the-monarch','the-original-guardian','the-godfather-og-nft-membership','the-godfather-og','the-don','bruce-banner-3-nft-membership','bruce-banner-3','gamma-blaze','strawberry-banana-nft-membership','strawberry-banana','berry-bliss','torque-nft-membership','torque','875','the-chemist-nft-membership','the-chemist']);
const safeSummary={wellness:'A CBD self-care option. Compare format, price, and purchase cadence without relying on medical claims.',culinary:'A CBD culinary option. Review size, package facts, and current price; Budly does not recommend dosage.',education:'An educational product about the stated topic. No certification or outcome is guaranteed.',membership:'A tiered digital membership collectible. Review the current membership terms before purchase.',wholesale:'A website-listed bulk product. Requests outside the available website options may require support.'};
const starters=[['Help me choose a product','Help me choose the right product'],['Shop within my budget','Help me shop within my budget'],['Compare products','Help me compare products'],['Membership questions','I have questions about NFT membership terms and refunds'],['Wholesale inquiries','I have a wholesale inquiry'],['Order, shipping, or human support','I need order, shipping, or human support']];
const riskTerms=['diagnose','treat my','treat it','treatment','cure','cancer','dosage','dose','replace my medication','bad reaction','made me sick','hospital','is it legal','under 18','under 21','chargeback','unauthorized charge'];
document.querySelectorAll('[data-budly-sales]').forEach(root=>{
 const messages=root.querySelector('[data-budly-messages]'),form=root.querySelector('[data-budly-form]'),fields=root.querySelector('[data-budly-fields]'),send=root.querySelector('[data-budly-send]'),restart=root.querySelector('[data-budly-restart]');
 const conversationId=()=>('conv_'+(globalThis.crypto?.randomUUID?.().replaceAll('-','')||Date.now().toString(36)+Math.random().toString(36).slice(2))).slice(0,45);
 const urlParams=new URLSearchParams(window.location.search);
 const sanitizeParam=(val,maxLen=120)=>{if(!val||typeof val!=='string')return'';return val.trim().slice(0,maxLen).replace(/[^a-zA-Z0-9_\-\.:\/]/g,'')};
 const initialAttribution={
  source:sanitizeParam(urlParams.get('source'),64),
  platform:sanitizeParam(urlParams.get('platform'),64),
  content_id:sanitizeParam(urlParams.get('content_id'),100),
  campaign_id:sanitizeParam(urlParams.get('campaign_id'),100),
  cta_id:sanitizeParam(urlParams.get('cta_id'),64),
  product_or_topic:sanitizeParam(urlParams.get('product_or_topic'),100),
  published_post_id:sanitizeParam(urlParams.get('published_post_id'),100)
 };
 const hasAttribution=Boolean(initialAttribution.source||initialAttribution.content_id||initialAttribution.cta_id||initialAttribution.product_or_topic);
 let state={step:'identity',name:'',email:'',phone:'',memoryConsent:false,verified:false,decisionCsrf:'',goal:'',preselectedGoal:'',journey:null,answers:[],q:0,session:conversationId(),attribution:initialAttribution};
 const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
 const cleanText=s=>{if(!s)return'';let t=String(s).replace(/&#8217;/g,"'").replace(/&#8211;/g,'–').replace(/&#8230;/g,'…').replace(/&#39;/g,"'").replace(/&quot;/g,'"').replace(/\[([^\]]+)\]\([^)]+\)/g,'$1');let h=esc(t);h=h.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');h=h.replace(/\n/g,'<br>');return h};
 const bubble=(text,who='bot',label='')=>{const e=document.createElement('div');e.className='budly-message budly-'+who;e.innerHTML=(label?'<div class="budly-label">'+esc(label)+'</div>':'')+cleanText(text);messages.append(e);messages.scrollTop=messages.scrollHeight};
 const input=(html,label='Continue')=>{fields.innerHTML=html;send.hidden=false;send.textContent=label;fields.querySelector('input,select')?.focus()};
 const approvedLinkHosts=new Set(['cccultivate.com','wakenbakelounge.com','www.wakenbakelounge.com','dmckenzies.wixsite.com','learn.cccultivate.com']);
 const link=(url,label)=>{let parsed;try{parsed=new URL(url,window.location.href)}catch(e){return}if(parsed.protocol!=='https:'||!approvedLinkHosts.has(parsed.hostname))return;const card=document.createElement('div'),anchor=document.createElement('a');card.className='budly-card';anchor.href=parsed.href;anchor.target='_blank';anchor.rel='noopener noreferrer';anchor.textContent=String(label||'Learn more')+' ↗';card.append(anchor);messages.append(card);messages.scrollTop=messages.scrollHeight};
 const renderApprovedLinks=links=>Array.isArray(links)&&links.slice(0,3).forEach(item=>item&&link(item.url,item.label));
 const track=(event,extra={})=>{
  const metaObject=Object.assign({},extra.metadata&&typeof extra.metadata==='object'?extra.metadata:(extra.metadata?{raw:extra.metadata}:{}),hasAttribution?{attribution:state.attribution}:{});
  const body=new URLSearchParams({
   action:'budly_sales_track',
   nonce:cfg.trackNonce||'',
   event,
   session:state.session,
   name:state.name,
   email:state.email,
   phone:state.phone,
   memory_consent:state.memoryConsent?'1':'',
   journey:state.journey?.label||'',
   metadata:Object.keys(metaObject).length?JSON.stringify(metaObject):'',
   source:state.attribution.source||'',
   platform:state.attribution.platform||'',
   content_id:state.attribution.content_id||'',
   campaign_id:state.attribution.campaign_id||'',
   cta_id:state.attribution.cta_id||'',
   product_or_topic:state.attribution.product_or_topic||'',
   ...extra
  });
  fetch(cfg.ajaxUrl,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body,keepalive:true}).catch(()=>{});
 };
  const conversationSummary=()=>[state.goal,...state.answers].filter(Boolean).join(' | ');
  const complete=(summary=conversationSummary())=>track('conversation_completed',{summary});
  const start=()=>{
    state={step:'conversational',name:'',email:'',phone:'',memoryConsent:false,verified:false,decisionCsrf:'',goal:'',preselectedGoal:'',journey:null,answers:[],q:0,session:conversationId(),attribution:initialAttribution};
    messages.innerHTML='';
    restart.hidden=true;
    bubble('Hi, I’m Budly! 👋 I’m here to help you understand your options before choosing a product, course, membership, or support path. What would you like help with today?');
    input('<input name="answer" aria-label="Ask Budly anything" placeholder="Ask Budly anything…" required><button type="button" class="budly-secondary" data-budly-returning>Returning customer? Verify your email</button>','Send');
  };
  const recallRequest=async email=>{const body=new URLSearchParams({action:'budly_sales_request_recall',nonce:cfg.recallNonce||'',email});const r=await fetch(cfg.ajaxUrl,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const out=await r.json();if(!out.success)throw new Error(out.data?.message||'Unable to send a code.');return out.data};
  const recallVerify=async(email,code)=>{const body=new URLSearchParams({action:'budly_sales_verify_recall',nonce:cfg.recallNonce||'',email,code});const r=await fetch(cfg.ajaxUrl,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const out=await r.json();if(!out.success)throw new Error(out.data?.message||'Unable to verify that code.');return out.data};
  const showRecallHistory=history=>{if(!history?.length){bubble('I do not have a previous conversation summary to show, but your saved profile is ready.','bot','Verified profile');return}bubble('Here are the latest conversation notes you asked me to remember:','bot','Your Budly history');history.forEach(item=>bubble((item.journey?item.journey+': ':'')+item.summary,'bot',item.created_at||'Previous conversation'))};
  const goalInput=()=>input('<div class="budly-starters" aria-label="Popular questions">'+starters.map(([label,value])=>'<button type="button" data-budly-starter="'+esc(value)+'">'+esc(label)+'</button>').join('')+'</div><input name="answer" aria-label="Tell me what you’re looking for" placeholder="Tell me what you’re looking for" required>');
  const route=goal=>Object.entries(journeys).map(([id,j])=>[id,j,j.signals.filter(x=>goal.toLowerCase().includes(x)).length]).sort((a,b)=>b[2]-a[2])[0];
  const hasRisk=text=>riskTerms.some(x=>String(text).toLowerCase().includes(x));
  const membershipPolicyRequested=text=>['refund','cancel','cancellation','begin','start','discount','terms','policy'].some(x=>String(text).toLowerCase().includes(x));
  const explainMembershipPolicy=()=>{bubble('Membership begins as soon as the transaction finishes processing. You may cancel within 7 days for a full refund only if the membership has not been used. Using a membership discount counts as use and disqualifies the purchase from a refund. Cancel through your account profile; if that is unavailable, email '+cfg.supportEmail+'.','bot','Membership terms');link(cfg.policiesUrl,'Read all customer policies')};
  const ask=()=>{if(state.q<state.journey.questions.length){bubble(state.journey.questions[state.q],'bot',state.journey.label);input('<input name="answer" aria-label="Your answer" placeholder="Your answer" required>');return}state.step='finish';bubble('Thanks. I’m checking the current public catalog now.');finish()};
  const loadProducts=async()=>{try{const r=await fetch(cfg.storeApiUrl,{credentials:'same-origin'});if(!r.ok)throw 0;return(await r.json()).filter(p=>allowed.has(p.slug))}catch(e){return[]}};
  const money=p=>{const d=Number(p.prices?.currency_minor_unit??2),lo=Number(p.prices?.price??0)/10**d,min=Number(p.prices?.price_range?.min_amount??p.prices?.price??0)/10**d,max=Number(p.prices?.price_range?.max_amount??p.prices?.price??0)/10**d;return max&&max!==min?'$'+min.toFixed(2)+'–$'+max.toFixed(2):'$'+lo.toFixed(2)};
  const recommend=products=>{const request=(state.goal+' '+state.answers.join(' ')).toLowerCase(),words=request.match(/[a-z0-9]+/g)||[],numbers=request.match(/\$?\d+(?:\.\d+)?/g)?.map(x=>Number(x.replace('$','')))||[],budget=numbers.length>=2?{min:Math.min(...numbers.slice(-2)),max:Math.max(...numbers.slice(-2))}:null,price=p=>Number(p.prices?.price??0)/10**Number(p.prices?.currency_minor_unit??2);let scored=products.map(p=>{const cats=(p.categories||[]).map(c=>c.name);if(!state.journey.cats.some(c=>cats.includes(c)))return[-1,p];if(state.journey===journeys.culinary&&cats.includes('Education'))return[-1,p];if(state.journey!==journeys.wholesale&&cats.includes('bulk'))return[-1,p];const hay=(p.name+' '+cats.join(' ')).toLowerCase(),within=!budget||(price(p)>=budget.min&&price(p)<=budget.max);let score=words.filter(w=>w.length>2&&hay.includes(w)).length;if(request.includes('one-time')&&(hay.includes('one-time')||hay.includes('1-time')))score+=4;if(request.includes('monthly')&&hay.includes('monthly'))score+=4;if(budget&&within)score+=8;return[score,p,within]}).filter(x=>x[0]>=0);if(budget&&scored.some(x=>x[2]))scored=scored.filter(x=>x[2]);scored.sort((a,b)=>b[0]-a[0]||price(a[1])-price(b[1]));return scored[0]?.[1]||null};
  const card=p=>{const e=document.createElement('article');e.className='budly-card';e.innerHTML='<div class="budly-label">Closest current match</div><h3>'+esc(p.name.replace(/&#8217;/g,"'").replace(/&#8211;/g,'–'))+'</h3><div class="budly-price">'+esc(money(p))+'</div><p>'+esc(safeSummary[Object.keys(journeys).find(k=>journeys[k]===state.journey)])+'</p><a href="'+esc(p.permalink)+'">View product ↗</a>';messages.append(e);messages.scrollTop=messages.scrollHeight;track('recommendation_shown',{product_url:p.permalink});e.querySelector('a').addEventListener('click',()=>track('product_clicked',{product_url:p.permalink}))};
  const handoff=async()=>{const summary=[state.goal,...state.answers].join(' | '),body=new URLSearchParams({action:'budly_sales_handoff',nonce:cfg.nonce,name:state.name||'Website visitor',email:state.email||cfg.supportEmail,journey:state.journey?.label||'Support',summary});try{const r=await fetch(cfg.ajaxUrl,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const out=await r.json();if(out.success){bubble(out.data.message+' Reference: '+out.data.reference,'bot','Human support');if(!out.data.sent)link('mailto:'+cfg.supportEmail,'Email '+cfg.supportEmail)}else throw new Error(out.data?.message)}catch(e){bubble('I could not send the handoff automatically. Please email '+cfg.supportEmail+'.','bot','Human support');link('mailto:'+cfg.supportEmail,'Email '+cfg.supportEmail)}};
  const offerHumanHelp=()=>{input('<button type="button" data-human-help>Request human support</button>','');send.hidden=true;fields.querySelector('[data-human-help]').addEventListener('click',()=>{track('human_support_requested');handoff()})};
  const governedDecision=async()=>{
   const journey=Object.keys(journeys).find(k=>journeys[k]===state.journey)||'wellness',
         headers={'Content-Type':'application/json','X-WP-Nonce':cfg.decisionNonce,'Idempotency-Key':'idem_'+state.session};
   if(state.decisionCsrf)headers['X-Budly-CSRF']=state.decisionCsrf;
   const payload={
    conversation_id:state.session,
    journey,
    objective:state.goal,
    answers:state.answers,
    use_memory:state.memoryConsent
   };
   if(hasAttribution)payload.attribution=state.attribution;
   const r=await fetch(cfg.decisionUrl,{method:'POST',credentials:'same-origin',headers,body:JSON.stringify(payload)});
   const out=await r.json();
   if(!r.ok||!out.success)throw new Error(out?.error?.message||'Budly could not record this decision.');
   return out.data;
  };
  const activateLegacy=(msg)=>{
   bubble(msg||'I’m switching to the guided experience so we can keep going without interruption.','bot','Guided mode');
   state.conversationalActive=false;
   if(state.goal){
    const [,j]=route(state.goal);
    state.journey=j;
    state.step='questions';
    bubble('I’ll use the '+j.label+' path so the next questions stay relevant.','bot',j.label);
    ask();
   }else{
    state.step='goal';
    goalInput();
   }
  };
  const conversationalTurn=async(message)=>{
   const headers={'Content-Type':'application/json','X-WP-Nonce':cfg.conversationNonce||''};
   const r=await fetch(cfg.conversationUrl,{
    method:'POST',
    credentials:'same-origin',
    headers,
    body:JSON.stringify({conversation_id:state.session,message})
   });
   const out=await r.json();
   if(!r.ok||!out.success)throw new Error(out?.error?.message||'The conversational runtime is temporarily unavailable.');
   return out.data;
  };
  const finish=async()=>{send.hidden=true;fields.innerHTML='';const decision=await governedDecision(),products=await loadProducts(),p=products.find(x=>x.slug===decision.selected_product_id);if(decision.outcome==='human_review'){bubble('I cannot safely complete that request with an automated product recommendation. A qualified person can help.','bot','Human review');offerHumanHelp()}else if(decision.outcome==='recommended'&&p){bubble('Based on what you shared, this is the closest approved match in the current catalog.','bot',state.journey.label);card(p)}else if(decision.outcome==='clarification_required'||decision.outcome==='nurture'){bubble('I need a little more detail before making a confident match, so I will not guess.','bot','More information needed');offerHumanHelp()}else if(decision.outcome==='consent_restricted'){bubble('I continued without remembered information because the required consent was not active.','bot','Privacy protected');offerHumanHelp()}else{bubble('I do not have a confident approved catalog match, so I will not guess.','bot');offerHumanHelp()}complete();state.step='done'};
  form.addEventListener('click',e=>{
    const returning=e.target.closest('[data-budly-returning]');
    if(returning){
      root.dataset.budlyConversationId=state.session;
      window.BudlySecureMemory.open(root,profile=>{
        state.name=profile?.preferred_name||'there';
        state.verified=true;
        state.memoryConsent=Boolean(profile?.memoryApproved);
        state.decisionCsrf=profile?.budlyCsrf||'';
        track('identity_verified');
        state.step='conversational';
        bubble('Welcome back, '+(profile?.preferred_name||'there')+'! What can I help you with today?','bot');
        input('<input name="answer" aria-label="Ask Budly anything" placeholder="Ask Budly anything…" required><button type="button" class="budly-secondary" data-budly-returning>Returning customer? Verify your email</button>','Send');
      });
      return;
    }
    const starter=e.target.closest('[data-budly-starter]');
    if(!starter)return;
    track('starter_selected',{metadata:starter.textContent.trim()});
    const field=fields.querySelector('input[name="answer"]');
    if(field){
      field.value=starter.dataset.budlyStarter;
      form.requestSubmit();
    }
  });
  form.addEventListener('submit',async e=>{
    e.preventDefault();const d=Object.fromEntries(new FormData(form));send.disabled=true;
    try{
      if(state.step==='recall-email'){state.email=d.recall_email;const result=await recallRequest(state.email);bubble(result.message,'bot','Check your email');state.step='recall-code';input('<input name="recall_code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" placeholder="Six-digit code" required>','Verify and recall');restart.hidden=false}
      else if(state.step==='recall-code'){const result=await recallVerify(state.email,d.recall_code);state.name=result.profile.name||'there';state.email=result.profile.email;state.phone=result.profile.phone||'';state.memoryConsent=true;state.verified=true;track('identity_verified');if(result.history?.length)track('history_recalled',{metadata:String(result.history.length)});bubble(result.message,'bot','Email verified');showRecallHistory(result.history);state.step='conversational';bubble('What can I help you with today?');input('<input name="answer" aria-label="Ask Budly anything" placeholder="Ask Budly anything…" required><button type="button" class="budly-secondary" data-budly-returning>Returning customer? Verify your email</button>','Send')}
      else if(state.step==='conversational'||state.step==='goal'){
        const userMessage=d.answer;
        if(!userMessage||!userMessage.trim())return;
        state.goal=userMessage;
        bubble(userMessage,'user');
        restart.hidden=false;
        if(cfg.conversationEnabled){
          state.step='conversational';
          try{
            const turn=await conversationalTurn(userMessage);
            bubble(turn.response.text,'bot');
            renderApprovedLinks(turn.response.links);
            if(turn.response.resulting_action==='human_handoff'){
              offerHumanHelp();
            }else if(turn.response.resulting_action==='legacy_guided_flow'){
              activateLegacy();
            }else{
              input('<input name="answer" aria-label="Ask Budly anything" placeholder="Ask Budly anything…" required><button type="button" class="budly-secondary" data-budly-returning>Returning customer? Verify your email</button>','Send');
            }
          }catch(err){
            activateLegacy('I’m currently operating in guided mode. You can still explore products or connect with human support.');
          }
        }else{
          if(hasRisk(userMessage)){
            state.journey=journeys.wellness;
            state.answers=['safety review','human assistance','no automated recommendation'];
            track('journey_selected');
            await finish();
            return;
          }
          const [,j]=route(userMessage);
          state.journey=j;
          track('journey_selected');
          if(j===journeys.membership&&membershipPolicyRequested(userMessage))explainMembershipPolicy();
          state.step='questions';
          bubble('I’ll use the '+j.label+' path so the next questions stay relevant.','bot',j.label);
          ask();
        }
      }
      else if(state.step==='questions'){state.answers.push(d.answer);bubble(d.answer,'user');state.q++;ask()}
    }catch(err){bubble(err.message||'Something went wrong. Please try again.','bot','Notice')}finally{send.disabled=false}
  });
  root.querySelectorAll('[data-budly-hero-starter]').forEach(button=>button.addEventListener('click',()=>{
    root.querySelectorAll('[data-budly-hero-starter]').forEach(b=>b.classList.remove('is-selected'));
    button.classList.add('is-selected');
    const starterText=button.dataset.budlyHeroStarter||'';
    track('starter_selected',{metadata:button.textContent.trim()});
    const field=fields.querySelector('input[name="answer"]');
    if(field){
      field.value=starterText;
      form.requestSubmit();
    }
  }));
  restart.addEventListener('click',start);start();
});
})();
