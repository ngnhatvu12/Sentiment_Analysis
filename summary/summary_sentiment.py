from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import time
import db
import logging
import os

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

def insert_stock_sentiment(conn, interval='24h', run_time=None):
    logger.info(f"=== Bắt đầu insert stock_sentiment interval={interval} ===")
    """
    Insert dữ liệu sentiment vào bảng stock_sentiment theo interval: 24h, Week, Month
    - 24h: từ 8h hôm qua -> 8h hôm nay
    - Week: từ 8h thứ 2 tuần trước -> 8h thứ 2 tuần này
    - Month: từ 8h ngày 1 tháng trước -> 8h ngày 1 tháng này
    """

    if run_time is None:
        run_time = datetime.now()

    # mặc định end_time là 8h sáng hôm nay
    end_time = datetime(run_time.year, run_time.month, run_time.day, 8, 0, 0)

    if interval == '24h':
        start_time = end_time - timedelta(days=1)

    elif interval.lower() == 'week':
        # Tìm thứ 2 gần nhất trước end_time
        weekday = end_time.weekday()  # 0 = Monday
        start_time = end_time - timedelta(days=weekday+7)  # Monday tuần trước 8h
        end_time = start_time + timedelta(days=7)

    elif interval.lower() == 'month':
        # Kết thúc tại 8h sáng hôm nay
        end_time = datetime(run_time.year, run_time.month, run_time.day, 8, 0, 0)
        # Bắt đầu từ 30 ngày trước
        start_time = end_time - timedelta(days=30)

    else:
        raise ValueError("Interval không hợp lệ, chỉ hỗ trợ: 24h, Week, Month")

    start_ts = int(start_time.timestamp())
    end_ts = int(end_time.timestamp())

    query = f"""
        INSERT INTO public.api_sentiment_stock_sentiment 
            (symbol, "interval", positive, negative, neutral, total, "timestamp")
        SELECT 
            symbol,
            '{interval}' as interval,
            SUM(CASE WHEN sentiment = 'TÍCH_CỰC' THEN 1 ELSE 0 END) AS positive,
            SUM(CASE WHEN sentiment = 'TIÊU_CỰC' THEN 1 ELSE 0 END) AS negative,
            SUM(CASE WHEN sentiment = 'TRUNG_TÍNH'  THEN 1 ELSE 0 END) AS neutral,
            COUNT(symbol) AS total
			,{end_ts} AS timestamp
        FROM public.api_sentiment_all_content
        WHERE symbol is not null 
		and timestamp BETWEEN {start_ts} AND {end_ts}
        GROUP BY symbol
        ON CONFLICT (symbol, "interval", "timestamp") DO NOTHING;
    """
    logger.info(f"Chạy query insert api_sentiment_stock_sentiment: {query}")
    cur = conn.cursor()
    cur.execute(query)
    conn.commit()
    cur.close()

    logger.info(f"✅ Đã insert dữ liệu interval={interval} cho khoảng {start_time} -> {end_time}")

def insert_top10_stock_sentiment(conn, interval='24h', run_time=None):
    logger.info(f"=== Bắt đầu insert TOP 10 stock_sentiment interval={interval} ===")
    """
    Lưu top 10 mã chứng khoán được nhắc nhiều nhất (theo total)
    vào bảng stock_sentiment, dựa trên dữ liệu đã có trong stock_sentiment.
    - interval: 24h / Week / Month
    - chỉ lấy dữ liệu của ngày hiện tại (end_time = 8h hôm nay)
    """

    if run_time is None:
        run_time = datetime.now()

    # Lấy top 10 theo timestamp mới nhất
    insert_query = f"""
        INSERT INTO public.api_sentiment_top_stock_sentiment
            (symbol, "interval", positive, negative, neutral, total, row_num, updated_at)
        SELECT *
        FROM (
            SELECT 
                symbol,
                '{interval}' as interval,
                positive,
                negative,
                neutral,
                total,
                ROW_NUMBER() OVER (ORDER BY total DESC) as row_num,
                "timestamp" as updated_at
            FROM public.api_sentiment_stock_sentiment
            WHERE "interval" = '{interval}'
            AND "timestamp" = (
                SELECT MAX("timestamp") FROM public.api_sentiment_stock_sentiment WHERE "interval" = '{interval}'
            )
            ORDER BY total DESC
            LIMIT 10
        ) sub
        ON CONFLICT ("interval", row_num) 
        DO UPDATE SET
            symbol = EXCLUDED.symbol,
            positive = EXCLUDED.positive,
            negative = EXCLUDED.negative,
            neutral = EXCLUDED.neutral,
            total = EXCLUDED.total,
            updated_at = EXCLUDED.updated_at;
    """
    logger.info(f"insert_query: {insert_query}")
    cur = conn.cursor()
    cur.execute(insert_query)
    conn.commit()
    cur.close()

    logger.info(f"✅ Đã insert TOP 10 từ stock_sentiment interval={interval} (timestamp mới nhất)")


# if __name__ == "__main__":
#     conn = db.get_connection()
#     run_interval = ('24h', 'week', 'month')
#     for interval in run_interval:
#         insert_stock_sentiment(conn, interval=interval)
#         insert_top10_stock_sentiment(conn, interval=interval)
    
#     conn.close()

def run_daily_job():
    try:
        logger.info(f"Job chạy lúc {datetime.now()}")
        conn = db.get_connection()
        run_interval = ('24h', 'week', 'month')
        for interval in run_interval:
            insert_stock_sentiment(conn, interval=interval)

        insert_top10_stock_sentiment(conn, '24h')    
        conn.close()
        logger.info("Job hoàn thành thành công ✅")

    except Exception as e:
        logger.info(f"Lỗi khi chạy job: {e}")

if __name__ == "__main__":
    scheduler = BackgroundScheduler()

    # chạy mỗi ngày lúc 8h05, có misfire handling
    scheduler.add_job(
        run_daily_job,
        "cron",
        hour=8,
        minute=10,
        misfire_grace_time=600,  # cho phép trễ tối đa 10 phút
        coalesce=False           # không gộp nhiều job bị lỡ
    )

    # chạy ngay 1 lần khi start
    run_daily_job()

    scheduler.start()
    logger.info("Bot đã khởi động, job sẽ chạy ngay và lặp lại mỗi ngày lúc 8h10.")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Bot đã dừng.")
#  pyinstaller --onefile rumor/rumor_analysis.py --exclude-module=torch --exclude-module=torchvision --exclude-module=torchaudio