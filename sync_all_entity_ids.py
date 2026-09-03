"""
sync_all_entity_ids.py
──────────────────────
Takes entity_id from BOTH zdotapps_user_master AND factops_user_master
and syncs into:
  1. SQLite  three_c_eng_mapping  (our FRS mapping table)
  2. MySQL   3c_eng_events        (entity_id column)
  3. MySQL   3c_eng_attendance    (entity_id column)
  4. MySQL   3c_eng_persons       (entity_id column, if column exists)

Matching: full name (first+last) vs our persons.name — exact then fuzzy.
Run: python sync_all_entity_ids.py
"""

import sys
import sqlite3
import pymysql
from difflib import SequenceMatcher
from datetime import datetime

MYSQL_CFG = dict(
    host="zdotapps-devenviron.cvuouqwaej9d.ap-south-1.rds.amazonaws.com",
    port=3306, user="3c_dev_user", password="2H&5bQU2*)J)",
    database="3C_Z_ATTEND_AI", charset="utf8mb4", connect_timeout=10
)
SQLITE_DB = r"data\frs.db"

def sim(a, b):
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

mysql = pymysql.connect(**MYSQL_CFG)
mc = mysql.cursor()
sq = sqlite3.connect(SQLITE_DB)
sq.row_factory = sqlite3.Row
sc = sq.cursor()

# ── 1. Build master lookup from BOTH tables ───────────────────
# source priority: zdotapps first, factops fills gaps
master = {}  # full_name_lower -> {entity_id, full_name, source}

for tbl, src in [("factops_user_master", "factops"), ("zdotapps_user_master", "zdotapps")]:
    mc.execute(f"SELECT first_name, last_name, entity_id FROM `{tbl}` WHERE entity_id IS NOT NULL AND entity_id != ''")
    for fn, ln, eid in mc.fetchall():
        fn = (fn or "").strip()
        ln = (ln or "").strip()
        full = f"{fn} {ln}".strip()
        key  = full.lower()
        if key not in master:  # zdotapps loaded second → overwrites factops
            master[key] = {"entity_id": eid, "full_name": full, "source": src}

print(f"Master lookup built: {len(master)} unique names (zdotapps + factops)")

# ── 2. Load our persons ───────────────────────────────────────
sc.execute("SELECT id, name FROM persons ORDER BY id")
our_persons = sc.fetchall()

sc.execute("SELECT person_id, entity_id FROM three_c_eng_mapping WHERE person_id IS NOT NULL")
existing = {r[0]: r[1] for r in sc.fetchall()}
print(f"Already mapped: {len(existing)}  |  Our persons: {len(our_persons)}")

# ── 3. Match ─────────────────────────────────────────────────
print(f"\n{'='*70}")
print("MATCHING:")
print(f"{'='*70}")

to_write   = []   # (pid, our_name, entity_id, master_name, method, source)
no_match   = []

for p in our_persons:
    pid  = p["id"]
    name = p["name"].strip()

    if pid in existing:
        continue   # already has entity_id

    # Exact
    if name.lower() in master:
        info = master[name.lower()]
        to_write.append((pid, name, info["entity_id"], info["full_name"], "exact", info["source"]))
        print(f"  EXACT   {name:<32} -> {info['entity_id'][:22]}  [{info['source']}]")
        continue

    # Fuzzy
    best_s, best_k = 0.0, None
    for mk in master:
        s = sim(name, mk)
        if s > best_s:
            best_s, best_k = s, mk

    if best_s >= 0.80 and best_k:
        info = master[best_k]
        to_write.append((pid, name, info["entity_id"], info["full_name"], f"fuzzy_{best_s:.2f}", info["source"]))
        print(f"  FUZZY   {name:<32} -> {info['entity_id'][:22]}  [{info['source']}]  ({best_s:.2f})")
    else:
        no_match.append((pid, name, best_k or "", round(best_s, 2)))

print(f"\n  New matches : {len(to_write)}")
print(f"  No match    : {len(no_match)}")
if no_match:
    print(f"\n  --- Still unmatched ---")
    for pid, name, bk, bs in no_match:
        print(f"    ID={pid:<4} {name:<32}  best={bs:.2f} ({bk})")

if not to_write:
    print("\nNothing new to sync.")
    mysql.close(); sq.close(); sys.exit(0)

# ── 4. Write to SQLite three_c_eng_mapping ───────────────────
now = datetime.now().isoformat()
sc_w = sq.cursor()
wrote_sq = 0
for pid, our_name, eid, mname, method, src in to_write:
    # Check if entity_id already taken by another person
    sc_w.execute("SELECT person_id FROM three_c_eng_mapping WHERE entity_id = ?", (eid,))
    ex = sc_w.fetchone()
    if ex and ex[0] != pid:
        print(f"  [SKIP] entity {eid[:20]} already mapped to pid={ex[0]}, skip {our_name}")
        continue
    parts = mname.split(" ", 1)
    fn = parts[0]; ln = parts[1] if len(parts) > 1 else ""
    sc_w.execute("""
        INSERT INTO three_c_eng_mapping
            (entity_id, full_name, first_name, last_name, person_id, our_name, match_method, mapped_at)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(entity_id) DO UPDATE SET
            person_id=excluded.person_id, our_name=excluded.our_name,
            match_method=excluded.match_method, mapped_at=excluded.mapped_at
    """, (eid, mname, fn, ln, pid, our_name, f"{method}_{src}", now))
    wrote_sq += 1

sq.commit()
print(f"\n[SQLite] three_c_eng_mapping  : +{wrote_sq} new rows")

# Reload full map
sc_w.execute("SELECT person_id, entity_id FROM three_c_eng_mapping WHERE person_id IS NOT NULL")
full_map = {r[0]: r[1] for r in sc_w.fetchall()}
print(f"[SQLite] Total mapped          : {len(full_map)} persons")

# ── 5. Ensure entity_id columns exist in MySQL ───────────────
for tbl in ["3c_eng_events", "3c_eng_attendance", "3c_eng_persons"]:
    try:
        mc.execute(f"DESCRIBE `{tbl}`")
        cols = [r[0] for r in mc.fetchall()]
        if "entity_id" not in cols:
            mc.execute(f"ALTER TABLE `{tbl}` ADD COLUMN entity_id VARCHAR(255) DEFAULT NULL")
            mysql.commit()
            print(f"[MySQL] Added entity_id column to {tbl}")
    except Exception as e:
        pass  # table may not exist for all

# ── 6. Update MySQL 3c_eng_events ────────────────────────────
ev_upd = 0
for pid, eid in full_map.items():
    try:
        mc.execute("""UPDATE 3c_eng_events SET entity_id=%s
                      WHERE person_id=%s AND (entity_id IS NULL OR entity_id='')""",
                   (eid, pid))
        ev_upd += mc.rowcount
    except Exception:
        pass
mysql.commit()
print(f"[MySQL] 3c_eng_events updated  : {ev_upd} rows")

# ── 7. Update MySQL 3c_eng_attendance ────────────────────────
att_upd = 0
for pid, eid in full_map.items():
    try:
        mc.execute("""UPDATE 3c_eng_attendance SET entity_id=%s
                      WHERE person_id=%s AND (entity_id IS NULL OR entity_id='')""",
                   (eid, pid))
        att_upd += mc.rowcount
    except Exception:
        pass
mysql.commit()
print(f"[MySQL] 3c_eng_attendance upd  : {att_upd} rows")

# ── 8. Update MySQL 3c_eng_persons ───────────────────────────
per_upd = 0
for pid, eid in full_map.items():
    try:
        mc.execute("""UPDATE 3c_eng_persons SET entity_id=%s
                      WHERE id=%s AND (entity_id IS NULL OR entity_id='')""",
                   (eid, pid))
        per_upd += mc.rowcount
    except Exception:
        pass
mysql.commit()
print(f"[MySQL] 3c_eng_persons updated : {per_upd} rows")

mysql.close(); sq.close()

print(f"\n{'='*70}")
print(f"  DONE")
print(f"  SQLite mapping  : +{wrote_sq} | total {len(full_map)} persons mapped")
print(f"  MySQL events    : {ev_upd} rows")
print(f"  MySQL attendance: {att_upd} rows")
print(f"  MySQL persons   : {per_upd} rows")
print(f"{'='*70}")
