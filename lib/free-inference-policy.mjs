// This limits inference routing, not third-party tool fees or host costs.
export function freeInferenceEligible(provider,model,apiBase) {
  if(provider==='local'){
    try{const url=new URL(apiBase),host=url.hostname.replace(/^\[|\]$/g,'').toLowerCase();
      return ['http:','https:'].includes(url.protocol) && !url.username && !url.password && !url.search && !url.hash &&
        (['localhost','vector-local-inference','host.docker.internal','::1'].includes(host) || /^(?:127|10)\.\d+\.\d+\.\d+$/.test(host) || /^192\.168\.\d+\.\d+$/.test(host) || /^172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+$/.test(host) || /^(?:fc|fd)[a-f0-9]{2}:/.test(host));
    }catch{return false;}
  }
  if(provider!=='openrouter' || typeof model!=='string' || !(model==='openrouter/free'||/^[a-z0-9_.-]+\/[a-z0-9_.:/-]+:free$/i.test(model)))return false;
  try {const url=new URL(apiBase);return url.protocol==='https:' && url.hostname==='openrouter.ai' && !url.port && !url.username && !url.password && !url.search && !url.hash && url.pathname.replace(/\/$/,'')==='/api/v1';}catch{return false;}
}
export function enforceFreeInference(runtime) {
  if(runtime?.freeOnly && !freeInferenceEligible(runtime.provider,runtime.model,runtime.apiBase))throw Object.assign(new Error('Free-only inference has no eligible local or OpenRouter free model. Paid fallback is disabled.'),{code:'FREE_INFERENCE_UNAVAILABLE'});
}
