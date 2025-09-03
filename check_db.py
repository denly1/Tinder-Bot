import psycopg2
from psycopg2 import OperationalError

def check_db_connection():
    try:
        conn = psycopg2.connect(
            dbname="baza_tinder",
            user="postgres",
            password="1",
            host="localhost",
            port="5432"
        )
        conn.close()
        print("Подключение к базе данных успешно!")
        return True
    except OperationalError as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return False

if __name__ == "__main__":
    check_db_connection()
