'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {spawnSync} = require('child_process');
const {buildPlan, classifyCandidates} = require('./queue-plan');

function write(root, relative, body = '{}\n') {
  const target = path.join(root, relative);
  fs.mkdirSync(path.dirname(target), {recursive: true});
  fs.writeFileSync(target, body);
}

function git(root, args) {
  const result = spawnSync('git', args, {cwd: root, encoding: 'utf8'});
  if (result.status !== 0) throw new Error(result.stderr || `git ${args.join(' ')} failed`);
  return result.stdout.trim();
}

function main() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'frost-queue-doctor-'));
  try {
    write(root, 'runtime/requests/a.json');
    write(root, 'runtime/requests/b.json');
    write(root, 'runtime/requests/c.json');
    write(root, 'runtime/requests/d.json');
    write(root, 'runtime/results/a.json');
    write(root, 'runtime/verifications/a.json');
    write(root, 'runtime/results/b.json');

    const push = classifyCandidates(
      ['runtime/requests/d.json', 'runtime/requests/a.json', 'runtime/requests/b.json', 'runtime/requests/c.json', 'runtime/requests/a.json'],
      {root, eventName: 'push', maxBatch: 1},
    );
    assert.deepStrictEqual(push.reverify_existing, ['runtime/requests/a.json']);
    assert.deepStrictEqual(push.verify_missing, ['runtime/requests/b.json']);
    assert.deepStrictEqual(push.execute, ['runtime/requests/c.json']);
    assert.deepStrictEqual(push.deferred, ['runtime/requests/d.json']);

    const scheduled = classifyCandidates(
      ['runtime/requests/a.json', 'runtime/requests/b.json', 'runtime/requests/c.json', 'runtime/requests/d.json'],
      {root, eventName: 'schedule', maxBatch: 1},
    );
    assert.deepStrictEqual(scheduled.complete, ['runtime/requests/a.json']);
    assert.deepStrictEqual(scheduled.verify_missing, ['runtime/requests/b.json']);
    assert.deepStrictEqual(scheduled.execute, ['runtime/requests/c.json']);
    assert.deepStrictEqual(scheduled.deferred, ['runtime/requests/d.json']);

    const gitRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'frost-queue-git-'));
    try {
      git(gitRoot, ['init', '-q']);
      git(gitRoot, ['config', 'user.email', 'queue-doctor@example.invalid']);
      git(gitRoot, ['config', 'user.name', 'Queue Doctor']);
      write(gitRoot, 'runtime/requests/first.json');
      git(gitRoot, ['add', '.']);
      git(gitRoot, ['commit', '-qm', 'first']);
      const before = git(gitRoot, ['rev-parse', 'HEAD']);
      write(gitRoot, 'runtime/requests/second.json');
      git(gitRoot, ['add', '.']);
      git(gitRoot, ['commit', '-qm', 'second']);
      const head = git(gitRoot, ['rev-parse', 'HEAD']);
      const plan = buildPlan({root: gitRoot, eventName: 'push', before, head, maxBatch: 128});
      assert.strictEqual(plan.incremental, true);
      assert.strictEqual(plan.fallback_full_scan, false);
      assert.deepStrictEqual(plan.candidates, ['runtime/requests/second.json']);
      assert.deepStrictEqual(plan.execute, ['runtime/requests/second.json']);
    } finally {
      fs.rmSync(gitRoot, {recursive: true, force: true});
    }

    assert.throws(() => classifyCandidates([], {root, maxBatch: 0}), /maxBatch/);
    process.stdout.write(JSON.stringify({ok: true, checks: 12}) + '\n');
  } finally {
    fs.rmSync(root, {recursive: true, force: true});
  }
}

if (require.main === module) main();
