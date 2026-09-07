const messages=document.querySelector('#messages'),form=document.querySelector('#composer'),fields=document.querySelector('#fields'),send=document.querySelector('#send'),restart=document.querySelector('#restart');
const urlParams=new URLSearchParams(window.location.search);
const initialAttribution={
 source:urlParams.get('source')||'direct',
 platform:urlParams.get('platform')||'web',
 content_id:urlParams.get('content_id')||'',
 campaign_id:urlParams.get('campaign_id')||'',
 cta_id:urlParams.get('cta_id')||'CTA-ASK-BUDLY-001',
 product_or_topic:urlParams.get('product_or_topic')||'UNKNOWN',
 published_post_id:urlParams.get('published_post_id')||''
};
const state={step:'conversation',sessionId:null,journeyId:null,attribution:initialAttribution,customerId:null,goal:'',journey:null,journeyAnswers:[],questionIndex:0,details:{}};
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function bubble(text,who='bot',label=''){const el=document.createElement('div');el.className=`message ${who}`;el.innerHTML=(label?`<div class="journey">${esc(label)}</div>`:'')+esc(text);messages.append(el);messages.scrollTop=messages.scrollHeight}
function inputs(html,button='Continue'){fields.innerHTML=html;send.textContent=button;setTimeout(()=>fields.querySelector('input,select')?.focus(),50)}
async function api(path,payload){send.disabled=true;try{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await r.json();if(!r.ok)throw new Error(data.error||'Please try again.');return data}finally{send.disabled=false}}

async function begin(){
 messages.innerHTML='';
 Object.assign(state,{step:'conversation',customerId:null,goal:'',journey:null,journeyAnswers:[],questionIndex:0,details:{}});
 restart.hidden=true;
 try{
  const intakeRes=await api('/api/intake',{landing_input:initialAttribution,landing_route:window.location.href});
  state.sessionId=intakeRes.session_id;
  state.journeyId=intakeRes.journey_id;
 }catch(e){}
 bubble("Hi, I’m Budly! I can help you compare current Wake'n'Bake Lounge products and answer questions without pressure. What are you looking for today?");
 inputs('<input name="message" id="chat-input" placeholder="Ask Budly anything..." autocomplete="off" required>','Send');
}

form.addEventListener('submit',async e=>{
 e.preventDefault();
 const data=Object.fromEntries(new FormData(form));
 try{
  if(state.step==='conversation'){
   const msg=data.message||data.answer;
   bubble(msg,'user');
   const out=await api('/api/turn',{session_id:state.sessionId,message:msg});
   bubble(out.bot_message,'bot');
   if(out.recommended_destination){
    showProductCard(out);
   }
   restart.hidden=false;
   inputs('<input name="message" id="chat-input" placeholder="Ask another question..." autocomplete="off" required>','Send');
  }
  else if(state.step==='identity'){
   bubble(data.name,'user');
   const out=await api('/api/start',{name:data.name,email:data.email,session_id:state.sessionId,attribution:state.attribution});
   state.customerId=out.customer_id;
   state.step='goal';
   restart.hidden=false;
   bubble(out.message);
   inputs('<input name="answer" placeholder="Tell me what you’re looking for" required>');
  }
  else if(state.step==='goal'){
   state.goal=data.answer;
   bubble(data.answer,'user');
   const out=await api('/api/route',{customer_id:state.customerId,shopping_goal:state.goal});
   state.journey=out.journey;
   state.step='journey';
   bubble(out.message,'bot',out.journey.label);
   askJourney();
  }
  else if(state.step==='journey'){
   state.journeyAnswers.push(data.answer);
   bubble(data.answer,'user');
   state.questionIndex++;
   askJourney();
  }
  else if(state.step==='experience'){
   state.details.experience_level=data.answer;
   bubble(fields.querySelector('option:checked').textContent,'user');
   state.step='format';
   bubble('What format sounds best, if you already have one in mind?');
   inputs('<input name="answer" placeholder="For example: oil, topical, book, course, digital…">');
  }
  else if(state.step==='format'){
   state.details.preferred_format=data.answer;
   bubble(data.answer||'No preference','user');
   state.step='budget';
   bubble('What budget range feels comfortable?');
   inputs('<input name="answer" placeholder="For example: under $75 or no set budget">');
  }
  else if(state.step==='budget'){
   state.details.budget_range=data.answer;
   bubble(data.answer||'No set budget','user');
   state.step='timeline';
   bubble('When are you hoping to make a decision?');
   inputs('<select name="answer"><option value="today">Today</option><option value="this_week">This week</option><option value="this_month">This month</option><option value="researching">Just researching</option></select>','Show my next step');
  }
  else if(state.step==='timeline'){
   state.details.purchase_timeline=data.answer;
   bubble(fields.querySelector('option:checked').textContent,'user');
   await finish();
  }
 }catch(err){
  bubble(err.message,'bot','Something went wrong');
 }
});

function askJourney(){
 const qs=state.journey.discovery_questions;
 if(state.questionIndex<qs.length){
  bubble(qs[state.questionIndex],'bot',state.journey.label);
  inputs('<input name="answer" placeholder="Your answer" required>');
  return;
 }
 state.step='experience';
 bubble('How familiar are you with this category?');
 inputs('<select name="answer"><option value="new">I’m new</option><option value="some_experience">Some experience</option><option value="experienced">Experienced</option><option value="unknown">Not sure</option></select>');
}

async function finish(){
 fields.innerHTML='';
 send.hidden=true;
 const out=await api('/api/complete',{customer_id:state.customerId,shopping_goal:state.goal,journey_answers:state.journeyAnswers,...state.details});
 bubble(out.message,'bot',out.journey.label);
 if(out.outcome==='recommendation')showProduct(out.recommendation);
 else if(out.outcome==='human_handoff'){
  bubble('Reference: '+out.escalation_id.slice(0,8).toUpperCase(),'bot','Handoff saved');
  if(out.human_sales_email)showLink('mailto:'+out.human_sales_email+'?subject=Budly%20handoff%20'+out.escalation_id.slice(0,8),`Contact ${out.human_sales_email}`);
 }else if(out.catalog_url)showLink(out.catalog_url,'Browse all products');
 state.step='done';
}

function showProductCard(out){
 const el=document.createElement('article');
 el.className='product-card recommendation-card';
 el.innerHTML=`<div class="journey">Recommended Destination</div><h3>${esc(out.display_label||out.product_or_topic)}</h3><p>State: <strong>${esc(out.qualification_state)}</strong></p><a href="${esc(out.recommended_destination)}" target="_blank" rel="noopener">${esc(out.display_label||'View Verified Product')} ↗</a>`;
 messages.append(el);
 messages.scrollTop=messages.scrollHeight;
}

function showProduct(p){
 const el=document.createElement('article');
 el.className='product-card';
 const facts=(p.factual_features||[]).map(x=>`<li>${esc(x)}</li>`).join('');
 const variants=p.variants?.length?`<p><strong>Options:</strong> ${p.variants.map(esc).join(', ')}</p>`:'';
 el.innerHTML=`<div class="journey">Closest match</div><h3>${esc(p.name)}</h3><div class="price">${esc(p.price||'See current price')}</div><p>${esc(p.summary)}</p>${variants}${facts?`<ul>${facts}</ul>`:''}<a href="${esc(p.product_url)}" target="_blank" rel="noopener">View verified product ↗</a>`;
 messages.append(el);
 messages.scrollTop=messages.scrollHeight;
}

function showLink(url,label){
 const el=document.createElement('div');
 el.className='product-card';
 el.innerHTML=`<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label)} ↗</a>`;
 messages.append(el);
}

restart.addEventListener('click',()=>{send.hidden=false;begin()});
begin();
