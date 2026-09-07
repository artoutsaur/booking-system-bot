import psycopg2
from psycopg2 import Error
from config import DB_CONFIG
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.create_tables()
        self.update_tables()

    def create_tables(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(100),
                    is_admin BOOLEAN DEFAULT FALSE,
                    is_super_admin BOOLEAN DEFAULT FALSE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS workplaces (
                    workplace_id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    booking_id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    workplace_id INTEGER REFERENCES workplaces(workplace_id),
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    log_id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    action VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.commit()

    def update_tables(self):
        """Обновляет структуру таблиц, добавляя новые столбцы"""
        with self.conn.cursor() as cur:
            try:
                cur.execute("""
                    ALTER TABLE users 
                    ADD COLUMN IF NOT EXISTS username VARCHAR(100)
                """)
                self.conn.commit()
            except Exception as e:
                logger.error(f"Ошибка при обновлении таблиц: {e}")
                self.conn.rollback()

    def add_user(self, user_id, username=None, is_admin=False, is_super_admin=False):
        """Добавляет пользователя в систему"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, username, is_admin, is_super_admin)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username
            """, (user_id, username, is_admin, is_super_admin))
            self.conn.commit()

    def get_user(self, user_id):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, username, is_admin, is_super_admin 
                FROM users 
                WHERE user_id = %s
            """, (user_id,))
            return cur.fetchone()

    def is_admin(self, user_id):
        """Проверяет, является ли пользователь администратором"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT is_admin FROM users WHERE user_id = %s
            """, (user_id,))
            result = cur.fetchone()
            return result[0] if result else False

    def is_super_admin(self, user_id):
        """Проверяет, является ли пользователь супер-админом"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT is_super_admin FROM users WHERE user_id = %s
            """, (user_id,))
            result = cur.fetchone()
            return result[0] if result else False

    def add_workplace(self, name):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO workplaces (name)
                VALUES (%s)
                RETURNING workplace_id
            """, (name,))
            workplace_id = cur.fetchone()[0]
            self.conn.commit()
            return workplace_id

    def get_workplaces(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT workplace_id, name FROM workplaces
            """)
            return cur.fetchall()

    def delete_workplace(self, workplace_id, force=False):
        """Удаляет рабочее место
        :param workplace_id: ID рабочего места
        :param force: Если True, удалит и все связанные бронирования
        :return: Имя удаленного рабочего места или None
        """
        with self.conn.cursor() as cur:
            try:
                if force:
                    # Удаляем все бронирования для этого места
                    cur.execute("""
                        DELETE FROM bookings
                        WHERE workplace_id = %s
                    """, (workplace_id,))
                
                # Удаляем само рабочее место
                cur.execute("""
                    DELETE FROM workplaces
                    WHERE workplace_id = %s
                    RETURNING name
                """, (workplace_id,))
                
                result = cur.fetchone()
                self.conn.commit()
                return result[0] if result else None
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Ошибка при удалении рабочего места: {e}")
                return None

    def create_booking(self, user_id, workplace_id, start_date, end_date):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM bookings
                WHERE workplace_id = %s
                AND (start_date, end_date) OVERLAPS (%s, %s)
            """, (workplace_id, start_date, end_date))
            if cur.fetchone():
                return None
                
            cur.execute("""
                INSERT INTO bookings (user_id, workplace_id, start_date, end_date)
                VALUES (%s, %s, %s, %s)
                RETURNING booking_id
            """, (user_id, workplace_id, start_date, end_date))
            booking_id = cur.fetchone()[0]
            self.conn.commit()
            return booking_id

    def get_user_bookings(self, user_id):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT b.booking_id, w.name, b.start_date, b.end_date
                FROM bookings b
                JOIN workplaces w ON b.workplace_id = w.workplace_id
                WHERE b.user_id = %s
            """, (user_id,))
            return cur.fetchall()

    def get_all_bookings(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT b.booking_id, u.user_id, u.username, w.name, b.start_date, b.end_date
                FROM bookings b
                JOIN users u ON b.user_id = u.user_id
                JOIN workplaces w ON b.workplace_id = w.workplace_id
            """)
            return cur.fetchall()

    def cancel_booking(self, booking_id, user_id=None, is_admin=False):
        with self.conn.cursor() as cur:
            if is_admin:
                cur.execute("""
                    DELETE FROM bookings
                    WHERE booking_id = %s
                """, (booking_id,))
            else:
                cur.execute("""
                    DELETE FROM bookings
                    WHERE booking_id = %s AND user_id = %s
                """, (booking_id, user_id))
            self.conn.commit()
            return cur.rowcount > 0

    def add_admin(self, user_id, is_super_admin=False):
        """Добавляет или обновляет администратора"""
        with self.conn.cursor() as cur:
            # Сначала добавляем пользователя, если его нет
            cur.execute("""
                INSERT INTO users (user_id) 
                VALUES (%s) 
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id,))
            # Затем назначаем администратором
            cur.execute("""
                UPDATE users 
                SET is_admin = TRUE, is_super_admin = %s 
                WHERE user_id = %s
            """, (is_super_admin, user_id))
            self.conn.commit()
            return cur.rowcount > 0

    def remove_admin(self, user_id):
        """Удаляет права администратора"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE users 
                SET is_admin = FALSE, is_super_admin = FALSE 
                WHERE user_id = %s
            """, (user_id,))
            self.conn.commit()
            return cur.rowcount > 0

    def get_admins(self):
        """Получает список всех администраторов"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, username, is_super_admin 
                FROM users 
                WHERE is_admin = TRUE
                ORDER BY is_super_admin DESC, user_id
            """)
            return cur.fetchall()

    def get_statistics(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bookings")
            total_bookings = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(DISTINCT user_id) FROM bookings")
            unique_users = cur.fetchone()[0]
            
            cur.execute("""
                SELECT w.name, COUNT(b.workplace_id) as bookings_count
                FROM workplaces w
                LEFT JOIN bookings b ON w.workplace_id = b.workplace_id
                GROUP BY w.name
                ORDER BY bookings_count DESC
                LIMIT 5
            """)
            popular_workplaces = cur.fetchall()
            
            return {
                'total_bookings': total_bookings,
                'unique_users': unique_users,
                'popular_workplaces': popular_workplaces
            }

    def has_bookings_for_workplace(self, workplace_id):
        """Проверяет, есть ли бронирования для указанного рабочего места"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM bookings
                WHERE workplace_id = %s
            """, (workplace_id,))
            return cur.fetchone()[0] > 0

    def log_action(self, user_id, action):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO logs (user_id, action)
                VALUES (%s, %s)
            """, (user_id, action))
            self.conn.commit()

    def is_first_user(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            return cur.fetchone()[0] == 0

    def close(self):
        if self.conn:
            self.conn.close()