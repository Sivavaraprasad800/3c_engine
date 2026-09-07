"""
create_status_table.py — Create 3c_eng_system_status table in production DB.
SAFE: CREATE TABLE IF NOT EXISTS only — no data touched.
Run: python scripts/tools/create_status_table.py
"""
import pymysql

conn = pymysql.connect(
    host="zdotbox.c7mkuyk28a42.ap-south-1.rds.amazonaws.com",
    port=3306, user="zdotbox", password="5fi7p1QDYRnX7TzKe6Py",
    database="3C_Z_ATTEND_AI", charset="utf8mb4", connect_timeout=10,
)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS `3c_eng_system_status` (
    `id`              INT AUTO_INCREMENT PRIMARY KEY,
    `org_id`          VARCHAR(100) NOT NULL DEFAULT 'default',
    `hostname`        VARCHAR(200),
    `ip_address`      VARCHAR(50),
    `status`          TINYINT DEFAULT 1 COMMENT '1=running 0=stopped',
    `version`         VARCHAR(50),
    `cameras_running` INT DEFAULT 0,
    `last_heartbeat`  VARCHAR(50),
    `started_at`      VARCHAR(50),
    UNIQUE KEY `uq_org_host` (`org_id`, `hostname`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
""")
conn.commit()

cur.execute("SHOW CREATE TABLE `3c_eng_system_status`")
print("Table created:")
print(cur.fetchone()[1])
cur.close()
conn.close()
print("\nDone — no existing data was changed.")
