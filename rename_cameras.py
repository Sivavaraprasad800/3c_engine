import pymysql

conn = pymysql.connect(
    host="zdotapps-devenviron.cvuouqwaej9d.ap-south-1.rds.amazonaws.com",
    port=3306, user="3c_dev_user", password="2H&5bQU2*)J)",
    database="3C_Z_ATTEND_AI", charset="utf8mb4", connect_timeout=10
)
cur = conn.cursor()

renames = [
    ("DEMO",  "studio-1 (2)"),
    ("dome",  "studio-1 (1)"),
]

for old_id, new_id in renames:
    print(f"\nRenaming '{old_id}' → '{new_id}'")

    # 3c_eng_events
    cur.execute("UPDATE 3c_eng_events SET camera_id=%s WHERE camera_id=%s", (new_id, old_id))
    print(f"  3c_eng_events    : {cur.rowcount} rows updated")

    # 3c_eng_attendance
    cur.execute("UPDATE 3c_eng_attendance SET camera_id=%s WHERE camera_id=%s", (new_id, old_id))
    print(f"  3c_eng_attendance: {cur.rowcount} rows updated")

    # 3c_eng_cameras (update primary key — need insert+delete since id is PK)
    cur.execute("SELECT * FROM 3c_eng_cameras WHERE id=%s", (old_id,))
    row = cur.fetchone()
    if row:
        cols = [d[0] for d in cur.description]
        data = dict(zip(cols, row))
        data["id"] = new_id
        placeholders = ", ".join([f"`{c}`=%s" for c in cols])
        vals = [data[c] for c in cols]
        # Insert new row
        col_names = ", ".join([f"`{c}`" for c in cols])
        val_placeholders = ", ".join(["%s"] * len(cols))
        cur.execute(f"INSERT IGNORE INTO 3c_eng_cameras ({col_names}) VALUES ({val_placeholders})", vals)
        # Delete old row
        cur.execute("DELETE FROM 3c_eng_cameras WHERE id=%s", (old_id,))
        print(f"  3c_eng_cameras   : renamed id='{old_id}' → '{new_id}'")
    else:
        print(f"  3c_eng_cameras   : no camera row found for '{old_id}' (only events updated)")

conn.commit()
print("\n=== DONE — verifying ===")

cur.execute("SELECT id, name FROM 3c_eng_cameras ORDER BY id")
print("\nCameras now:")
for r in cur.fetchall():
    print(f"  id={r[0]:<20} name={r[1]}")

cur.execute("SELECT camera_id, COUNT(*) FROM 3c_eng_events GROUP BY camera_id ORDER BY camera_id")
print("\nEvents by camera_id:")
for r in cur.fetchall():
    if r[0]:
        print(f"  {r[0]:<25} {r[1]} events")

conn.close()
print("\nDone.")
