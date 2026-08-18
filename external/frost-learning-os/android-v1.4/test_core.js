const assert=require('assert');
const C=require('./app/src/main/assets/core.js');
function q(id){return C.QUESTIONS.find(x=>x.id===id)}

assert(C.equivalentLinearExpr('12+3x','3x+12'));
assert(!C.equivalentLinearExpr('12+3x','4x+12'));
assert.strictEqual(C.diagnose(q('d1'),'3x+4').code,'PARTIAL_DISTRIBUTION');
assert.notStrictEqual(C.diagnose(q('d2'),'3x+4').code,'PARTIAL_DISTRIBUTION');

let s=C.initialState();
assert(!C.transferReady(s,'distribution'));
assert(!C.unlocked(s,'linear'));
C.updateState(s,q('d1'),'3x+12','2026-08-01T00:00:00Z');
C.updateState(s,q('d2'),'10y-15','2026-08-01T00:01:00Z');
assert(C.masteryReady(s,'distribution','2026-08-01T00:02:00Z'));
assert(C.unlocked(s,'linear','2026-08-01T00:02:00Z'));
assert(C.retentionRequired(s.mastery.distribution,'2026-08-18T00:00:00Z'));
assert(!C.masteryReady(s,'distribution','2026-08-18T00:00:00Z'));
C.updateState(s,q('d1'),'wrong','2026-08-18T00:01:00Z');
assert.strictEqual(s.mastery.distribution.retentionHold,true);
C.updateState(s,q('d2'),'10y-15','2026-08-18T00:02:00Z');
assert.strictEqual(s.mastery.distribution.retentionHold,false);

let e=C.initialState();
C.appendEvidence(e,{id:'1',at:'2026-08-18T00:00:00Z',type:'TEST'});
assert(C.verifyEvidenceChain(e).ok);
e.evidence[0].type='TAMPER';
assert(!C.verifyEvidenceChain(e).ok);

const legacy={version:2,mastery:{distribution:{alpha:2,beta:1}},evidence:[],questionHistory:[]};
const migrated=C.normalizeState(legacy);
assert.strictEqual(migrated.version,4);
assert(Array.isArray(migrated.mastery.distribution.correctQuestionIds));
console.log('FROST_LEARNING_OS_CORE_TESTS PASS');
