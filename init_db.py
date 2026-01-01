import psycopg2
import os

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:root@localhost/postgres')

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin INTEGER DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS shops (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    username TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    image TEXT NOT NULL,
    checked INTEGER DEFAULT 0,
    shown INTEGER DEFAULT 0
)
''')

conn.commit()
conn.close()
print("Database initialized!")
