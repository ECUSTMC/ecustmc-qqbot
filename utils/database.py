"""数据库工具模块"""
import sqlite3
from datetime import datetime
import random
import json
import os


def is_spring_festival() -> bool:
    """判断春节期间运势增强功能是否开启"""
    return os.getenv("SPRING_FESTIVAL_ENABLED", "false").lower() == "true"


def init_user_numbers_db():
    """初始化用户数字数据库"""
    conn = sqlite3.connect('user_numbers.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_numbers (
            user_id TEXT PRIMARY KEY,
            random_number INTEGER,
            number INTEGER,
            date TEXT
        )
    ''')
    conn.commit()
    return conn, cursor


def get_fortune_number(lucky_star):
    """根据幸运星象计算运势数字"""
    star_count = lucky_star.count('★')
    if star_count == 0:
        return random.randint(0, 10)
    elif star_count == 1:
        return random.randint(5, 15)
    elif star_count == 2:
        return random.randint(10, 25)
    elif star_count == 3:
        return random.randint(25, 40)
    elif star_count == 4:
        return random.randint(40, 55)
    elif star_count == 5:
        return random.randint(55, 70)
    elif star_count == 6:
        return random.randint(70, 85)
    elif star_count == 7:
        return random.randint(85, 100)
    else:
        return None


def get_user_fortune_data(user_id, jrys_data):
    """获取用户运势数据"""
    conn, cursor = init_user_numbers_db()
    today_date = datetime.now().strftime('%Y-%m-%d')
    is_festival = is_spring_festival()

    cursor.execute('SELECT random_number, number FROM user_numbers WHERE user_id = ? AND date = ?',
                   (user_id, today_date))
    row = cursor.fetchone()

    if row:
        random_number = row[0]
        number = row[1]
        fortune_data = jrys_data[str(random_number)][0]
    else:
        while True:
            random_number = random.randint(1, 1433)
            fortune_data = jrys_data.get(str(random_number))

            if fortune_data:
                fortune_data = fortune_data[0]
                lucky_star = fortune_data['luckyStar']
                star_count = lucky_star.count('★')
                
                if is_festival and star_count < 4:
                    continue
                
                number = get_fortune_number(lucky_star)

                if number is not None:
                    break

        cursor.execute('''
            INSERT OR REPLACE INTO user_numbers (user_id, random_number, number, date) 
            VALUES (?, ?, ?, ?)
        ''', (user_id, random_number, number, today_date))
        conn.commit()

    conn.close()
    return random_number, number, fortune_data


def get_user_rp_number(user_id, jrys_data):
    """获取用户人品值，与运势保持关联"""
    conn, cursor = init_user_numbers_db()
    today_date = datetime.now().strftime('%Y-%m-%d')
    is_festival = is_spring_festival()

    cursor.execute('SELECT random_number, number FROM user_numbers WHERE user_id = ? AND date = ?',
                   (user_id, today_date))
    row = cursor.fetchone()

    if row:
        random_number = row[0]
        number = row[1]
        fortune_data = jrys_data[str(random_number)][0]
    else:
        while True:
            random_number = random.randint(1, 1433)
            fortune_data = jrys_data.get(str(random_number))

            if fortune_data:
                fortune_data = fortune_data[0]
                lucky_star = fortune_data['luckyStar']
                star_count = lucky_star.count('★')
                
                if is_festival and star_count < 4:
                    continue
                
                number = get_fortune_number(lucky_star)

                if number is not None:
                    break

        cursor.execute('''
            INSERT OR REPLACE INTO user_numbers (user_id, random_number, number, date) 
            VALUES (?, ?, ?, ?)
        ''', (user_id, random_number, number, today_date))
        conn.commit()

    conn.close()
    return number
