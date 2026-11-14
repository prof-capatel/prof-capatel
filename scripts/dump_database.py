import os
import sys
import datetime
from pathlib import Path
import pymysql

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database.session import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB

def dump_db():
    backup_dir = BASE_DIR / "database" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"project_backup_{timestamp}.sql"

    print(f"[*] Dumping database to {backup_file.name}...")

    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

    with open(backup_file, "w", encoding="utf-8") as f:
        f.write(f"-- Curiosity HUB Multi-Tenant Face Attendance Database Dump\n")
        f.write(f"-- Generated At: {datetime.datetime.now().isoformat()}\n")
        f.write(f"-- Database: {MYSQL_DB}\n\n")
        f.write("SET FOREIGN_KEY_CHECKS=0;\n\n")

        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES;")
            tables = [list(r.values())[0] for r in cursor.fetchall()]

            for table in tables:
                cursor.execute(f"SHOW CREATE TABLE `{table}`;")
                create_sql = cursor.fetchone()["Create Table"]
                f.write(f"-- Table structure for table `{table}`\n")
                f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
                f.write(f"{create_sql};\n\n")

                cursor.execute(f"SELECT * FROM `{table}`;")
                rows = cursor.fetchall()
                if rows:
                    f.write(f"-- Dumping data for table `{table}` ({len(rows)} rows)\n")
                    f.write(f"LOCK TABLES `{table}` WRITE;\n")
                    for row in rows:
                        cols = ", ".join([f"`{k}`" for k in row.keys()])
                        vals = []
                        for v in row.values():
                            if v is None:
                                vals.append("NULL")
                            elif isinstance(v, (int, float)):
                                vals.append(str(v))
                            elif isinstance(v, (datetime.datetime, datetime.date)):
                                vals.append(f"'{v}'")
                            elif isinstance(v, bytes):
                                vals.append(f"0x{v.hex()}")
                            else:
                                escaped = str(v).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r")
                                vals.append(f"'{escaped}'")
                        val_str = ", ".join(vals)
                        f.write(f"INSERT INTO `{table}` ({cols}) VALUES ({val_str});\n")
                    f.write("UNLOCK TABLES;\n\n")

        f.write("SET FOREIGN_KEY_CHECKS=1;\n")

    conn.close()
    file_size_kb = round(os.path.getsize(backup_file) / 1024, 1)
    print(f"[OK] Database successfully dumped to {backup_file} ({file_size_kb} KB)")

if __name__ == "__main__":
    dump_db()

