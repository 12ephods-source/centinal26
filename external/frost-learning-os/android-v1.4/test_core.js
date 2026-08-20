const assert=require('assert');
const crypto=require('crypto');
const C=require('./app/src/main/assets/core.js');
require('./app/src/main/assets/hotfix.js').apply(C);
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
assert(C.transferReady(s,'distribution','2026-08-01T00:02:00Z'));
assert(C.unlocked(s,'linear','2026-08-01T00:02:00Z'));
assert(C.retentionRequired(s.mastery.distribution,'2026-08-18T00:00:00Z'));
assert(!C.masteryReady(s,'distribution','2026-08-18T00:00:00Z'));
C.updateState(s,q('d1'),'wrong','2026-08-18T00:01:00Z');
assert.strictEqual(s.mastery.distribution.retentionHold,true);
C.updateState(s,q('d2'),'10y-15','2026-08-18T00:02:00Z');
assert.strictEqual(s.mastery.distribution.retentionHold,false);

// Repetition of one item alone must never unlock transfer.
let repeated=C.initialState();
for(let i=0;i<4;i++) C.updateState(repeated,q('d1'),'3x+12',`2026-08-19T0${i}:00:00Z`);
assert.strictEqual(C.independentCorrectCount(repeated.mastery.distribution),1);
assert.strictEqual(C.transferReady(repeated,'distribution','2026-08-19T05:00:00Z'),false);
assert.notStrictEqual(C.nextQuestion(repeated,'2026-08-19T05:00:00Z').id,'d3');

// Frozen curriculum-reachability gate: every transfer skill must be able to
// collect two independent direct observations before its transfer item.
for(const skill of Object.keys(C.SKILLS)){
  const direct=C.QUESTIONS.filter(item=>item.skill===skill&&!item.transfer);
  const transfers=C.QUESTIONS.filter(item=>item.skill===skill&&item.transfer);
  if(!transfers.length) continue;
  assert(
    direct.length>=2,
    `${skill} transfer is structurally unreachable: only ${direct.length} non-transfer item(s) for a two-distinct-item readiness gate`,
  );
  const reach=C.initialState();
  C.updateState(reach,direct[0],direct[0].answer,'2026-08-19T06:00:00Z');
  C.updateState(reach,direct[1],direct[1].answer,'2026-08-19T06:01:00Z');
  assert.strictEqual(C.independentCorrectCount(reach.mastery[skill]),2);
  assert.strictEqual(C.transferReady(reach,skill,'2026-08-19T06:02:00Z'),true);
  const oneItem=C.initialState();
  for(let i=0;i<4;i++) C.updateState(oneItem,direct[0],direct[0].answer,`2026-08-19T0${i}:10:00Z`);
  assert.strictEqual(C.transferReady(oneItem,skill,'2026-08-19T06:03:00Z'),false);
}

let e=C.initialState();
C.appendEvidence(e,{id:'1',at:'2026-08-18T00:00:00Z',type:'TEST'});
assert(C.verifyEvidenceChain(e).ok);
e.evidence[0].type='TAMPER';
assert(!C.verifyEvidenceChain(e).ok);

// Evidence hashing must be true UTF-8 SHA-256, not ASCII-only.
for(const text of ['漢','🧠','𝑥','é']){
  const expected=crypto.createHash('sha256').update(text,'utf8').digest('hex');
  assert.strictEqual(C.sha256(text),expected);
  const unicodeState=C.initialState();
  const event=C.appendEvidence(unicodeState,{id:'unicode',at:'2026-08-19T00:00:00Z',type:'ANSWER_SUBMITTED',question_id:'d1',skill:'distribution',response:text,correct:false});
  assert.strictEqual(event.hash.length,64);
  assert(C.verifyEvidenceChain(unicodeState).ok);
  unicodeState.evidence[0].response=text+'x';
  assert(!C.verifyEvidenceChain(unicodeState).ok);
}

const legacy={version:2,mastery:{distribution:{alpha:2,beta:1}},evidence:[],questionHistory:[]};
const migrated=C.normalizeState(legacy);
assert.strictEqual(migrated.version,4);
assert(Array.isArray(migrated.mastery.distribution.correctQuestionIds));
console.log('FROST_LEARNING_OS_CORE_TESTS PASS');
