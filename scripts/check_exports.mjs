/** Browser converter round-trip fixtures. No DOM or browser required. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {formatExport,tokenize} from '../frontend/src/core/exporters.js';
const text='🙂 bạn ngu!';const spans=[{start:6,end:9,label:'TOXIC'}];
const rows=[{id:1,text,label:'TOXIC',spans,context:'parent',source_text:text,review_status:'adjudicated',annotators:[{user_id:1,label:'TOXIC',spans,status:'submitted',revision:1,assisted:false}],is_meaningful:true}];
const tokens=tokenize(text,spans);assert.equal(tokens.map(t=>t.text).join(' '),'🙂 bạn ngu !');assert.equal(tokens.find(t=>t.text==='ngu').bio,'B-TOXIC');assert.equal(tokens.at(-1).bio,'O');
const formats=['conll','conll_full','hf_jsonl','spacy_json','doccano_jsonl','label_studio_json','json_sentence','json_token','jsonl','xml','csv_sentence','csv_token','csv_spans','csv_annotations','xlsx','json_llm'];
for(const format of formats){const out=formatExport(rows,format,[{key:'TOXIC',name:'Toxic'}],'Export fixture');assert.ok(out.body.length>0);if(format==='xlsx'&&process.argv[2])fs.writeFileSync(process.argv[2],out.body);}
console.log('All 16 browser export converters produced output; Unicode and partial-token BIO verified.');
