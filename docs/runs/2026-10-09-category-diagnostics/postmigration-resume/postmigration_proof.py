#!/usr/bin/env python3
"""Read-only schema20 proof, including committed WAL and old NULL diagnostics."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import data_proof


def prove(directory):
    root=Path(directory)
    result=data_proof.prove(root,cold=False)  # WAL-aware; never immutable here
    data_proof.require(result['schema']==20,'episode_schema')
    with closing(sqlite3.connect((root/'episodes.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
        field=next((row for row in db.execute('PRAGMA table_info(memory_category_sources)') if row[1]=='failure_code'),None)
        data_proof.require(field is not None and field[2:]==('TEXT',0,None,0),'failure_column_contract')
        data_proof.require(db.execute('SELECT count(*) FROM memory_category_sources WHERE failure_code IS NOT NULL').fetchone()[0]==0,'non_null_old_failure_code')
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',required=True);args=parser.parse_args()
    try:print(json.dumps(prove(args.data_dir),sort_keys=True));return 0
    except Exception as exc:
        print(json.dumps({'error':str(exc) if isinstance(exc,data_proof.CheckFailed) else 'postmigration_proof_failed'}));return 1

if __name__=='__main__':raise SystemExit(main())
