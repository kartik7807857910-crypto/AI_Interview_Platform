import sqlite3


def create_database():

    connection = sqlite3.connect("users.db")

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


def add_user(name, email, password, role): # type: ignore

    connection = sqlite3.connect("users.db")

    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO users (name, email, password, role)
        VALUES (?, ?, ?, ?)
    """, (name, email, password, role)) # type: ignore

    connection.commit()
    connection.close()


def check_user(email, password): # type: ignore

    connection = sqlite3.connect("users.db")

    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM users
        WHERE email = ? AND password = ?
    """, (email, password)) # type: ignore

    user = cursor.fetchone()

    connection.close()

    return user