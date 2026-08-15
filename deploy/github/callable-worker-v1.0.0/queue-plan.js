'use strict';

const fs = require('fs');
const path = require('path');
const {spawnSync} = require('child_process');

const PLAN_SCHEMA = 'frost-callable-queue-plan/1.0';
const DEFAULT_MAX_BATCH = 128;
const REQUEST_DIR = 'runtime/requests';
const RESULT_DIR = 'runtime/results';
const VERIFICATION_DIR = 'runtime/verifications';
const ZERO_SHA = '0000000000000000000000000000000000000000';

function normalizeRepoPath(value) {
  return value.split(path.sep).join('/').replace(/^\.\//, '');
}

function isRequestPath(value) {
  const normalized = normalizeRepoPath(value);
  return normalized.startsWith(`${REQUEST_DIR}/`) && normalized.endsWith('.json');
}

function listAllRequests(root = '.') {
  const dir = path.join(root, REQUEST_DIR);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((name) => name.endsWith('.json'))
    .map((name) => `${REQUEST_DIR}/${name}`)
    .sort();
}

function validCommit(root, sha) {
  if (typeof sha !== 'string' || !/^[0-9a-f]{40}$/.test(sha) || sha === ZERO_SHA) return false;
  const check = spawnSync('git', ['cat-file', '-e', `${sha}^{commit}`], {
    cwd: root,
    encoding: 'utf8',
  });
  return check.status === 0;
}

function changedRequests(root, before, head) {
  if (!validCommit(root, before) || !validCommit(root, head)) {
    return {paths: listAllRequests(root), fallback: true, reason: 'commit-range-unavailable'};
  }
  const diff = spawnSync(
    'git',
    ['diff', '--name-only', '--diff-filter=AM', before, head, '--', REQUEST_DIR],
    {cwd: root, encoding: 'utf8'},
  );
  if (diff.status !== 0) {
    return {paths: listAllRequests(root), fallback: true, reason: 'git-diff-failed'};
  }
  const paths = diff.stdout
    .split(/\r?\n/)
    .map((value) => normalizeRepoPath(value.trim()))
    .filter((value) => value && isRequestPath(value))
    .filter((value) => fs.existsSync(path.join(root, value)));
  return {paths: [...new Set(paths)].sort(), fallback: false, reason: null};
}

function classifyCandidates(candidates, options = {}) {
  const root = options.root || '.';
  const eventName = options.eventName || 'workflow_dispatch';
  const maxBatch = Number(options.maxBatch ?? DEFAULT_MAX_BATCH);
  if (!Number.isInteger(maxBatch) || maxBatch < 1 || maxBatch > 10000) {
    throw new Error('maxBatch must be an integer from 1 to 10000');
  }

  const unique = [...new Set(candidates.map(normalizeRepoPath))]
    .filter(isRequestPath)
    .filter((value) => fs.existsSync(path.join(root, value)))
    .sort();

  const execute = [];
  const verify_missing = [];
  const reverify_existing = [];
  const complete = [];
  const deferred = [];

  for (const requestPath of unique) {
    const base = path.basename(requestPath);
    const resultPath = `${RESULT_DIR}/${base}`;
    const verificationPath = `${VERIFICATION_DIR}/${base}`;
    const hasResult = fs.existsSync(path.join(root, resultPath));
    const hasVerification = fs.existsSync(path.join(root, verificationPath));

    if (hasResult) {
      if (!hasVerification) {
        verify_missing.push(requestPath);
      } else if (eventName === 'push') {
        // Re-verify a request that changed after an immutable result already exists.
        // The verifier must fail if the request no longer matches the result envelope.
        reverify_existing.push(requestPath);
      } else {
        complete.push(requestPath);
      }
      continue;
    }

    if (execute.length < maxBatch) execute.push(requestPath);
    else deferred.push(requestPath);
  }

  return {
    candidates: unique,
    execute,
    verify_missing,
    reverify_existing,
    complete,
    deferred,
  };
}

function buildPlan(options = {}) {
  const root = path.resolve(options.root || '.');
  const eventName = options.eventName || 'workflow_dispatch';
  const maxBatch = Number(options.maxBatch ?? DEFAULT_MAX_BATCH);
  let discovery;
  if (eventName === 'push') discovery = changedRequests(root, options.before, options.head);
  else discovery = {paths: listAllRequests(root), fallback: false, reason: null};

  const classified = classifyCandidates(discovery.paths, {root, eventName, maxBatch});
  return {
    schema: PLAN_SCHEMA,
    event_name: eventName,
    incremental: eventName === 'push' && !discovery.fallback,
    fallback_full_scan: discovery.fallback,
    fallback_reason: discovery.reason,
    max_batch: maxBatch,
    counts: {
      candidates: classified.candidates.length,
      execute: classified.execute.length,
      verify_missing: classified.verify_missing.length,
      reverify_existing: classified.reverify_existing.length,
      complete: classified.complete.length,
      deferred: classified.deferred.length,
    },
    ...classified,
  };
}

function parseArgs(argv) {
  const options = {root: '.', eventName: 'workflow_dispatch', maxBatch: DEFAULT_MAX_BATCH};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = argv[i + 1];
    if (arg === '--root') { options.root = next; i += 1; }
    else if (arg === '--event') { options.eventName = next; i += 1; }
    else if (arg === '--before') { options.before = next; i += 1; }
    else if (arg === '--head') { options.head = next; i += 1; }
    else if (arg === '--max-batch') { options.maxBatch = Number(next); i += 1; }
    else throw new Error(`unknown argument: ${arg}`);
  }
  return options;
}

function main(argv) {
  const plan = buildPlan(parseArgs(argv));
  process.stdout.write(`${JSON.stringify(plan, null, 2)}\n`);
}

if (require.main === module) main(process.argv.slice(2));
module.exports = {
  PLAN_SCHEMA,
  DEFAULT_MAX_BATCH,
  REQUEST_DIR,
  RESULT_DIR,
  VERIFICATION_DIR,
  listAllRequests,
  changedRequests,
  classifyCandidates,
  buildPlan,
};
