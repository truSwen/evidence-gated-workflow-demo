import {mount} from './app.js';
let sessionId;
async function post(path,data){
 const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 if(!response.ok)throw new Error('The local synthetic runner refused this command.');
 return response.json();
}
mount({label:'Local Python · state lives in this runner session',
 async reset(fixture){const r=await post('/api/review',{action:'reset',fixture});sessionId=r.session_id;return r.view;},
 async command(action,args={}){return (await post('/api/review',{action,session_id:sessionId,...args})).view;},
 async legacy(scenario){return post('/api/run',{scenario});}
});
