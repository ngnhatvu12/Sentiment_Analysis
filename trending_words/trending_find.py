import os
import re
import psycopg2
import pandas as pd
from dotenv import load_dotenv
from underthesea import word_tokenize
import numpy as np
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import time
import logging
import os

from datetime import timedelta
import pandas as pd
import pytz

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


# ============== 1. Load biến môi trường ==============
load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )

def load_stopwords(file_path="vietnamese-stopwords.txt"):
    with open(file_path, "r", encoding="utf-8") as f:
        return set([line.strip() for line in f if line.strip()])


# ============== 2. Hàm xử lý text ==============
# Stopword tiếng Việt (NLTK có hỗ trợ, có thể bổ sung thêm tùy nhu cầu)
try:
    # stop_words = set(stopwords.words("vietnamese"))
    stop_words = load_stopwords()
except:
    stop_words = {
        "là","và","của","có","cho","với","một","các","những","được","này",
        "đã","trong","khi","đó","từ","thì","ra","ở","đến","cũng","như",
        "sẽ","không","vẫn","nên","rằng","lại","đi","hay","nhiều","ít","hơn","tới"
    }

def clean_text_old(text: str):
    if not isinstance(text, str):
        return []
    text = text.lower()
    text = re.sub(r"http\S+|www\S+", "", text)   # bỏ link
    text = re.sub(r"[^a-zA-ZÀ-ỹ0-9\s]", " ", text)  # bỏ ký tự đặc biệt
    tokens = word_tokenize(text, format="text").split() # type: ignore
    # tokens = [t for t in tokens if t not in stop_words and len(t) > 1]
    tokens = [
        t for t in tokens 
        if t not in stop_words 
        and len(t) > 1 
        and not t.isdigit()            # bỏ token toàn số
        and not re.match(r"^\d+$", t)  # chắc chắn bỏ chuỗi chỉ gồm số
    ]
    return tokens

# Regex tách từ nhanh hơn nhiều
TOKEN_PATTERN = re.compile(r"[a-zA-ZÀ-ỹ0-9]+", re.UNICODE)

def clean_text(text: str):
    if not isinstance(text, str):
        return []
    text = text.lower()
    text = re.sub(r"http\S+|www\S+", "", text)
    tokens = TOKEN_PATTERN.findall(text)  # nhanh hơn nltk.word_tokenize rất nhiều
    return [t for t in tokens if t not in stop_words and len(t) > 1 and not t.isdigit()]

# ============== 3. Load dữ liệu từ Postgres ==============
def load_sql_query(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def load_data(end_time=None):
    VIET_TZ = pytz.timezone("Asia/Bangkok")
    conn = get_connection()

    if end_time is None:
        end_time = datetime.now(VIET_TZ)

    # Lấy 2 ngày gần nhất tính tới end_time (giờ Việt Nam)
    start_date = (end_time - timedelta(days=2)).date()
    logger.info(f"start date: {start_date}, end_time: {end_time}")

    # Đọc query từ file
    query = load_sql_query("trending_load_data_query.sql")
    logger.info(f"trending query: {query}")
    count_placeholders = query.count("%s")
    params = (start_date,) * count_placeholders

    df = pd.read_sql(query, conn, params=params)
    conn.close()

    # --- Chuẩn hóa timezone ---
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
        # Chuyển từ UTC → Việt Nam
        df["date"] = df["date"].dt.tz_convert(VIET_TZ)

    logger.info(
        f"****load_data df['date'].min()={df['date'].min()}, "
        f"df['date'].max()={df['date'].max()} (đã convert về Asia/Bangkok)"
    )

    return df


# ============== 4. Phân tích trending word ==============


def analyze_trending(df: pd.DataFrame, top_n: int = 20, alpha: float = 0.5, beta: float = 1.0):
    """
    Phân tích trending words theo công thức phổ biến (Twitter-like):
    score = count^alpha * growth^beta

    Args:
        df: DataFrame có cột ["content", "date"]
        top_n: số từ khóa top cần lấy
        alpha, beta: hệ số điều chỉnh (alpha ưu tiên số lượng, beta ưu tiên tăng trưởng)

    Returns:
        trending_final, trending_by_count, trending_by_growth, df_count
    """
    # Làm sạch & tách token
    df["tokens"] = df["content"].apply(clean_text)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    # Đếm từ theo ngày
    df_count = (
        df.explode("tokens")
        .groupby(["date", "tokens"])
        .size()
        .reset_index(name="count")
    )

    # Pivot -> ma trận ngày x từ
    pivot = df_count.pivot(index="date", columns="tokens", values="count").fillna(0)
    logger.info(f"pivot:{pivot}")

    # Tính growth so với hôm qua (có smoothing tránh chia 0)
    yesterday = pivot.shift(1).fillna(0)
    growth = (pivot - yesterday) / (yesterday + 1)

    # Lấy dữ liệu hôm nay
    today = pivot.index[-1]
    counts_today = pivot.loc[today]
    growth_today = growth.loc[today]

    # Gộp dữ liệu
    trending_today = pd.DataFrame({
        "word": counts_today.index,
        "count_today": counts_today.values.astype(int),
        "growth": growth_today.values
    })

    # Loại bỏ inf / NaN
    trending_today.replace([np.inf, -np.inf], np.nan, inplace=True)
    trending_today.dropna(inplace=True)

    # Ngưỡng lọc động: bỏ noise quá nhỏ
    max_count = counts_today.max()
    dynamic_min_count = max(2, max_count // 10)  # chặt chẽ hơn (1/10 max)
    trending_today = trending_today[trending_today["count_today"] >= dynamic_min_count]

    # Thêm score phổ biến
    trending_today["score"] = (trending_today["count_today"] ** alpha) * (
        (1 + trending_today["growth"]) ** beta
    )

    # Top theo từng loại
    trending_by_count = trending_today.sort_values(by="count_today", ascending=False).head(top_n)
    trending_by_growth = trending_today.sort_values(by="growth", ascending=False).head(top_n)
    trending_final = trending_today.sort_values(by="score", ascending=False).head(top_n)

    return trending_final, trending_by_count, trending_by_growth, df_count




def analyze_trending_2days(
    df: pd.DataFrame,
    top_n: int = 20,
    alpha: float = 0.5,
    beta: float = 1.0,
    end_time: pd.Timestamp = None,
    freq: str = "1H",
    align: str | None = "H",
    output_csv: str | None = None,
    use_bin_fallback: bool = True,   # nếu prev quá ít row thì chuyển sang đếm theo bin
    min_prev_rows_for_direct: int = 50  # threshold debug
):
    """
    Phiên bản chống sai lệch prev_count:
     - đảm bảo df < end_time
     - đồng bộ timezone
     - chuẩn hóa tokens trước explode
     - cung cấp fallback đếm theo bin (freq)
    Trả về: trending_final, trending_by_count, trending_by_growth, pivot_hourly (pivot có thể None)
    """
    if df is None or df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    logger.info(f"df['date'].min()={df['date'].min()}, df['date'].max()={df['date'].max()}")


    # đảm bảo có timezone Việt Nam
    VIET_TZ = pytz.timezone("Asia/Bangkok")

    df = df.copy()
    # chuẩn hóa date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # loại bản ghi không parse được
    df = df[df["date"].notna()]

    # --- Đưa toàn bộ date về cùng timezone Việt Nam ---
    if df["date"].dt.tz is None or df["date"].dt.tz.iloc[0] is None:
        # nếu cột date là naive (không có tz), ta giả định đó là giờ Việt Nam
        df["date"] = df["date"].dt.tz_localize(VIET_TZ)
    else:
        # nếu có timezone khác (ví dụ UTC) → chuyển sang giờ Việt Nam
        df["date"] = df["date"].dt.tz_convert(VIET_TZ)

    # --- Xác định anchor end_time ---
    if end_time is None:
        end_time = df["date"].max()

    # ép end_time về cùng timezone Việt Nam
    end_time = pd.to_datetime(end_time)
    if end_time.tzinfo is None:
        end_time = end_time.tz_localize(VIET_TZ)
    else:
        end_time = end_time.tz_convert(VIET_TZ)

    # --- Nếu cần align (ví dụ theo giờ tròn) ---
    if align == "H":
        end_time = end_time.floor("H")
    elif align == "min":
        end_time = end_time.floor("T")

    logger.info(f"✅ end_time (Asia/Bangkok) = {end_time}")
    logger.info(f"df['date'].min()={df['date'].min()}, df['date'].max()={df['date'].max()}")


    # làm tròn nếu cần
    if align == "H":
        end_time = end_time.floor("H")
    elif align == "min":
        end_time = end_time.floor("T")
    
    # logger.info(f"end_time={end_time}, current_start={current_start}")
    # logger.info(f"df['date'].min()={df['date'].min()}, df['date'].max()={df['date'].max()}")
    # logger.info(f"Timezone info: df_tz={df_tz}, end_time_tz={end_time.tzinfo}")

    # --- Lọc data trước end_time (chỉ lấy < end_time) ---
    # df = df[df["date"] < end_time]



    # cửa sổ
    current_start = end_time - timedelta(hours=24)
    prev_start = current_start - timedelta(hours=24)
    logger.info(f"WINDOW prev:{prev_start} -> {current_start}, current:{current_start} -> {end_time}")
    logger.info(f"df['date'].min()={df['date'].min()}, df['date'].max()={df['date'].max()}")
    # --- Tokenize & chuẩn hóa tokens (bắt buộc trả list) ---
    df["tokens"] = df["content"].apply(clean_text)

    def _ensure_list(x):
        # trả về list string sạch (lọc None, '', whitespace)
        if isinstance(x, (list, tuple)):
            return [str(t).strip() for t in x if t is not None and str(t).strip() != ""]
        if pd.isna(x):
            return []
        s = str(x).strip()
        return [s] if s != "" else []

    df["tokens"] = df["tokens"].apply(_ensure_list)

    # explode
    exploded = df.explode("tokens")
    # loại bỏ token rỗng / NaN
    exploded = exploded[exploded["tokens"].notna()]
    exploded["tokens"] = exploded["tokens"].astype(str).str.strip()
    exploded = exploded[exploded["tokens"] != ""]

    # --- Debug: số hàng trong mỗi cửa sổ ---
    now_rows = ((exploded["date"] >= current_start) & (exploded["date"] < end_time)).sum()
    prev_rows = ((exploded["date"] >= prev_start) & (exploded["date"] < current_start)).sum()
    total_rows = len(exploded)
    logger.info(f"exploded rows total={total_rows}, now_rows={now_rows}, prev_rows={prev_rows}")

    # --- Count trực tiếp theo cửa sổ ---
    counts_now = (
        exploded.loc[(exploded["date"] >= current_start) & (exploded["date"] < end_time), ["tokens"]]
        .groupby("tokens")
        .size()
        .rename("count_now")
    )

    counts_prev = (
        exploded.loc[(exploded["date"] >= prev_start) & (exploded["date"] < current_start), ["tokens"]]
        .groupby("tokens")
        .size()
        .rename("count_prev")
    )

    # nếu prev có quá ít record và user muốn fallback -> dùng pivot theo bin (ổn định hơn)
    pivot_hourly = None
    if use_bin_fallback and prev_rows < min_prev_rows_for_direct and total_rows > 0:
        logger.info("prev_rows nhỏ -> dùng phương pháp pivot theo bin (fallback)")
        # build pivot: index = time bins, columns = tokens
        pivot = (
            exploded.groupby([pd.Grouper(key="date", freq=freq), "tokens"])
            .size()
            .unstack(fill_value=0)
            .sort_index()
        )
        # ensure index covers full range prev_start -> end_time - freq
        try:
            delta = pd.Timedelta(freq)
        except Exception:
            delta = pd.Timedelta(hours=1)
        full_index = pd.date_range(prev_start, end_time - delta, freq=freq)
        pivot = pivot.reindex(full_index, fill_value=0)
        pivot_hourly = pivot

        # sum bins for current and prev
        counts_now_bin = pivot.loc[current_start: end_time - delta].sum(axis=0)
        counts_prev_bin = pivot.loc[prev_start: current_start - delta].sum(axis=0)

        counts_now = counts_now_bin.rename("count_now")
        counts_prev = counts_prev_bin.rename("count_prev")

    # Đồng bộ index
    counts_now, counts_prev = counts_now.align(counts_prev, fill_value=0)

    # Growth
    growth = (counts_now - counts_prev) / (counts_prev + 1)

    # Build dataframe tổng hợp
    trending = pd.DataFrame({
        "word": counts_now.index,
        "count_today": counts_now.astype(int).values,
        "count_prev": counts_prev.astype(int).values,
        "growth": growth.values
    })

    trending.replace([np.inf, -np.inf], np.nan, inplace=True)
    trending.dropna(inplace=True)

    # Lọc noise (dynamic)
    max_count = counts_now.max() if len(counts_now) > 0 else 0
    dynamic_min_count = max(2, int(max_count // 4))
    trending = trending[trending["count_today"] >= dynamic_min_count]

    # Score
    trending["score"] = (trending["count_today"] ** alpha) * ((1 + trending["growth"]) ** beta)

    trending_by_count = trending.sort_values("count_today", ascending=False).head(top_n)
    trending_by_growth = trending.sort_values("growth", ascending=False).head(top_n)
    trending_final = trending.sort_values("score", ascending=False).head(top_n)

    # optional output pivot to csv
    if output_csv and pivot_hourly is not None:
        pivot_hourly.to_csv(output_csv, encoding="utf-8-sig")

    return trending_final, trending_by_count, trending_by_growth, pivot_hourly


def _build_pivot(exploded_df: pd.DataFrame, start_time: pd.Timestamp, end_time: pd.Timestamp, freq: str = "1H"):
    """
    Helper: build pivot (time x token) từ exploded_df (cột date, tokens).
    Chỉ tạo pivot trong khoảng [start_time, end_time].
    """
    # lọc khoảng 48h (prev_start -> end_time)
    df_w = exploded_df[(exploded_df["date"] > start_time) & (exploded_df["date"] <= end_time)].copy()
    if df_w.empty:
        return pd.DataFrame()

    # group theo freq (ví dụ 1H) để có ma trận hour x token
    df_count = (
        df_w.groupby([pd.Grouper(key="date", freq=freq), "tokens"])
        .size()
        .reset_index(name="count")
    )

    pivot = df_count.pivot(index="date", columns="tokens", values="count").fillna(0)

    # đảm bảo tất cả giờ trong khoảng đều có (nếu muốn)
    full_idx = pd.date_range(start=start_time + timedelta(seconds=1), end=end_time, freq=freq)
    pivot = pivot.reindex(full_idx, fill_value=0)

    return pivot


# ============== 6. Save trending vào PostgreSQL ==============
def save_trending_to_db(df: pd.DataFrame, interval: str = "24h", end_time=None):
    """
    Lưu kết quả trending vào bảng api_sentiment_trending_keyword
    Args:
        df: DataFrame có cột ["word", "growth"]
        interval: '24h', 'Week', 'Month'
    """
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = int(end_time.timestamp())
    for i, row in enumerate(df.itertuples(), start=1):
        cursor.execute(
            """
            INSERT INTO api_sentiment_trending_keyword (interval, row_num, keyword, total, score, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (interval, row_num) DO UPDATE SET
                keyword = EXCLUDED.keyword,
                total = EXCLUDED.total,
                score = EXCLUDED.score,
                timestamp = EXCLUDED.timestamp
            """,
            (interval, i, row.word, row.count_today, float(row.score), timestamp)
        )
    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"✅ Đã lưu {len(df)} trending keywords vào bảng api_sentiment_trending_keyword (interval={interval})")
# ============== 6. Job chạy hằng ngày ==============
def job_trending():
    logger.info("📥 Bắt đầu job phân tích trending...")
    # Lấy thời gian hiện tại, làm tròn xuống theo giờ
    end = pd.Timestamp.now().floor("H")  # ví dụ: 2025-10-04 13:42 -> 2025-10-04 13:00
    logger.info(f"Mốc thời gian end_time = {end}")
    df = load_data(end)
    trending_final, trending_count, trending_growth, df_count = analyze_trending(df, 20)
    # trending_count.to_csv("trending_today_count.csv", index=False, encoding="utf-8-sig")
    # trending_growth.to_csv("trending_today_growth.csv", index=False, encoding="utf-8-sig")
    trending_final.to_csv("trending_today_final.csv", index=False, encoding="utf-8-sig")
    # mốc bạn muốn
    final, by_count, by_growth,_ = analyze_trending_2days(
        df,
        top_n=10,
        alpha=0.6,
        beta=1.2,
        end_time=end,
        freq="1H",
        align="H",
        output_csv="analyze_trending_current.csv"
    )
    final.to_csv("trending_2days.csv", index=False, encoding="utf-8-sig")
    save_trending_to_db(final, '24h', end)

    logger.info("✅ Job hoàn tất!")


# ============== 7. Scheduler ==============
if __name__ == "__main__":
    scheduler = BackgroundScheduler()

    # chạy mỗi giờ vào phút thứ 10
    scheduler.add_job(
        job_trending,
        "cron",
        minute=10,
        misfire_grace_time=600,  # cho phép trễ tối đa 10 phút
        coalesce=False           # không gộp nhiều job bị lỡ
    )

    # chạy ngay 1 lần khi start
    job_trending()

    scheduler.start()
    logger.info("Bot đã khởi động, job sẽ chạy ngay và lặp lại mỗi giờ vào phút 10.")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Bot đã dừng.")



# pyinstaller --onefile --collect-all underthesea --hidden-import sqlite3 --hidden-import _sqlite3 trending_find.py
# pyinstaller --onefile  trending_words/trending_find.py --collect-all underthesea --exclude-module=torch --exclude-module=torchvision --exclude-module=torchaudio

