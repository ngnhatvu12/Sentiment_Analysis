import os
import re
import psycopg2
import pandas as pd
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )

def get_tickers(conn):
    cur = conn.cursor()
    cur.execute("SELECT ticker FROM public.stock_list WHERE ticker <> ''")
    tickers = [row[0].upper() for row in cur.fetchall()]
    cur.close()
    return tickers

def save_rumors(conn, rumor_df):
    """
    Lưu dữ liệu từ DataFrame rumor_df vào bảng public.rumor
    Các cột cần: content, symbol, source, date
    - date: sẽ convert sang unix timestamp
    - sentiment: để NULL
    """
    
    # Chuẩn bị dữ liệu (list of tuples)
    records = [
        (row["id"], row["date"], row["symbol"], row["content"], None, row["source"])
        for _, row in rumor_df.iterrows()
    ]

    sql = """
        INSERT INTO public.rumor (id, timestamp, symbol, content, sentiment, source)
        VALUES %s
    """

    with conn.cursor() as cur:
        execute_values(cur, sql, records)
    conn.commit()
