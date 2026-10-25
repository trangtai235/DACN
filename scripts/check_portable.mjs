import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {portablePredict} from '../frontend/src/core/inference.js';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const model=JSON.parse(fs.readFileSync(path.join(root,process.argv[3]||'frontend/public/model-1.json'),'utf8'));
const rows=JSON.parse(fs.readFileSync(process.argv[2]||path.join(root,'dist/assets/demo-data.json'),'utf8'));
const pred=portablePredict(model,rows.map(r=>r.text));
const errors=rows.map((r,i)=>({id:r.id,want:r.ai_label??r.expected,got:pred[i]})).filter(r=>r.want!==r.got);
if(errors.length){console.error(JSON.stringify(errors.slice(0,10)));process.exit(1);}
console.log(`Portable model: ${rows.length} / ${rows.length} predictions match sklearn.`);
