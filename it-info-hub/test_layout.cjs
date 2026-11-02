const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context=vm.createContext({document:{querySelector:()=>null},localStorage:{getItem:()=>null},Set,console});
let code=fs.readFileSync(process.argv[2],'utf8'); code=code.slice(0,code.lastIndexOf('(async () =>'));
vm.runInContext(code,context);
assert.equal(vm.runInContext("isRelease({source:'vLLM Releases',category:'AI Agent'})",context),true);
assert.equal(vm.runInContext("isRelease({source:'GitHub Blog',category:'Software'})",context),false);
assert.equal(vm.runInContext("isRelease({source:'Custom',category:'Software Release'})",context),true);
console.log('Release routing checks passed');
