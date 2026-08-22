#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, time, uuid
from pathlib import Path

ROOT = Path(os.environ.get("CENTINAL26_HOME", str(Path.home()/".centinal26")))
DB = ROOT/"state"/"daemon.sqlite3"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS task (
 id TEXT PRIMARY KEY,intent TEXT NOT NULL,capability TEXT NOT NULL,payload_json TEXT NOT NULL,
 idempotency_key TEXT NOT NULL UNIQUE,state TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,
 lease_owner TEXT,lease_until INTEGER,attempt_count INTEGER NOT NULL DEFAULT 0,next_attempt_at INTEGER NOT NULL DEFAULT 0,
 source_revision TEXT,last_error TEXT);
CREATE TABLE IF NOT EXISTS evidence (
 id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT NOT NULL,ts INTEGER NOT NULL,kind TEXT NOT NULL,payload_json TEXT NOT NULL,sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS daemon_state (key TEXT PRIMARY KEY,value TEXT NOT NULL);
"""

def con():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.executescript(SCHEMA); return c

def enqueue(args):
    payload=json.loads(args.payload)
    now=int(time.time())
    idem=args.idempotency_key or hashlib.sha256(json.dumps({"intent":args.intent,"capability":args.capability,"payload":payload},sort_keys=True).encode()).hexdigest()
    task_id=args.task_id or str(uuid.uuid4())
    c=con()
    try:
        c.execute("INSERT INTO task(id,intent,capability,payload_json,idempotency_key,state,created_at,updated_at,next_attempt_at,source_revision) VALUES(?,?,?,?,?,'QUEUED',?,?,?,?,?)",
                  (task_id,args.intent,args.capability,json.dumps(payload,sort_keys=True),idem,now,now,0,args.source_revision))
        c.commit()
        print(json.dumps({"status":"QUEUED","task_id":task_id,"idempotency_key":idem},sort_keys=True))
    except sqlite3.IntegrityError:
        row=c.execute("SELECT id,state FROM task WHERE idempotency_key=?",(idem,)).fetchone()
        print(json.dumps({"status":"ALREADY_EXISTS","task_id":row["id"],"state":row["state"],"idempotency_key":idem},sort_keys=True))

def status(args):
    c=con()
    if args.task_id:
        row=c.execute("SELECT * FROM task WHERE id=?",(args.task_id,)).fetchone()
        print(json.dumps(dict(row) if row else {"status":"NOT_FOUND"},sort_keys=True))
    else:
        rows=[dict(r) for r in c.execute("SELECT id,intent,capability,state,attempt_count,updated_at,last_error FROM task ORDER BY created_at DESC LIMIT ?",(args.limit,))]
        health=c.execute("SELECT value FROM daemon_state WHERE key='health'").fetchone()
        print(json.dumps({"health":json.loads(health[0]) if health else None,"tasks":rows},sort_keys=True))

def evidence(args):
    c=con(); rows=[dict(r) for r in c.execute("SELECT ts,kind,payload_json,sha256 FROM evidence WHERE task_id=? ORDER BY id",(args.task_id,))]
    for r in rows: r["payload"]=json.loads(r.pop("payload_json"))
    print(json.dumps({"task_id":args.task_id,"evidence":rows},sort_keys=True))

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    q=sub.add_parser("enqueue"); q.add_argument("--intent",required=True); q.add_argument("--capability",required=True); q.add_argument("--payload",required=True); q.add_argument("--idempotency-key"); q.add_argument("--task-id"); q.add_argument("--source-revision"); q.set_defaults(fn=enqueue)
    s=sub.add_parser("status"); s.add_argument("--task-id"); s.add_argument("--limit",type=int,default=20); s.set_defaults(fn=status)
    e=sub.add_parser("evidence"); e.add_argument("task_id"); e.set_defaults(fn=evidence)
    a=p.parse_args(); a.fn(a)
if __name__=="__main__": main()
