import os
import logging
from datetime import date, datetime
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Параметры БД можно переопределить через переменные окружения
DB_NAME = os.getenv("PGDATABASE", "baza_tinder")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "1")
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = int(os.getenv("PGPORT", "5432"))


def get_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        cursor_factory=RealDictCursor,
    )


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Таблица пользователей (строго по ТЗ)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                age INT CHECK (age BETWEEN 18 AND 99),
                city TEXT NOT NULL,
                normalized_city TEXT,
                gender TEXT,
                bio TEXT,
                gender_interest TEXT NOT NULL,
                interests TEXT[] NOT NULL,
                photos TEXT[] NOT NULL DEFAULT '{}',
                videos TEXT[] NOT NULL DEFAULT '{}',
                smoking TEXT DEFAULT NULL,
                drinking TEXT DEFAULT NULL,
                relationship TEXT DEFAULT NULL,
                vip BOOLEAN DEFAULT FALSE,
                vip_until TIMESTAMP DEFAULT NULL,
                blocked BOOLEAN DEFAULT FALSE,
                daily_views INT DEFAULT 0,
                last_view DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_active_at TIMESTAMP DEFAULT NOW(),
                age_min_preference INT,
                age_max_preference INT,
                city_filter_enabled BOOLEAN DEFAULT TRUE
            );
            """
        )

        # Таблица жалоб
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS complaints (
                id SERIAL PRIMARY KEY,
                reporter_id BIGINT NOT NULL,
                reported_id BIGINT NOT NULL,
                reason TEXT DEFAULT 'Жалоба от пользователя',
                created_at TIMESTAMP DEFAULT NOW()
            );
            """
        )

        # Таблица симпатий (лайков)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS likes (
                id SERIAL PRIMARY KEY,
                from_user BIGINT NOT NULL,
                to_user BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (from_user, to_user)
            );
            """
        )

        # Входящие симпатии (очередь на просмотр)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS likes_inbox (
                id SERIAL PRIMARY KEY,
                to_user BIGINT NOT NULL,
                from_user BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                seen BOOLEAN DEFAULT FALSE,
                UNIQUE (to_user, from_user)
            );
            """
        )

        # История просмотров (для админ-панели)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS views (
                id SERIAL PRIMARY KEY,
                viewer_id BIGINT NOT NULL,
                viewed_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """
        )

        # Платежи (YooKassa)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                payment_id TEXT UNIQUE NOT NULL,
                user_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL DEFAULT 'RUB',
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP DEFAULT NULL
            );
            """
        )

        # Индексы для ускорения
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_city ON users(city);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_norm_city ON users(normalized_city);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_gender_interest ON users(gender_interest);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_complaints_reported_id ON complaints(reported_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_complaints_reporter_id ON complaints(reporter_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_views_viewer_id ON views(viewer_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_views_viewed_id ON views(viewed_id);")

        # Миграции для уже существующей БД (добавление недостающих колонок)
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS normalized_city TEXT;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS gender TEXT;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP DEFAULT NOW();")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS age_min_preference INT;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS age_max_preference INT;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS city_filter_enabled BOOLEAN DEFAULT TRUE;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS vip_until TIMESTAMP;")

        # Глобальные настройки приложения
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        conn.commit()
        logger.info("База данных и таблицы успешно инициализированы.")
    except Exception as e:
        logger.exception("Ошибка инициализации базы: %s", e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()


# --- CRUD и сервисные функции ---

def get_user(telegram_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE telegram_id=%s", (telegram_id,))
            return cur.fetchone()
    finally:
        conn.close()


def add_user(
    telegram_id: int,
    name: str,
    age: int,
    city: str,
    gender: str,
    gender_interest: str,
    interests: list,
    smoking: str = None,
    drinking: str = None,
    relationship: str = None,
):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (
                    telegram_id, name, age, city, gender, gender_interest, interests, smoking, drinking, relationship
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (telegram_id) DO UPDATE SET
                    name=EXCLUDED.name,
                    age=EXCLUDED.age,
                    city=EXCLUDED.city,
                    gender=EXCLUDED.gender,
                    gender_interest=EXCLUDED.gender_interest,
                    interests=EXCLUDED.interests,
                    smoking=EXCLUDED.smoking,
                    drinking=EXCLUDED.drinking,
                    relationship=EXCLUDED.relationship
                """,
                (
                    telegram_id,
                    name,
                    age,
                    city,
                    gender,
                    gender_interest,
                    interests,
                    smoking,
                    drinking,
                    relationship,
                ),
            )
        conn.commit()
        logger.info("User upserted: %s", telegram_id)
    finally:
        conn.close()


def update_user_photos(telegram_id: int, photos: list):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET photos=%s WHERE telegram_id=%s", (photos, telegram_id))
        conn.commit()
        logger.info("Updated photos for %s: %d items", telegram_id, len(photos or []))
    finally:
        conn.close()


def update_user_videos(telegram_id: int, videos: list):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET videos=%s WHERE telegram_id=%s", (videos, telegram_id))
        conn.commit()
        logger.info("Updated videos for %s: %d items", telegram_id, len(videos or []))
    finally:
        conn.close()


def is_blocked(telegram_id: int) -> bool:
    user = get_user(telegram_id)
    return bool(user and user.get("blocked"))


def set_vip(telegram_id: int, vip: bool):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET vip=%s WHERE telegram_id=%s", (vip, telegram_id))
        conn.commit()
        logger.info("Set VIP=%s for %s", vip, telegram_id)
    finally:
        conn.close()


def set_vip_until(telegram_id: int, until_dt: datetime):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET vip_until=%s, vip=TRUE WHERE telegram_id=%s", (until_dt, telegram_id))
        conn.commit()
        logger.info("Set VIP until %s for %s", until_dt, telegram_id)
    finally:
        conn.close()


def is_vip_active(telegram_id: int) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT vip, vip_until FROM users WHERE telegram_id=%s", (telegram_id,))
            row = cur.fetchone()
            if not row:
                return False
            if row.get("vip"):
                return True
            if row.get("vip_until") is None:
                return False
            cur.execute("SELECT NOW() < %s AS active", (row["vip_until"],))
            return bool(cur.fetchone()["active"])
    finally:
        conn.close()


def create_payment_record(payment_id: str, user_id: int, amount: int, currency: str = "RUB", status: str = "pending", expires_at: datetime | None = None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payments (payment_id, user_id, amount, currency, status, expires_at)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (payment_id) DO NOTHING
                """,
                (payment_id, user_id, amount, currency, status, expires_at),
            )
        conn.commit()
    finally:
        conn.close()


def update_payment_status(payment_id: str, status: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE payments SET status=%s WHERE payment_id=%s", (status, payment_id))
        conn.commit()
    finally:
        conn.close()


def set_blocked(telegram_id: int, blocked: bool):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET blocked=%s WHERE telegram_id=%s", (blocked, telegram_id))
        conn.commit()
        logger.info("Set BLOCKED=%s for %s", blocked, telegram_id)
    finally:
        conn.close()


def reset_daily_views_if_needed(telegram_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT daily_views, last_view, vip FROM users WHERE telegram_id=%s", (telegram_id,))
            row = cur.fetchone()
            if not row:
                return
            if row["vip"]:
                return
            today = date.today()
            if row["last_view"] is None or row["last_view"] < today:
                cur.execute(
                    "UPDATE users SET daily_views=0, last_view=%s WHERE telegram_id=%s",
                    (today, telegram_id),
                )
        conn.commit()
    finally:
        conn.close()


def can_increment_view(telegram_id: int, max_per_day: int = 10) -> bool:
    # Если глобально отключены ограничения — всегда можно
    if is_limits_disabled():
        return True
    reset_daily_views_if_needed(telegram_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT vip, vip_until, daily_views FROM users WHERE telegram_id=%s", (telegram_id,))
            row = cur.fetchone()
            if not row:
                return False
            # Активный VIP — либо флаг vip, либо vip_until в будущем
            if row["vip"]:
                return True
            if row.get("vip_until") is not None:
                try:
                    # сравнение по времени в БД
                    cur.execute("SELECT NOW() < %s AS active", (row["vip_until"],))
                    active = cur.fetchone()["active"]
                    if active:
                        return True
                except Exception:
                    pass
            return (row["daily_views"] or 0) < max_per_day
    finally:
        conn.close()


def increment_view(telegram_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET daily_views = COALESCE(daily_views,0) + 1, last_view = %s WHERE telegram_id=%s",
                (date.today(), telegram_id),
            )
        conn.commit()
    finally:
        conn.close()


def record_view(viewer_id: int, viewed_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO views (viewer_id, viewed_id) VALUES (%s,%s)",
                (viewer_id, viewed_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_next_profile_for_user(current_user_id: int):
    """Выдаёт следующий профиль с учётом возрастных и городских фильтров сFallback."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Получим предпочтения текущего пользователя
            cur.execute(
                """
                SELECT age, city, normalized_city, age_min_preference, age_max_preference, city_filter_enabled, gender_interest
                FROM users WHERE telegram_id=%s AND blocked=FALSE
                """,
                (current_user_id,),
            )
            me = cur.fetchone()
            if not me:
                return None
            # Нормализуем город пользователя при необходимости
            my_norm_city = me.get("normalized_city")
            if not my_norm_city and me.get("city"):
                my_norm_city = normalize_city_str(me.get("city"))
                cur.execute("UPDATE users SET normalized_city=%s WHERE telegram_id=%s", (my_norm_city, current_user_id))

            # Возрастной коридор по умолчанию: возраст ±3, но не младше 18
            my_age = me.get("age") or 18
            min_age = me.get("age_min_preference") or max(18, my_age - 3)
            max_age = me.get("age_max_preference") or (my_age + 3)
            city_enabled = bool(me.get("city_filter_enabled") if me.get("city_filter_enabled") is not None else True)

            # Фильтр по полу искомого партнёра
            gi = (me.get("gender_interest") or "Без разницы")
            gender_filter = None
            if gi.startswith("Парни"):
                gender_filter = "Парень"
            elif gi.startswith("Девушки"):
                gender_filter = "Девушка"

            params = {
                "me": current_user_id,
                "min_age": min_age,
                "max_age": max_age,
                "norm_city": my_norm_city or None,
                "gender": gender_filter,
            }

            # 1) тот же город + возрастной фильтр
            if city_enabled and my_norm_city:
                if gender_filter:
                    cur.execute(
                        """
                        SELECT * FROM users
                        WHERE telegram_id <> %(me)s
                          AND blocked = FALSE
                          AND age BETWEEN %(min_age)s AND %(max_age)s
                          AND COALESCE(normalized_city, LOWER(city)) = %(norm_city)s
                          AND gender = %(gender)s
                        ORDER BY vip DESC, RANDOM() LIMIT 1
                        """,
                        params,
                    )
                else:
                    cur.execute(
                        """
                        SELECT * FROM users
                        WHERE telegram_id <> %(me)s
                          AND blocked = FALSE
                          AND age BETWEEN %(min_age)s AND %(max_age)s
                          AND COALESCE(normalized_city, LOWER(city)) = %(norm_city)s
                        ORDER BY vip DESC, RANDOM() LIMIT 1
                        """,
                        params,
                    )
                row = cur.fetchone()
                if row:
                    return row

            # 2) другие города + возрастной фильтр
            if gender_filter:
                cur.execute(
                    """
                    SELECT * FROM users
                    WHERE telegram_id <> %(me)s
                      AND blocked = FALSE
                      AND age BETWEEN %(min_age)s AND %(max_age)s
                      AND gender = %(gender)s
                    ORDER BY vip DESC, RANDOM() LIMIT 1
                    """,
                    params,
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM users
                    WHERE telegram_id <> %(me)s
                      AND blocked = FALSE
                      AND age BETWEEN %(min_age)s AND %(max_age)s
                    ORDER BY vip DESC, RANDOM() LIMIT 1
                    """,
                    params,
                )
            row = cur.fetchone()
            if row:
                return row

            # 3) любой подходящий пользователь без возрастного фильтра как последний шанс
            if gender_filter:
                cur.execute(
                    """
                    SELECT * FROM users
                    WHERE telegram_id <> %(me)s
                      AND blocked = FALSE
                      AND gender = %(gender)s
                    ORDER BY vip DESC, RANDOM() LIMIT 1
                    """,
                    params,
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM users
                    WHERE telegram_id <> %(me)s
                      AND blocked = FALSE
                    ORDER BY vip DESC, RANDOM() LIMIT 1
                    """,
                    params,
                )
            return cur.fetchone()
    finally:
        conn.close()

# --- Вспомогательные функции настроек и нормализации ---

def normalize_city_str(s: str) -> str:
    if not s:
        return None
    s = s.strip().lower()
    # простая нормализация: ё->е, множественные пробелы
    s = s.replace("ё", "е")
    s = " ".join(s.split())
    return s

def touch_last_active(telegram_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET last_active_at=NOW() WHERE telegram_id=%s", (telegram_id,))
        conn.commit()
    finally:
        conn.close()

def set_age_preference(telegram_id: int, min_age: int, max_age: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET age_min_preference=%s, age_max_preference=%s WHERE telegram_id=%s",
                (min_age, max_age, telegram_id),
            )
        conn.commit()
    finally:
        conn.close()

def set_city_filter_enabled(telegram_id: int, enabled: bool):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET city_filter_enabled=%s WHERE telegram_id=%s", (enabled, telegram_id))
        conn.commit()
    finally:
        conn.close()

def set_user_city(telegram_id: int, city: str):
    norm = normalize_city_str(city)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET city=%s, normalized_city=%s WHERE telegram_id=%s", (city, norm, telegram_id))
        conn.commit()
    finally:
        conn.close()

def get_app_setting(key: str, default: str = None) -> str:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM app_settings WHERE key=%s", (key,))
            row = cur.fetchone()
            return (row and row.get("value")) or default
    finally:
        conn.close()

def set_app_setting(key: str, value: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
                (key, value),
            )
        conn.commit()
    finally:
        conn.close()

def is_limits_disabled() -> bool:
    v = get_app_setting("limits_disabled", "false")
    return str(v).lower() in ("1", "true", "yes")


def add_like(from_user: int, to_user: int) -> bool:
    """Возвращает True, если получилась взаимная симпатия."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("INSERT INTO likes (from_user, to_user) VALUES (%s,%s)", (from_user, to_user))
            except Exception:
                # дубликат — игнорируем
                pass
            # Добавим запись во входящие для получателя лайка (если ещё нет)
            try:
                cur.execute(
                    "INSERT INTO likes_inbox (to_user, from_user) VALUES (%s,%s) ON CONFLICT (to_user, from_user) DO NOTHING",
                    (to_user, from_user),
                )
            except Exception:
                pass
            cur.execute("SELECT 1 FROM likes WHERE from_user=%s AND to_user=%s", (to_user, from_user))
            mutual = cur.fetchone() is not None
        conn.commit()
        if mutual:
            logger.info("Mutual like between %s and %s", from_user, to_user)
        else:
            logger.info("Like from %s to %s", from_user, to_user)
        return mutual
    finally:
        conn.close()


def get_new_likes(telegram_id: int) -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT from_user, created_at FROM likes WHERE to_user=%s ORDER BY created_at DESC LIMIT 50",
                (telegram_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def get_unseen_likes(telegram_id: int) -> list:
    """Вернёт список входящих лайков (from_user, created_at), которые ещё не просмотрены пользователем."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT from_user, created_at FROM likes_inbox WHERE to_user=%s AND seen=FALSE ORDER BY created_at ASC",
                (telegram_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def mark_inbox_seen(to_user: int, from_user: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE likes_inbox SET seen=TRUE WHERE to_user=%s AND from_user=%s",
                (to_user, from_user),
            )
        conn.commit()
    finally:
        conn.close()


def count_unseen_likes(telegram_id: int) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM likes_inbox WHERE to_user=%s AND seen=FALSE", (telegram_id,))
            row = cur.fetchone()
            return int(row["c"]) if row else 0
    finally:
        conn.close()


def add_complaint(reporter_id: int, reported_id: int, reason: str = "Жалоба от пользователя"):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO complaints (reporter_id, reported_id, reason) VALUES (%s,%s,%s)",
                (reporter_id, reported_id, reason),
            )
        conn.commit()
        logger.info("Complaint: reporter=%s reported=%s reason=%s", reporter_id, reported_id, reason)
    finally:
        conn.close()


def list_complaints(limit: int = 50) -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, reporter_id, reported_id, reason, created_at FROM complaints ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def list_users_for_csv():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    telegram_id,
                    name,
                    age,
                    city,
                    gender_interest,
                    interests,
                    smoking,
                    drinking,
                    relationship,
                    vip,
                    blocked,
                    last_view,
                    daily_views,
                    COALESCE(array_length(photos, 1), 0) AS photos_count,
                    COALESCE(array_length(videos, 1), 0) AS videos_count
                FROM users
                ORDER BY id
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


def list_active_user_ids() -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT telegram_id FROM users WHERE blocked = FALSE")
            rows = cur.fetchall()
            return [r["telegram_id"] for r in rows]
    finally:
        conn.close()


def update_user_field(telegram_id: int, field: str, value):
    allowed = {"name", "age", "city", "gender_interest", "bio"}
    if field not in allowed:
        raise ValueError("Unsupported field")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE users SET {field}=%s WHERE telegram_id=%s", (value, telegram_id))
        conn.commit()
        logger.info("Updated %s for %s", field, telegram_id)
    finally:
        conn.close()


def update_user_interests(telegram_id: int, interests: list):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET interests=%s WHERE telegram_id=%s", (interests, telegram_id))
        conn.commit()
        logger.info("Updated interests for %s: %d items", telegram_id, len(interests or []))
    finally:
        conn.close()


def delete_user(telegram_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # удалить связанные записи
            cur.execute("DELETE FROM likes WHERE from_user=%s OR to_user=%s", (telegram_id, telegram_id))
            cur.execute("DELETE FROM complaints WHERE reporter_id=%s OR reported_id=%s", (telegram_id, telegram_id))
            cur.execute("DELETE FROM views WHERE viewer_id=%s OR viewed_id=%s", (telegram_id, telegram_id))
            # очистить пользователя
            cur.execute("DELETE FROM users WHERE telegram_id=%s", (telegram_id,))
        conn.commit()
        logger.info("Deleted user %s", telegram_id)
    finally:
        conn.close()
