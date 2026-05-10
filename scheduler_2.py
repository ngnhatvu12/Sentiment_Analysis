import schedule
import time
import sys
import os
from datetime import datetime
import logging

# Thiết lập logging
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scheduler.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# ====================== JOBS =========================
def daily_processing_job():
    """Công việc xử lý hàng ngày vào cuối ngày với --last-24h"""
    try:
        logger.info("Starting daily batch processing with --last-24h...")

        # 👉 Import và gọi hàm trong main.py trực tiếp
        import main
        if hasattr(main, "main__"):  
            main.main__(last_24h=True)
        else:
            logger.error("main.py không có hàm main(last_24h=True)")
            return

        logger.info("Daily processing completed successfully!")

    except Exception as e:
        logger.error(f"Error in daily processing job: {e}", exc_info=True)


def health_check_job():
    """Kiểm tra sức khỏe hệ thống hàng giờ"""
    try:
        logger.info("Performing system health check...")

        import main
        if hasattr(main, "main"):
            main.main__(stats=1)  # Gọi hàm tương ứng trong main.py
        else:
            logger.warning("main.py không có tham số stats=1")

        logger.info("System health check passed")

    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)


# ====================== SCHEDULER =========================
def setup_scheduler():
    """Thiết lập lịch chạy hàng ngày"""
    # Chạy chính vào 23:50 hàng ngày
    schedule.every().day.at("23:50").do(daily_processing_job)

    # Health check hàng giờ từ 8h đến 23h
    for hour in range(8, 24):
        schedule.every().day.at(f"{hour:02d}:00").do(health_check_job)

    # 👉 Chạy ngay khi khởi động
    logger.info("Running initial jobs...")
    daily_processing_job()
    health_check_job()

    logger.info("Scheduler setup complete!")
    logger.info("Next run scheduled for 23:50 daily")
    logger.info("Health checks scheduled hourly from 8:00 to 23:00")


def main():
    """Hàm main cho scheduler"""
    logger.info("Starting AI Sentiment Analysis Scheduler Service...")

    setup_scheduler()

    logger.info("Scheduler is running. Press Ctrl+C to stop.")

    while True:
        try:
            schedule.run_pending()
            time.sleep(30)  # Kiểm tra mỗi 30 giây

            # Log mỗi 10 phút để biết service vẫn hoạt động
            if int(time.time()) % 600 == 0:
                logger.info("Scheduler service is alive and waiting...")

        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error in scheduler: {e}")
            time.sleep(60)  # Chờ 1 phút nếu có lỗi


if __name__ == "__main__":
    main()

#  pyinstaller --onefile --collect-all underthesea --additional-hooks-dir=. scheduler_2.py