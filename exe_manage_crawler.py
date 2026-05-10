import subprocess
import time
import datetime
import logging
import psutil
import os
import signal
import sys

# ----------------- CẤU HÌNH -----------------
CRAWLERS = [
    r"C:\CrawlerEXE\group_crawler\exe_fb.exe",
    r"C:\CrawlerEXE\group_crawler\exe_yt.exe",
]

RESET_HOUR = 23
RESET_MINUTE = 30

LOG_FILE = "watchdog.log"
# --------------------------------------------

# Logging ra file + console
logger = logging.getLogger()
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(console_handler)

processes = {}

def start_crawler(path):
    logger.info(f"[START] {path}")
    return subprocess.Popen(path, creationflags=subprocess.CREATE_NEW_CONSOLE)

def stop_all():
    logger.info("🛑 Dừng toàn bộ crawler...")
    for path in CRAWLERS:
        exe_name = os.path.basename(path).lower()
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                if proc.info['exe'] and proc.info['exe'].lower() == path.lower():
                    logger.info(f"[STOP] {proc.info['pid']} - {proc.info['exe']}")
                    proc.terminate()
                    proc.wait(timeout=5)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue
    logger.info("✅ Đã dừng toàn bộ crawler.")

def get_process_info(exe_path):
    """Trả về (pid, status) của exe_path"""
    exe_name = os.path.basename(exe_path).lower()
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == exe_name:
                return proc.info['pid'], "✅ ĐANG CHẠY"
            if proc.info['exe'] and proc.info['exe'].lower() == exe_path.lower():
                return proc.info['pid'], "✅ ĐANG CHẠY"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return "-", "❌ CHƯA CHẠY"

def print_status():
    """In trạng thái các exe dưới dạng bảng"""
    print("\n=== TRẠNG THÁI CRAWLER ===")
    print(f"{'Tên exe':40} | {'PID':8} | Trạng thái")
    print("-"*65)
    for path in CRAWLERS:
        pid, status = get_process_info(path)
        print(f"{os.path.basename(path):40} | {str(pid):8} | {status}")
    print("="*65 + "\n")

def monitor():
    logger.info("🔄 Watchdog bắt đầu chạy... (nhấn Ctrl+C để thoát)")

    while True:
        for path in CRAWLERS:
            pid, status = get_process_info(path)
            if status.startswith("❌"):
                logger.warning(f"⚠️ {path} chưa chạy hoặc đã chết → khởi động lại.")
                processes[path] = start_crawler(path)
            else:
                logger.info(f"✅ {path} (PID {pid}) vẫn đang chạy.")

        # Hiển thị trạng thái bảng
        print_status()

        time.sleep(600)

if __name__ == "__main__":
    try:
        monitor()
    except KeyboardInterrupt:
        logger.info("⏹ Watchdog dừng bằng Ctrl+C → tắt toàn bộ crawler...")
        stop_all()
        logger.info("Đã tắt toàn bộ crawler. Thoát sau 10s")
        time.sleep(10)
        sys.exit(0)
