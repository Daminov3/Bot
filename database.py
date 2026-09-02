import os
import psycopg2
from psycopg2 import pool

print("DATABASE.PY (SUPABASE POSTGRESQL) ISHLADI")

# Render paneliga kiritgan havolamizni oladi
DATABASE_URL = os.getenv("DATABASE_URL")

connection_pool = pool.SimpleConnectionPool(
    1,
    10,
    DATABASE_URL
)


def get_connection():
    return connection_pool.getconn()


def release_connection(conn):
    if conn:
        connection_pool.putconn(conn)
def create_tables():
    print("create_tables ishga tushdi")
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE,
            full_name TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id SERIAL PRIMARY KEY,
            movie_code INTEGER UNIQUE,
            title TEXT,
            file_id TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE
        )
    """)

    conn.commit()
    release_connection(conn)

    print("Onlayn ma'lumotlar bazasi jadvallari tayyor!")

def add_user(telegram_id, full_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users (telegram_id, full_name)
        VALUES (%s, %s)
        ON CONFLICT (telegram_id) DO NOTHING
    """, (telegram_id, full_name))

    conn.commit()
    release_connection(conn)

    print(f"Yangi user onlayn bazaga qo'shildi: {telegram_id}")

def add_movie(movie_code, title, file_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO movies (movie_code, title, file_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (movie_code) DO UPDATE SET title = EXCLUDED.title, file_id = EXCLUDED.file_id
    """, (movie_code, title, file_id))

    conn.commit()
    release_connection(conn)

    print(f"Kino onlayn bazaga qo'shildi: {movie_code} - {title}")

def get_movie(movie_code):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT title, file_id FROM movies WHERE movie_code = %s
    """, (movie_code,))

    movie = cursor.fetchone()

    release_connection(conn)

    return movie

def get_all_movies():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT movie_code, title FROM movies ORDER BY movie_code
    """)
    movies = cursor.fetchall()
    release_connection(conn)
    return movies

def delete_movie(movie_code):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movies WHERE movie_code = %s", (movie_code,))
    deleted = cursor.rowcount
    conn.commit()
    release_connection(conn)
    return deleted > 0

def get_users_count():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    release_connection(conn)
    return count

def get_movies_count():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM movies")
    count = cursor.fetchone()[0]
    release_connection(conn)
    return count

def add_channel(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO channels (username) VALUES (%s) ON CONFLICT (username) DO NOTHING", (username,))
    conn.commit()
    release_connection(conn)
    return True

def delete_channel(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE username = %s", (username,))
    deleted = cursor.rowcount
    conn.commit()
    release_connection(conn)
    return deleted > 0

def get_all_channels():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM channels ORDER BY id")
    channels = cursor.fetchall()
    release_connection(conn)
    return [channel[0] for channel in channels]

def get_all_movies_txt():
    conn = get_connection() 
    cursor = conn.cursor()
    cursor.execute("SELECT movie_code, title, file_id FROM movies ORDER BY movie_code")
    rows = cursor.fetchall()
    release_connection(conn)
    
    file_path = "backup_movies.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("=== KINO FILE ID BACKUP ===\n\n")
        for row in rows:
            f.write(f"Kino Kodi: {row[0]} | Nomi: {row[1]} | File ID: {row[2]}\n")
            f.write("-" * 40 + "\n")
    return file_path
