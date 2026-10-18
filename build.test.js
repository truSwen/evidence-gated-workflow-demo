import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
test('build uses shared HTML, explicit adapter and a clean asset allowlist',async()=>{
 await mkdir('dist',{recursive:true});await writeFile('dist/do-not-ship.txt','stale artifact');
 execFileSync(process.execPath,['build.js']);
 assert.deepEqual((await readdir('dist')).sort(),['404.html','_headers','entry.js','index.html','style.css']);
 assert.equal(await readFile('dist/index.html','utf8'),await readFile('index.html','utf8'));
 assert.equal(await readFile('dist/style.css','utf8'),await readFile('style.css','utf8'));
 const code=await readFile('dist/entry.js','utf8');
 assert.ok(!code.includes('/api/review'));assert.ok(!code.includes('/api/run'));assert.ok(!/\bfetch\(/.test(code));
 assert.match(await readFile('dist/_headers','utf8'),/script-src 'self'/);
});
