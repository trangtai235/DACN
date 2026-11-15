import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const walk=dir=>fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(dir,e.name)):[path.join(dir,e.name)]);
let checked=0;
for(const file of [...walk('frontend/src'),...walk('dist/assets')].filter(f=>f.endsWith('.js'))){
 const result=spawnSync(process.execPath,['--check',file],{encoding:'utf8'});
 if(result.error)throw result.error;
 if(result.status!==0){process.stderr.write(result.stderr||'Syntax check failed: '+file);process.exit(1);}
 const source=fs.readFileSync(file,'utf8');
 for(const match of source.matchAll(/(?:from\s*|import\s*)['"](\.[^'"]+)['"]/g)){
  const target=path.resolve(path.dirname(file),match[1].split('?')[0]);
  if(!fs.existsSync(target))throw new Error(`Missing module: ${file} -> ${match[1]}`);
 }
 checked++;
}
console.log(`Syntax and relative module targets verified for ${checked} source/build modules.`);
