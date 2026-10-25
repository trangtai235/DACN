// Exact portable form of sklearn char TF-IDF + binary linear LogisticRegression.
export function portablePredict(model,texts){
 if(!model.vocab)model.vocab=new Map(model.features.map((f,i)=>[f,i]));
 return texts.map(text=>{
  const chars=Array.from(text.toLowerCase().replace(/\s\s+/g,' ')),counts=new Map();
  for(let n=3;n<=5;n++)for(let i=0;i<=chars.length-n;i++){
   const idx=model.vocab.get(chars.slice(i,i+n).join(''));if(idx!==undefined)counts.set(idx,(counts.get(idx)||0)+1);
  }
  let norm=0,dot=0;
  for(const [i,c] of counts){const w=(1+Math.log(c))*model.idf[i];norm+=w*w;dot+=w*model.coef[i];}
  return (model.label_keys||['NON_TOXIC','TOXIC'])[model.intercept+(norm?dot/Math.sqrt(norm):0)>=0?1:0];
 });
}
