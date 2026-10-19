const cancelled = () => ({ok:false,json:async()=>({privacyCancelled:true})});

// Keep request sequencing testable independently of rendering. Consent is never
// retried silently and an obsolete scope can never confirm a reviewed request.
export function createPrivacySender({fetchImpl=fetch,onState,requestChoice,now=Date.now}) {
  let generation=0,busy=false,abort=null;
  return {
    cancel(){generation++;busy=false;abort?.abort();abort=null;onState({phase:'idle'});},
    async send(url,body,{localOnly=false,isCurrent=()=>true}={}){
      if(busy)throw new Error('Eine Anfrage wird bereits geprüft.');
      // The composer discloses separate protection for newly read tool evidence.
      body={...body,...(!localOnly && body.mode!=='local' && body.privacyEnabled!==false ? {toolEvidenceDecision:'replace'} : {})};
      busy=true;const version=++generation;const startedAt=now();
      const controller=new AbortController();abort=controller;
      const current=()=>version===generation && isCurrent();
      const state=phase=>{if(current())onState({phase,startedAt:phase==='sending'?now():startedAt});};
      const post=payload=>fetchImpl(url,{method:'POST',headers:{'Content-Type':'application/json'},
        signal:controller.signal,body:JSON.stringify(payload)});
      try {
        if(!current())return cancelled();
        if(!localOnly && body.mode!=='local')state(body.privacyEnabled===false?'sending':'checking');
        let response=await post(body);
        if(!current())return cancelled();
        if(response.status!==409)return response;
        const data=await response.clone().json();
        if(data.error!=='PRIVACY_REVIEW_REQUIRED')return response;
        if(!current())return cancelled();
        state('review');
        const choice=await requestChoice(data.privacyReview);
        if(!current() || !['replace','original'].includes(choice))return cancelled();
        state('sending');
        response=await post({...body,privacyDecision:choice,privacyReviewToken:data.privacyReview.token});
        return current()?response:cancelled();
      } catch(error){
        if(controller.signal.aborted || !current())return cancelled();
        throw error;
      } finally {
        if(version===generation){busy=false;abort=null;onState({phase:'idle'});}
      }
    }
  };
}

