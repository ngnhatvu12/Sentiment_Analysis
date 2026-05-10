import os
import re
import psycopg2
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import time

import logging

output_dir = "csv"
os.makedirs(output_dir, exist_ok=True)

# Thư mục lưu log
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
# Đặt tên file log theo ngày
log_file = os.path.join(LOG_DIR, f"bot_{datetime.now().strftime('%Y%m%d')}.log")

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,                   # mức log INFO trở lên
    format="%(asctime)s [%(levelname)s] %(message)s",  # định dạng log
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),  # ghi vào file
        logging.StreamHandler()                          # in ra console
    ]
)

logger = logging.getLogger(__name__)

# Load biến môi trường từ file .env
load_dotenv()


# ==============================
# 1. Kết nối PostgreSQL
# ==============================
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )

# ==============================
# 2. Lấy danh sách ticker
# ==============================
def get_tickers(conn):
    cur = conn.cursor()
    cur.execute("SELECT symbol FROM public.institution_profiles where symbol <> ''")
    tickers = [row[0].upper() for row in cur.fetchall()]
    cur.close()
    return tickers

# ==============================
# 3. Các hàm detect tin đồn
# ==============================
patterns = [
    r"\bnghe\s+(nói|đồn)(\s+rằng|\s+là|\s+đâu)?\b",
    r"\bđồn\s+rằng\b",
    r"\bcó\s+tin\s+đồn(\s+rằng|\s+là)?\b",
    r"\btheo\s+lời\s+đồn\b",
    r"\bngười\s+ta\s+nói(\s+rằng|\s+là)?\b",
    r"\bcó\s+nguồn\s+tin(\s+rằng|\s+là)?\b",
    r"\bnhiều\s+người\s+nói\b",
    r"\bcó\s+người\s+(bảo|cho\s+rằng)\b",
    r"\b(xì\s+xào|rỉ\s+tai\s+nhau|truyền\s+tai\s+nhau)\b",
    r"\btin\s+(hành\s+lang|vỉa\s+hè)\b",
    r"\btin\s+(chưa\s+kiểm\s+chứng|chưa\s+xác\s+thực)\b",
    r"\bchưa\s+có\s+căn\s+cứ\b",
    r"\bhình\s+như\b",
    r"\bnghe\s+bảo\b",
    r"\bnghe\s+kể\b",
    r"\bđược\s+cho\s+là\b",
    r"\bcó\s+vẻ\s+như\b",
    r"\bcó\s+khả\s+năng\s+là\b",
    r"\btin\s+nội\s+bộ\b",
    r"\btin\s+rò\s+rỉ\b",
    r"\bcó\s+lời\s+đồn\b",
    r"\bcó\s+người\s+truyền\s+tai\b",
    r"\bđồn\s+đại\s+phát\b",
    r"\bđồn\s+đại\b",
    r"\bđồn\s+thổi\b",
    r"\brumou?r\b", r"\bhearsay\b", r"\bword\s+on\s+the\s+street\b",
    r"\bpeople\s+say\b", r"\bsources\s+say\b", r"\ballegedly\b",
    r"\breportedly\b", r"\bunconfirmed\b", r"\bspeculation\b",
    r"\bwhispers?\b", r"\bit\s+is\s+said\b", r"\baccording\s+to\s+rumors?\b",
    r"\bgossip\b", r"\brumor\s+has\s+it\b"
]

def detect_rumor_regex(text):
    if not text:
        return None
    text_lower = text.lower()
    for pat in patterns:
        if re.search(pat, text_lower):
            return pat
    return None

def extract_symbols(text, ticker_pattern):
    if not text:
        return None
    matches = ticker_pattern.findall(text.upper())
    return ",".join(sorted(set(matches))) if matches else None

# ==============================
# 4. Hàm insert vào bảng rumor
# ==============================
def insert_rumors(conn, rumor_df):
    cur = conn.cursor()
    insert_sql = """
        INSERT INTO public.api_sentiment_rumor ("timestamp", symbol, content, sentiment, source)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    for _, row in rumor_df.iterrows():
        # ts = int(datetime.strptime(str(row["date"]), "%Y-%m-%d %H:%M:%S").timestamp())
        cur.execute(insert_sql, (
            # row["id"],
            row["date"],
            row["symbol"],
            row["content"],
            None,  # sentiment để trống
            row["source"]
        ))
    conn.commit()
    cur.close()
    logger.info(f"✅ Đã lưu {len(rumor_df)} tin đồn vào bảng rumor")

# ==============================
# 5. Main flow
# ==============================
def get_messages(conn, start_ts, end_ts, start_time, end_time):
    query_messages = f"""
        SELECT 
            fp.post_id AS id,
            fp.original_content AS content,
            EXTRACT(EPOCH FROM fp.date)::bigint AS date,
            'fireant_posts' AS source,
            string_agg(elem->>'symbol', ', ') AS symbols
        FROM fireant_posts fp
        CROSS JOIN LATERAL jsonb_array_elements(fp.tagged_symbols) elem
        WHERE fp.date >= '{start_time}' AND fp.date < '{end_time}'
        GROUP BY fp.post_id, fp.original_content, fp.date

        UNION ALL

        SELECT 
            MIN(id) AS id,                         -- lấy id đại diện
            string_agg(content, ' || ') AS content, -- nối các content cùng ngày
            date,
            'zalo_chat' AS source,
            '' AS symbols
        FROM zalo_chat
        WHERE content <> 'NA' 
        AND date >= {start_ts} AND date < {end_ts}
        GROUP BY date;

    """
    logger.info(f"query_messages: {query_messages}")
    cur = conn.cursor()
    cur.execute(query_messages)
    cols = [desc[0] for desc in cur.description]   # lấy tên cột
    rows = cur.fetchall()
    cur.close()
    return pd.DataFrame(rows, columns=cols)

def run_daily_job():
    try:
        logger.info("start rumor analysis")
        conn = get_connection()

        # Tính thời gian 8h hôm qua và 8h hôm nay (epoch giây) 
        now = datetime.now() 
        end_time = datetime.combine(now.date(), datetime.min.time()) + timedelta(hours=8) # 8h hôm nay 
        start_time = end_time - timedelta(days=1) # 8h hôm qua 
        start_ts = int(start_time.timestamp()) 
        end_ts = int(end_time.timestamp()) 

        logger.info(f"Start: {start_ts} ({start_time})")
        logger.info(f"End:   {end_ts} ({end_time})")

        df = get_messages(conn, start_ts, end_ts, start_time, end_time)

        # Lấy ticker từ DB
        tickers = get_tickers(conn)
        ticker_pattern = re.compile(r"\b(" + "|".join(re.escape(t) for t in tickers) + r")\b")

        # Detect tin đồn
        df["matched_keyword"] = df["content"].apply(detect_rumor_regex)

        # Xử lý symbol theo source
        df["symbol"] = df.apply(
            lambda row: extract_symbols(row["content"], ticker_pattern) 
                        if row["source"] == "zalo_chat" else row.get("symbols", ""),
            axis=1
        )

        # Lọc ra rumor
        rumor_df = df[df["matched_keyword"].notnull()].copy()
        rumor_df = rumor_df.reset_index(drop=True)
        rumor_df = rumor_df[["id", "content", "symbol", "source", "date", "matched_keyword"]]

        # ⚡ Loại bỏ content trùng lặp
        rumor_df = rumor_df.drop_duplicates(subset=["content"], keep="first").reset_index(drop=True)

        logger.info(f"Phát hiện {len(rumor_df)} tin đồn.")
        # Xuất csv
        rumor_df.to_csv("csv/detected_rumor_messages.csv", index=False, encoding="utf-8-sig")

        # Lưu vào DB
        insert_rumors(conn, rumor_df)

        conn.close()
    except Exception as e:
        logger.info(f"Lỗi khi chạy job: {e}")

if __name__ == "__main__":
    scheduler = BackgroundScheduler()

    # chạy mỗi ngày lúc 7h55, có misfire handling
    scheduler.add_job(
        run_daily_job,
        "cron",
        hour=7,
        minute=55,
        misfire_grace_time=600,  # cho phép trễ tối đa 10 phút
        coalesce=False           # không gộp nhiều job bị lỡ
    )

    # chạy ngay 1 lần khi start
    run_daily_job()

    scheduler.start()
    now = datetime.now() 
    logger.info(f"Bot đã khởi động, job sẽ chạy ngay và lặp lại mỗi ngày lúc {now}.")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Bot đã dừng.")