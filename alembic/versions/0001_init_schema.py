"""init schema

Revision ID: 0001
Revises: 
Create Date: 2025-09-03 18:00:00
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # users
    op.execute(
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

    # complaints
    op.execute(
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

    # likes
    op.execute(
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

    # likes_inbox
    op.execute(
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

    # views
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS views (
            id SERIAL PRIMARY KEY,
            viewer_id BIGINT NOT NULL,
            viewed_id BIGINT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    )

    # payments
    op.execute(
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

    # app_settings
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )

    # indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_city ON users(city);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_norm_city ON users(normalized_city);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_gender_interest ON users(gender_interest);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_complaints_reported_id ON complaints(reported_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_complaints_reporter_id ON complaints(reporter_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_views_viewer_id ON views(viewer_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_views_viewed_id ON views(viewed_id);")


def downgrade():
    # safe drop (optional)
    pass
