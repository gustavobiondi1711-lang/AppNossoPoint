from cs50 import SQL
import os
import shutil

DATABASE_PATH = "/data/dados.db"
if not os.path.exists(DATABASE_PATH):
    shutil.copy("dados.db", DATABASE_PATH)
    db = SQL("sqlite:///" + DATABASE_PATH)

db.execute('''CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    token TEXT NOT NULL,
    cargo TEXT NOT NULL
);
''')

print(db.execute('SELECT * FROM tokens'))