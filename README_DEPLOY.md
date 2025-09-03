# Деплой Telegram-бота на Ubuntu 22.04 (IP 5.129.201.9) с автообновлением через GitHub Actions + systemd + Alembic

Ниже пошаговая инструкция и необходимые файлы в репозитории. Итог: пуш в ветку `main` автоматически разворачивается на сервере, перезапускает сервис и выполняет миграции БД.

## 1) Что будет установлено/использовано
- Python 3.10+ и virtualenv (venv)
- PostgreSQL 14+
- Alembic (миграции)
- systemd (сервис бота)
- GitHub Actions (CI/CD), SSH-доступ на сервер

## 2) Подготовка сервера (Ubuntu)
Выполнить на сервере 5.129.201.9 под пользователем с sudo (например, `ubuntu`):

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git postgresql postgresql-contrib
```

Создайте БД и пользователя в PostgreSQL:
```bash
sudo -u postgres psql <<'SQL'
CREATE USER tin_bot WITH PASSWORD 'strong_password';
CREATE DATABASE baza_tinder OWNER tin_bot;
GRANT ALL PRIVILEGES ON DATABASE baza_tinder TO tin_bot;
SQL
```

Создайте директории приложения и логов:
```bash
sudo mkdir -p /opt/tin-bot
sudo mkdir -p /var/log/tin-bot
sudo chown -R $USER:$USER /opt/tin-bot /var/log/tin-bot
```

Склонируйте репозиторий (после того как выложите на GitHub):
```bash
cd /opt/tin-bot
git clone https://github.com/<your-account>/<your-repo>.git .
python3 -m venv venv
./venv/bin/pip install -U pip
./venv/bin/pip install -r requirements.txt
```

Создайте файл окружения `/etc/tin-bot.env`:
```bash
sudo tee /etc/tin-bot.env >/dev/null <<'ENV'
TELEGRAM_TOKEN=Ваш_токен_бота
ADMIN_ID=825042510
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=baza_tinder
PGUSER=tin_bot
PGPASSWORD=strong_password
PYTHONUNBUFFERED=1
# Платёжные провайдеры (опционально)
# PAYMENT_PROVIDER_TOKEN=
# TRIBUTE_API_KEY=
ENV
sudo chmod 600 /etc/tin-bot.env
```

Установите systemd-сервис:
```bash
sudo cp systemd/tin-bot.service /etc/systemd/system/tin-bot.service
sudo systemctl daemon-reload
sudo systemctl enable tin-bot
sudo systemctl start tin-bot
sudo systemctl status tin-bot --no-pager
```

Проверьте логи:
```bash
journalctl -u tin-bot -f -n 200
```

## 3) Настройка GitHub Actions (CI/CD)
В репозитории уже есть workflow `.github/workflows/deploy.yml`.

В GitHub → Settings → Secrets and variables → Actions → Secrets:
- SSH_HOST = 5.129.201.9
- SSH_USER = ubuntu (или ваш пользователь на сервере)
- SSH_KEY = приватный ключ (начинается с `-----BEGIN OPENSSH PRIVATE KEY-----`)
- SSH_PORT = 22 (если нестандартный — укажите свой)

После каждого пуша в `main` Actions подключится по SSH и выполнит скрипт `deploy/deploy.sh`:
- `git pull`
- установка зависимостей
- `alembic upgrade head`
- перезапуск systemd-сервиса

## 4) Миграции Alembic
- Конфиг уже добавлен: `alembic.ini`, `alembic/env.py`, `alembic/versions/`.
- Начальная миграция создаёт текущие таблицы/индексы.
- Для новых изменений в БД:
  - создайте новую миграцию (локально):
    ```bash
    alembic revision -m "your change"
    # заполните upgrade()/downgrade()
    ```
  - запушьте в `main` → Actions применит на сервере `alembic upgrade head`.

## 5) Ручной перезапуск/деплой (опционально)
На сервере:
```bash
cd /opt/tin-bot
./deploy/deploy.sh
```

## 6) Примечания
- Бот читает параметры БД из переменных окружения (`PGHOST`, `PGUSER`, `PGPASSWORD`, и т.д.), см. `db.py`.
- Токен Telegram берём из `TELEGRAM_TOKEN`; при отсутствии — `main.py` завершит запуск с ошибкой.
- Логи systemd удобнее смотреть через `journalctl`.
- Если нужен nginx/https — можно добавить отдельно (не требуется для бота с polling).
