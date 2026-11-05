#!/usr/bin/python3
# Copies the old users.sqlite database into the MySQL user database.
# Run once by setup/mail-users.sh on upgrade. Ids are kept so mfa.user_id
# still points at the right user. Everything is one transaction: on any
# error nothing is written and users.sqlite is left in place.
#
# Usage: sqlite-to-mysql.py /path/to/users.sqlite /etc/mailinabox-mysql.password

import sqlite3, sys
import pymysql

TABLES = {
	# parents before children (mfa references users)
	"users": ["id", "email", "password", "extra", "privileges", "quota"],
	"aliases": ["id", "source", "destination", "permitted_senders"],
	"auto_aliases": ["id", "source", "destination", "permitted_senders"],
	"mfa": ["id", "user_id", "type", "secret", "mru_token", "label"],
}

def main(sqlite_path, password_file):
	src = sqlite3.connect(sqlite_path)
	with open(password_file, encoding="utf-8") as f:
		password = f.read().strip()
	dst = pymysql.connect(host="127.0.0.1", user="mailinabox", password=password,
		database="mailinabox", charset="utf8mb4", autocommit=False)
	c = dst.cursor()

	# Refuse to merge into a database that already has data.
	for table in TABLES:
		c.execute(f"SELECT COUNT(*) FROM {table}")
		if c.fetchone()[0]:
			sys.exit(f"MySQL table {table} is not empty, not copying {sqlite_path}.")

	try:
		for table, cols in TABLES.items():
			sql = f"SELECT {', '.join(cols)} FROM {table}"
			if table == "mfa":
				# SQLite never enforced the foreign key, so drop rows for deleted users.
				sql += " WHERE user_id IN (SELECT id FROM users)"
			rows = src.execute(sql).fetchall()
			if rows:
				c.executemany(
					f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
					rows)
			print(f"{table}: {len(rows)} rows")
		dst.commit()
	except Exception:
		dst.rollback()
		raise

if __name__ == "__main__":
	if len(sys.argv) != 3:
		sys.exit("usage: sqlite-to-mysql.py users.sqlite password-file")
	main(sys.argv[1], sys.argv[2])
