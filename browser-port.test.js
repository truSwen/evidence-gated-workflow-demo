import{test}from'node:test';import assert from'node:assert/strict';import{execFileSync}from'node:child_process';import{runScenario,SCENARIOS}from'./browser-workflow.js';
for(const scenario of Object.keys(SCENARIOS))test(`browser port matches complete Python result: ${scenario}`,async()=>{const expected=JSON.parse(execFileSync('python3',['demo.py','--scenario',scenario],{encoding:'utf8'}));assert.deepEqual(await runScenario(scenario),expected);});
test('unknown browser scenario is refused',async()=>{await assert.rejects(()=>runScenario('__proto__'),/Unknown scenario/);});
