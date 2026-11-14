import os
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2 import pool

from app.config import FREE_LIMIT, LIMIT_WAIT_SECONDS

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

    # "username" ustunida endi ikki xil qiymat saqlanadi:
    #   - ochiq kanal:  @kanal_username
    #   - maxfiy kanal: -1001234567890 (kanal ID raqami)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE
        )
    """)

    # Eski bazani buzmasdan yangi ustunlarni qo'shamiz
    cursor.execute("ALTER TABLE channels ADD COLUMN IF NOT EXISTS invite_link TEXT")
    cursor.execute("ALTER TABLE channels ADD COLUMN IF NOT EXISTS title TEXT")

    # VIP va limit tizimi uchun yangi ustunlar (eski ma'lumotlar saqlanib qoladi)
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS downloads_count INTEGER DEFAULT 0")
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS limit_started_at TIMESTAMPTZ")
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS vip_until TIMESTAMPTZ")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vip_payments (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            check_file_id TEXT,
            status TEXT,
            auto BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
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


def add_channel(identifier, invite_link=None, title=None):
    """
    identifier: '@username' (ochiq kanal) yoki '-100...' (maxfiy kanal ID si)
    invite_link: maxfiy kanal uchun taklif havolasi (https://t.me/+...)
    title: kanal nomi (tugmada ko'rsatish uchun)
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO channels (username, invite_link, title)
        VALUES (%s, %s, %s)
        ON CONFLICT (username) DO UPDATE
        SET invite_link = EXCLUDED.invite_link, title = EXCLUDED.title
    """, (identifier, invite_link, title))
    conn.commit()
    release_connection(conn)
    return True


def delete_channel(identifier):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE username = %s", (identifier,))
    deleted = cursor.rowcount
    conn.commit()
    release_connection(conn)
    return deleted > 0


def get_all_channels():
    """Faqat identifikatorlar ro'yxati (eski kod bilan mos)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM channels ORDER BY id")
    channels = cursor.fetchall()
    release_connection(conn)
    return [channel[0] for channel in channels]


def get_all_channels_full():
    """[(identifier, invite_link, title), ...]"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, invite_link, title FROM channels ORDER BY id")
    rows = cursor.fetchall()
    release_connection(conn)
    return rows


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


# ======================= VIP VA LIMIT =======================

def _now():
    return datetime.now(timezone.utc)


def _ensure_user(cursor, telegram_id, full_name=""):
    cursor.execute("""
        INSERT INTO users (telegram_id, full_name)
        VALUES (%s, %s)
        ON CONFLICT (telegram_id) DO NOTHING
    """, (telegram_id, full_name))


def get_vip_until(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT vip_until FROM users WHERE telegram_id = %s", (telegram_id,))
    row = cursor.fetchone()
    release_connection(conn)
    return row[0] if row else None


def is_vip(telegram_id):
    until = get_vip_until(telegram_id)
    return bool(until and until > _now())


def try_consume_download(telegram_id, full_name=""):
    """
    Kino yuborishdan OLDIN chaqiriladi.
    Qaytaradi: (ruxsat_bormi, kutish_soniyasi)

    - VIP bo'lsa: cheksiz, hisoblanmaydi
    - Bepul: FREE_LIMIT tagacha video; keyingi (4-) so'rovda 1 soatlik hisob boshlanadi
    - Soat o'tgach hisob nolga tushadi
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        _ensure_user(cursor, telegram_id, full_name)

        cursor.execute("""
            SELECT COALESCE(downloads_count, 0), limit_started_at, vip_until
            FROM users WHERE telegram_id = %s FOR UPDATE
        """, (telegram_id,))
        count, started, vip_until = cursor.fetchone()
        now = _now()

        # VIP faol
        if vip_until and vip_until > now:
            conn.commit()
            return True, 0

        # Kutish davri ketyapti
        if started is not None:
            elapsed = (now - started).total_seconds()
            if elapsed < LIMIT_WAIT_SECONDS:
                conn.commit()
                return False, int(LIMIT_WAIT_SECONDS - elapsed)

            # Soat o'tdi: hisobni nolga tushiramiz
            count = 0
            cursor.execute("""
                UPDATE users SET downloads_count = 0, limit_started_at = NULL
                WHERE telegram_id = %s
            """, (telegram_id,))

        # Limit tugagan, bu 4-so'rov: hisobni shu paytdan boshlaymiz
        if count >= FREE_LIMIT:
            cursor.execute("""
                UPDATE users SET limit_started_at = %s WHERE telegram_id = %s
            """, (now, telegram_id))
            conn.commit()
            return False, LIMIT_WAIT_SECONDS

        # Ruxsat: bitta videoni hisoblaymiz
        cursor.execute("""
            UPDATE users SET downloads_count = COALESCE(downloads_count, 0) + 1
            WHERE telegram_id = %s
        """, (telegram_id,))
        conn.commit()
        return True, 0

    except Exception:
        conn.rollback()
        raise
    finally:
        release_connection(conn)


def refund_download(telegram_id):
    """Video yuborilmay qolsa (xatolik), hisoblangan videoni qaytaramiz"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET downloads_count = GREATEST(COALESCE(downloads_count, 0) - 1, 0)
        WHERE telegram_id = %s
    """, (telegram_id,))
    conn.commit()
    release_connection(conn)


def grant_vip(telegram_id, hours=24):
    """VIP beradi. Allaqachon VIP bo'lsa, muddat ustiga qo'shiladi. Yangi tugash vaqtini qaytaradi."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        _ensure_user(cursor, telegram_id)
        cursor.execute(
            "SELECT vip_until FROM users WHERE telegram_id = %s FOR UPDATE",
            (telegram_id,)
        )
        current = cursor.fetchone()[0]
        now = _now()
        base = current if (current and current > now) else now
        new_until = base + timedelta(hours=hours)
        cursor.execute(
            "UPDATE users SET vip_until = %s WHERE telegram_id = %s",
            (new_until, telegram_id)
        )
        conn.commit()
        return new_until
    except Exception:
        conn.rollback()
        raise
    finally:
        release_connection(conn)


def revoke_vip(telegram_id, hours=24):
    """Bitta to'lov uchun berilgan VIP muddatini ayirib tashlaydi"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT vip_until FROM users WHERE telegram_id = %s FOR UPDATE",
            (telegram_id,)
        )
        row = cursor.fetchone()
        if not row or row[0] is None:
            conn.commit()
            return
        new_until = row[0] - timedelta(hours=hours)
        if new_until <= _now():
            new_until = None
        cursor.execute(
            "UPDATE users SET vip_until = %s WHERE telegram_id = %s",
            (new_until, telegram_id)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_connection(conn)


def create_payment(user_id, check_file_id, status, auto=False):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO vip_payments (user_id, check_file_id, status, auto)
        VALUES (%s, %s, %s, %s) RETURNING id
    """, (user_id, check_file_id, status, auto))
    payment_id = cursor.fetchone()[0]
    conn.commit()
    release_connection(conn)
    return payment_id


def update_payment_status(payment_id, new_status, from_statuses):
    """
    Chek holatini faqat from_statuses ichida bo'lsa o'zgartiradi
    (ikki marta bosib yuborishdan himoya). user_id yoki None qaytaradi.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE vip_payments SET status = %s
        WHERE id = %s AND status = ANY(%s)
        RETURNING user_id
    """, (new_status, payment_id, list(from_statuses)))
    row = cursor.fetchone()
    conn.commit()
    release_connection(conn)
    return row[0] if row else None


def has_recent_auto_approval(user_id, hours=8):
    """Oxirgi 'hours' soatda shu foydalanuvchiga avto-tasdiq berilganmi (tun oralig'i 8 soat)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM vip_payments
        WHERE user_id = %s AND auto = TRUE AND created_at > %s
    """, (user_id, _now() - timedelta(hours=hours)))
    count = cursor.fetchone()[0]
    release_connection(conn)
    return count > 0
