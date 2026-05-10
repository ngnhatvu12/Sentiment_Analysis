import os
import json
import time
from datetime import datetime

import psycopg2
from psycopg2.extras import DictCursor

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import ActionChains
import time
from dotenv import load_dotenv
import logging

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

# --- Kết nối DB ---
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )


# --- Normalize ngày ---
def normalize_date(raw_date: str, base_date: datetime = None) -> str:
    if not raw_date.strip():
        return ""
    if base_date is None:
        base_date = datetime.now()

    current_year = base_date.year
    raw_date = raw_date.replace("\n", " ").strip()

    try:
        dt = datetime.strptime(f"{raw_date} {current_year}", "%a %b %d %Y")
    except ValueError:
        return raw_date

    if dt < base_date and (base_date.month == 12 and dt.month == 1):
        dt = dt.replace(year=current_year + 1)

    return dt.strftime("%Y-%m-%d")

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains

import time

import random
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    TimeoutException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def _rand_sleep(a=0.05, b=0.25):
    """Ngủ trong khoảng nhỏ ngẫu nhiên để giống thao tác người."""
    time.sleep(random.uniform(a, b))

def human_click(driver, element, *, pre_wait=0.1, steps=6, move_pause=(0.03, 0.18), extra_scroll=True):
    """
    Giả lập click giống người thật lên một WebElement đã có.
    Trả về True nếu click thành công, False nếu thất bại.
    """
    try:
        print("[DEBUG] human_click: bắt đầu")
        # Không chạy headless nếu muốn giống người thật hơn; nếu headless thì chuyển động chuột vẫn giả lập nhưng nhìn sẽ khác.
        if extra_scroll:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", element)
                _rand_sleep(0.05, 0.2)
                print("[DEBUG] human_click: scrollIntoView done")
            except WebDriverException as e:
                print(f"[DEBUG] human_click: scrollIntoView failed: {e}")

        # Chờ 1 chút như người đọc
        time.sleep(random.uniform(0.05, pre_wait + 0.15))

        # Lấy kích thước element
        rect = None
        try:
            rect = element.rect  # {'height':..., 'width':..., 'x':..., 'y':...}
        except Exception:
            # fallback: truy vấn via JS
            rect = driver.execute_script(
                "const r = arguments[0].getBoundingClientRect(); return {x:r.left, y:r.top, width:r.width, height:r.height};",
                element,
            )

        w = max(int(rect.get("width", 0)), 1)
        h = max(int(rect.get("height", 0)), 1)

        # Chọn một điểm đích trong element (có lề nhỏ để tránh viền)
        margin_x = min(4, max(1, w // 10))
        margin_y = min(4, max(1, h // 10))
        target_x = random.randint(margin_x, max(margin_x + 1, w - margin_x))
        target_y = random.randint(margin_y, max(margin_y + 1, h - margin_y))

        print(f"[DEBUG] human_click: element size w={w}, h={h}, target offset (x={target_x}, y={target_y})")

        # Tạo loạt điểm trung gian để di chuyển chuột "mịn"
        steps = max(3, int(steps))
        intermediate = []
        for i in range(1, steps + 1):
            ratio = i / float(steps)
            ix = int(target_x * ratio + random.uniform(-1, 1))
            iy = int(target_y * ratio + random.uniform(-1, 1))
            # đảm bảo giới hạn trong element
            ix = max(1, min(w - 1, ix))
            iy = max(1, min(h - 1, iy))
            intermediate.append((ix, iy))

        actions = ActionChains(driver)

        # Move in steps using move_to_element_with_offset + small pause
        for ix, iy in intermediate:
            actions.move_to_element_with_offset(element, ix, iy)
            actions.pause(random.uniform(move_pause[0], move_pause[1]))
        # final small pause and click
        actions.pause(random.uniform(0.04, 0.18))
        actions.click()
        print("[DEBUG] human_click: performing action chain (mouse move + click)...")
        actions.perform()
        print("[DEBUG] human_click: action chain performed -> success")
        return True

    except ElementClickInterceptedException as e:
        print(f"[DEBUG] human_click: ElementClickInterceptedException: {e} -- thử JS click fallback")
        try:
            driver.execute_script("arguments[0].click();", element)
            print("[DEBUG] human_click: fallback JS click success")
            return True
        except Exception as e2:
            print(f"[DEBUG] human_click: fallback JS click failed: {e2}")
            return False

    except StaleElementReferenceException as e:
        print(f"[DEBUG] human_click: StaleElementReferenceException: {e} -> element hết hạn")
        return False

    except TimeoutException as e:
        print(f"[DEBUG] human_click: TimeoutException: {e}")
        return False

    except WebDriverException as e:
        print(f"[DEBUG] human_click: WebDriverException: {e} -> thử fallback JS click")
        try:
            driver.execute_script("arguments[0].click();", element)
            print("[DEBUG] human_click: fallback JS click success")
            return True
        except Exception as e2:
            print(f"[DEBUG] human_click: fallback JS click failed: {e2}")
            return False

    except Exception as e:
        print(f"[DEBUG] human_click: Unexpected error: {e}")
        return False


def human_click_by_selector(driver, selector, by=By.CSS_SELECTOR, timeout=10):
    """
    Tìm element bằng selector rồi gọi human_click.
    Trả về True/False.
    """
    wait = WebDriverWait(driver, timeout)
    try:
        print(f"[DEBUG] human_click_by_selector: đang chờ presence của {selector}")
        el = wait.until(EC.presence_of_element_located((by, selector)))
        print("[DEBUG] human_click_by_selector: presence OK")
        # optional: ensure visible / clickable before attempt
        # nhưng vẫn dùng human_click để kiếm phần tử
        success = human_click(driver, el)
        if not success:
            print("[DEBUG] human_click_by_selector: human_click trả về False -> thử element_to_be_clickable + click")
            try:
                clickable = wait.until(EC.element_to_be_clickable((by, selector)))
                clickable.click()
                print("[DEBUG] human_click_by_selector: click bằng element.click() thành công")
                return True
            except Exception as e:
                print(f"[DEBUG] human_click_by_selector: fallback click failed: {e}")
                # final JS click
                try:
                    driver.execute_script("arguments[0].click();", el)
                    print("[DEBUG] human_click_by_selector: cuối cùng JS click thành công")
                    return True
                except Exception as e2:
                    print(f"[DEBUG] human_click_by_selector: cuối cùng cũng fail: {e2}")
                    return False
        return True
    except TimeoutException:
        print("[DEBUG] human_click_by_selector: Không tìm thấy element trong thời gian chờ")
        return False


def scrape_calendar_detail():
    options = Options()
    # options.add_argument("--headless")
    options.add_argument("--start-maximized")

    service = Service(ChromeDriverManager().install(), port=9515)
    driver = webdriver.Chrome(service=service, options=options)

    url = "https://www.forexfactory.com/calendar"
    driver.get(url)

    # # scroll toàn bộ trang
    # last_height = driver.execute_script("return document.body.scrollHeight")
    # while True:
    #     time.sleep(3)
    #     driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    #     time.sleep(3)
    #     new_height = driver.execute_script("return document.body.scrollHeight")
    #     if new_height == last_height:
    #         break
    #     last_height = new_height

    wait = WebDriverWait(driver, 10)
    table = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table.calendar__table"))
    )
    rows = table.find_elements(By.CSS_SELECTOR, "tr.calendar__row")

    grouped_data = []
    current_date = None
    day_events = []
    last_time = ""

    for idx, row in enumerate(rows):
        try:
            date_cell = row.find_elements(By.CSS_SELECTOR, ".calendar__date .date")
            if date_cell:
                if current_date and day_events:
                    grouped_data.append({
                        "Date": current_date,
                        "Events": day_events
                    })

                base_date = datetime.now()
                raw_date = date_cell[0].text.strip()
                current_date = normalize_date(raw_date, base_date)
                print(f"raw_date: {raw_date} -> current_date: {current_date}")

                day_events = []
                last_time = ""

            time_event = row.find_element(By.CSS_SELECTOR, ".calendar__time").text if row.find_elements(By.CSS_SELECTOR, ".calendar__time") else ""
            currency = row.find_element(By.CSS_SELECTOR, ".calendar__currency").text if row.find_elements(By.CSS_SELECTOR, ".calendar__currency") else ""
            impact = row.find_element(By.CSS_SELECTOR, ".calendar__impact span").get_attribute("title") if row.find_elements(By.CSS_SELECTOR, ".calendar__impact span") else ""
            event = row.find_element(By.CSS_SELECTOR, ".calendar__event-title").text if row.find_elements(By.CSS_SELECTOR, ".calendar__event-title") else ""
            actual = row.find_element(By.CSS_SELECTOR, ".calendar__actual").text if row.find_elements(By.CSS_SELECTOR, ".calendar__actual") else ""
            forecast = row.find_element(By.CSS_SELECTOR, ".calendar__forecast").text if row.find_elements(By.CSS_SELECTOR, ".calendar__forecast") else ""
            previous = row.find_element(By.CSS_SELECTOR, ".calendar__previous").text if row.find_elements(By.CSS_SELECTOR, ".calendar__previous") else ""

            if not event.strip():
                continue

            if time_event.strip():
                last_time = time_event.strip()
            else:
                time_event = last_time

            time.sleep(2)
            # tìm nút Open Detail
            detail_links = row.find_elements(By.CSS_SELECTOR, "a.calendar__detail-link")
            if not detail_links:
                continue
            print(f"[DEBUG] Tìm thấy nút Open Detail → thử mở...{detail_links}")
            detail_link = detail_links[0]
            detail_link.click()
            wait = WebDriverWait(driver, 5)

            # human_click_by_selector(driver, "td.calendar__cell.calendar__detail a[title='Open Detail']")
            # time.sleep(2)
            # human_click_by_selector(driver, "td.calendar__cell.calendar__detail a[title='Close Detail']")
            # time.sleep(2)
           
            # detail_row = wait.until(
            #     EC.presence_of_element_located(
            #         (By.CSS_SELECTOR, "tr.calendar__row.calendar__row--detail")
            #     )
            # )
            print("[DEBUG] Đã thấy dòng detail trong DOM.")
            # detail_html = detail_row.get_attribute("outerHTML")
            detail_html = ""
            print(f"detail_html:{detail_html}")
            detail_link.click()
            wait = WebDriverWait(driver, 5)


            # append event
            day_events.append({
                "Time": time_event,
                "Currency": currency,
                "Impact": impact,
                "Event": event,
                "Actual": actual,
                "Forecast": forecast,
                "Previous": previous,
                "Details": detail_html   # thêm cột details
            })

            # đóng lại để tiếp tục row tiếp theo
            try:
                close_btn = row.find_element(By.CSS_SELECTOR, "a.calendar__detail-link--loaded")
                driver.execute_script("arguments[0].click();", close_btn)
                time.sleep(3)
                print("[DEBUG] Đóng detail thành công")
            except Exception as e:
                print("[DEBUG] ❌ Lỗi khi đóng detail:", e)

        except Exception as e:
            print("[DEBUG] Exception :", e)
            continue

    if current_date and day_events:
        grouped_data.append({
            "Date": current_date,
            "Events": day_events
        })

    driver.quit()
    return grouped_data


# --- Scrape dữ liệu ---
def scrape_calendar():
    options = Options()
    # options.add_argument("--headless")
    options.add_argument("--start-maximized")

    service = Service(ChromeDriverManager().install(), port=9515)
    driver = webdriver.Chrome(service=service, options=options)

    url = "https://www.forexfactory.com/calendar"
    driver.get(url)

    # scroll toàn bộ trang
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    wait = WebDriverWait(driver, 10)
    table = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table.calendar__table"))
    )
    rows = table.find_elements(By.CSS_SELECTOR, "tr.calendar__row")

    grouped_data = []
    current_date = None
    day_events = []
    last_time = ""

    for idx, row in enumerate(rows):
        try:
            date_cell = row.find_elements(By.CSS_SELECTOR, ".calendar__date .date")
            if date_cell:
                if current_date and day_events:
                    grouped_data.append({
                        "Date": current_date,
                        "Events": day_events
                    })

                base_date = datetime.now()
                raw_date = date_cell[0].text.strip()
                current_date = normalize_date(raw_date, base_date)
                print(f"raw_date: {raw_date} -> current_date: {current_date}")

                day_events = []
                last_time = ""

            time_event = row.find_element(By.CSS_SELECTOR, ".calendar__time").text if row.find_elements(By.CSS_SELECTOR, ".calendar__time") else ""
            currency = row.find_element(By.CSS_SELECTOR, ".calendar__currency").text if row.find_elements(By.CSS_SELECTOR, ".calendar__currency") else ""
            impact = row.find_element(By.CSS_SELECTOR, ".calendar__impact span").get_attribute("title") if row.find_elements(By.CSS_SELECTOR, ".calendar__impact span") else ""
            event = row.find_element(By.CSS_SELECTOR, ".calendar__event-title").text if row.find_elements(By.CSS_SELECTOR, ".calendar__event-title") else ""
            actual = row.find_element(By.CSS_SELECTOR, ".calendar__actual").text if row.find_elements(By.CSS_SELECTOR, ".calendar__actual") else ""
            forecast = row.find_element(By.CSS_SELECTOR, ".calendar__forecast").text if row.find_elements(By.CSS_SELECTOR, ".calendar__forecast") else ""
            previous = row.find_element(By.CSS_SELECTOR, ".calendar__previous").text if row.find_elements(By.CSS_SELECTOR, ".calendar__previous") else ""

            if not event.strip():
                continue

            if time_event.strip():
                last_time = time_event.strip()
            else:
                time_event = last_time

            # append event
            day_events.append({
                "Time": time_event,
                "Currency": currency,
                "Impact": impact,
                "Event": event,
                "Actual": actual,
                "Forecast": forecast,
                "Previous": previous,
            })

        except Exception:
            continue

    if current_date and day_events:
        grouped_data.append({
            "Date": current_date,
            "Events": day_events
        })

    driver.quit()
    return grouped_data


# --- Lưu vào DB ---
def upsert_to_db(grouped_data):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    sql = """
    INSERT INTO economic_calendar (event_date, event_time, currency, impact, event, actual, forecast, previous)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (event_date, event_time, event)
    DO UPDATE SET
        currency = EXCLUDED.currency,
        impact = EXCLUDED.impact,
        actual = EXCLUDED.actual,
        forecast = EXCLUDED.forecast,
        previous = EXCLUDED.previous;
    """

    for day in grouped_data:
        event_date = day["Date"]
        for ev in day["Events"]:
            cur.execute(sql, (
                event_date,
                ev["Time"],
                ev["Currency"],
                ev["Impact"],
                ev["Event"],
                ev["Actual"],
                ev["Forecast"],
                ev["Previous"]
            ))

    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    # data = scrape_calendar()
    data = scrape_calendar_detail()

    # lưu JSON để debug
    with open("calendar_grouped.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # upsert vào DB
    # upsert_to_db(data)

    print("✅ Scrape + lưu PostgreSQL thành công!")
