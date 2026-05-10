from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, time
import psycopg2
import re
import pandas as pd
import time as time_module
import logging
from dotenv import load_dotenv
import os

# --- Setup logging ---
logging.basicConfig(
    filename="yt_post_summary.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

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
    cur.execute("SELECT ticker FROM public.stock_list where ticker <>''")   # chỉnh tên bảng/cột theo DB bạn
    tickers = [row[0].upper() for row in cur.fetchall()]
    cur.close()
    return tickers
# --- Lấy transcript từ 7h hôm qua → 7h hôm nay ---
def get_posts(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT post_id, post_content, post_at
        FROM public.yt_post
        WHERE post_at >= (date_trunc('day', now()) - interval '1 day' + interval '7 hour')
          AND post_at <  (date_trunc('day', now()) + interval '7 hour')
          limit 10
    """)
    rows = cur.fetchall()
    cur.close()
    return rows  # [(post_id, content, post_at), ...]

import re


def split_sentences_ori(text):
    sentences = []
    start = 0
    i = 0
    n = len(text)

    while i < n:
        char = text[i]

        if char.isupper():
            # lấy từ hiện tại từ vị trí i
            m = re.match(r'[A-Z0-9]+[a-z]*', text[i:])
            curr_word = m.group() if m else ''

            # nếu từ hiện tại là toàn hoa hoặc chữ+số liền nhau và dài >1 → không tách
            if re.match(r'^[A-Z0-9]+$', curr_word) and len(curr_word) > 1:
                i += len(curr_word)
                continue

            # tách câu tại vị trí i nếu không phải đầu text
            if i != start:
                sentences.append(text[start:i].strip())
                start = i

            i += len(curr_word)
        else:
            i += 1

    # thêm phần cuối
    sentences.append(text[start:].strip())
    return [s for s in sentences if s]


MAX_WORDS = 20  # số từ trước và sau ticker

def split_sentences(text):
    # chia text thành các từ, giữ luôn vị trí start index
    words = [(m.group(), m.start()) for m in re.finditer(r'\S+', text)]
    sentences = []
    start = 0

    for word, idx in words:
        # nếu từ là toàn hoa hoặc chữ+số liền nhau và dài >1 → không tách
        if re.match(r'^[A-Z0-9]+$', word) and len(word) > 1:
            continue

        # nếu từ bắt đầu bằng chữ hoa bình thường → tách câu
        if word[0].isupper():
            if idx != start:
                sentences.append(text[start:idx].strip())
                start = idx

    # thêm phần cuối
    sentences.append(text[start:].strip())
    return [s for s in sentences if s]

def extract_mentions(posts, tickers):
    logging.info(f"Extracting mentions from {len(posts)} posts with {len(tickers)} tickers.")
    data = []
    if not tickers:
        return pd.DataFrame(columns=["post_id", "post_ticker", "post_sentence", "context", "post_at"])

    tickers_sorted = sorted(tickers, key=len, reverse=True)
    pattern = re.compile('|'.join(map(re.escape, tickers_sorted)))

    for post_id, content, post_at in posts:
        words = content.split()
        for match in pattern.finditer(content):
            tk = match.group(0)
            start_char = match.start()
            end_char = match.end()

            # tìm index từ chứa ticker
            char_count = 0
            tk_index = -1
            for i, w in enumerate(words):
                char_count += len(w) + 1
                if char_count > start_char:
                    tk_index = i
                    break
            if tk_index == -1:
                continue

            # lấy 20 từ trước + 20 từ sau
            start_idx = max(0, tk_index - MAX_WORDS)
            end_idx = min(len(words), tk_index + MAX_WORDS + 1)
            sentence_window = " ".join(words[start_idx:end_idx])

            # --- tách câu trong window ---
            sentences = split_sentences(sentence_window)
            used = set()
            for i, sentence in enumerate(sentences):
                if i in used:
                    continue
                if tk not in sentence:
                    continue
                # gom 1 câu trước + câu chứa ticker + 1 câu sau
                context_parts = []
                if i > 0:
                    context_parts.append(sentences[i-1].strip())
                    used.add(i-1)
                context_parts.append(sentence.strip())
                if i < len(sentences) - 1:
                    context_parts.append(sentences[i+1].strip())
                    used.add(i+1)
                used.add(i)

                data.append((
                    post_id,
                    tk,
                    sentence.strip(),
                    " ".join(context_parts),
                    post_at
                ))

    return pd.DataFrame(data, columns=["post_id", "post_ticker", "post_sentence", "context", "post_at"])

# --- Lưu kết quả vào PostgreSQL ---
# def save_mentions(conn, df):
#     logging.info(f"Saving {len(df)} mentions to database.")
#     if df.empty:
#         return
#     cur = conn.cursor()
#     for _, row in df.iterrows():
#         cur.execute("""
#             INSERT INTO public.yt_post_summary (post_id, post_ticker, post_sentence, post_at)
#             VALUES (%s, %s, %s, %s)
#             ON CONFLICT (post_id, post_ticker)
#             DO UPDATE SET post_sentence = EXCLUDED.post_sentence,
#                           post_at = EXCLUDED.post_at;
#         """, (row.post_id, row.post_ticker, row.context, row.post_at))
#     conn.commit()
#     cur.close()

def save_mentions(conn, df):
    logging.info(f"Saving {len(df)} mentions to database.")
    if df.empty:
        return

    cur = conn.cursor()
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO public.api_sentiment_youtuber_advice (
                "timestamp", symbol, advise, source
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT ("timestamp", symbol, advise, source)
            DO NOTHING;
        """, (
            int(row.post_at.timestamp()),     # hoặc row['timestamp'] nếu dùng kiểu dict
            row.post_ticker,
            row.context,
            row.post_id,
        ))
    conn.commit()
    cur.close()


# --- Job hàng ngày ---
def daily_job():
    logging.info(f"Job running at {datetime.now()}")

    conn = get_connection()
    cur = conn.cursor()

    # tính khoảng thời gian: 7h hôm trước -> 7h hôm nay
    now = datetime.now()
    today_7h = datetime.combine(now.date(), time(7,0))
    yesterday_7h = today_7h - timedelta(days=1)

    cur.execute("""
        SELECT post_id, post_content, post_at 
        FROM public.yt_post
        WHERE post_at >= %s AND post_at < %s
    """, (yesterday_7h, today_7h))
    posts = cur.fetchall()

    # load tickers
    tickers = get_tickers(conn)

    # tìm mentions
    df = extract_mentions(posts, tickers)
    save_mentions(conn, df)
    conn.close()
    logging.info("Job done.")

# --- Scheduler ---
if __name__ == "__main__":
    scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")

    # chạy ngay 1 lần khi start
    daily_job()

    # sau đó hẹn giờ chạy 7h sáng hàng ngày
    scheduler.add_job(daily_job, 'cron', hour=7, minute=0)
    scheduler.start()

    logging.info("Scheduler started. Waiting for jobs...")

    try:
        while True:
            time_module.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

# pyinstaller --onefile yt_advise/main_yt_scheduler.py --exclude-module=torch --exclude-module=torchvision --exclude-module=torchaudio