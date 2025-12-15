CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    description TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    city TEXT,
    date TEXT NOT NULL,
    status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    city TEXT NOT NULL,
    role TEXT DEFAULT 'super_admin'
);

-- import sqlite3

-- conn = sqlite3.connect("database.db")
-- conn.executescript(open("schema.sql").read())
-- conn.close()

-- print("Database initialized successfully!")
