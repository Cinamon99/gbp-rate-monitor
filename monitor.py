#!/usr/bin/env python3
import os
import sys
import json
import requests
from datetime import datetime, timedelta
from urllib.parse import quote
from bs4 import BeautifulSoup
from icalendar import Calendar, Event, Timezone, TimezoneStandard
import pytz
from dotenv import load_dotenv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

load_dotenv()

BOC_URL = "https://www.boc.cn/sourcedb/whpj/"
DATA_FILE = "rate_data.json"
ICS_FILE = "gbp_alert.ics"
CHARTS_DIR = "charts"
TIMEZONE = pytz.timezone("Asia/Shanghai")
UTC = pytz.UTC

os.makedirs(CHARTS_DIR, exist_ok=True)

plt.rcParams["font.sans-serif"] = [
    "Arial Unicode MS", "PingFang SC", "Heiti SC", "Microsoft YaHei",
    "SimHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
    "DejaVu Sans"
]
plt.rcParams["axes.unicode_minus"] = False


def create_vtimezone():
    tzc = Timezone()
    tzc.add("tzid", "Asia/Shanghai")
    tzc.add("x-lic-location", "Asia/Shanghai")

    tzs = TimezoneStandard()
    tzs.add("dtstart", datetime(1970, 1, 1, 0, 0, 0))
    tzs.add("tzoffsetfrom", timedelta(hours=8))
    tzs.add("tzoffsetto", timedelta(hours=8))
    tzs.add("tzname", "CST")
    tzc.add_component(tzs)
    return tzc


def is_workday():
    now = datetime.now(TIMEZONE)
    return now.weekday() < 5


def get_boc_gbp_rate():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        response = requests.get(BOC_URL, headers=headers, timeout=30)
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "lxml")

        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 7:
                    currency_name = cells[0].get_text(strip=True)
                    if "英镑" in currency_name or "GBP" in currency_name:
                        sell_rate_text = cells[3].get_text(strip=True)
                        if sell_rate_text and sell_rate_text != "":
                            sell_rate = float(sell_rate_text)
                            pub_time = cells[-1].get_text(strip=True)
                            now = datetime.now(TIMEZONE)
                            return {
                                "currency": "GBP",
                                "currency_name": currency_name,
                                "sell_rate": sell_rate,
                                "pub_time": pub_time,
                                "timestamp": now.isoformat(),
                                "fetch_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                                "date": now.strftime("%Y-%m-%d"),
                            }
        return None
    except Exception as e:
        print(f"获取汇率失败: {e}", file=sys.stderr)
        return None


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "history": [],
        "last_alert_rate": None,
        "last_alert_time": None,
        "alerts": [],
    }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def should_alert(data, current_rate, threshold):
    if current_rate >= threshold:
        return False

    last_alert_rate = data.get("last_alert_rate")
    if last_alert_rate is None:
        return True

    if current_rate < last_alert_rate - 0.01:
        return True

    return False


def load_or_create_calendar():
    if os.path.exists(ICS_FILE):
        try:
            with open(ICS_FILE, "rb") as f:
                content = f.read()
                if len(content.strip()) > 0:
                    return Calendar.from_ical(content)
        except:
            pass

    cal = Calendar()
    cal.add("prodid", "-//GBP Rate Alert//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", "GBP Rate Alerts")
    cal.add("x-wr-timezone", "Asia/Shanghai")
    cal.add("x-published-ttl", "PT10M")
    cal.add_component(create_vtimezone())
    return cal


def add_event_to_calendar(cal, rate_info, threshold):
    now = datetime.now(TIMEZONE)
    event_uid = f"gbp-alert-{now.strftime('%Y%m%d%H%M%S')}@gbp-monitor"

    event = Event()
    event.add("dtstamp", now.astimezone(UTC))
    event.add("uid", event_uid)
    event.add("summary", f"GBP Sell Rate: {rate_info['sell_rate']} (Below {threshold})")

    description = (
        f"Currency: GBP\n"
        f"Sell Rate: {rate_info['sell_rate']}\n"
        f"BOC Published: {rate_info['pub_time']}\n"
        f"Check Time: {rate_info['fetch_time']}\n"
        f"Threshold: {threshold}\n"
        f"Status: Below threshold - consider buying!"
    )
    event.add("description", description)
    event.add("dtstart", now)
    event.add("dtend", now + timedelta(minutes=15))
    event.add("priority", 5)
    event.add("status", "CONFIRMED")
    event.add("transp", "OPAQUE")
    event.add("created", now.astimezone(UTC))
    event.add("last-modified", now.astimezone(UTC))

    cal.add_component(event)

    with open(ICS_FILE, "wb") as f:
        f.write(cal.to_ical())

    return ICS_FILE


def send_bark(rate_info, threshold, bark_url, bark_device_key):
    if not bark_device_key:
        print("Bark未配置，跳过推送")
        return False

    try:
        title = "💰 英镑汇率低于阈值!"
        body = (
            f"卖出价: {rate_info['sell_rate']}\n"
            f"阈值: {threshold}\n"
            f"时间: {rate_info['fetch_time']}"
        )

        # 防止 URL 多余斜杠
        url = f"{bark_url.rstrip('/')}/{bark_device_key}"

        payload = {
            "title": title,
            "body": body,
            "sound": "alarm",
            "group": "汇率提醒",
            "icon": "https://www.boc.cn/favicon.ico",
        }

        resp = requests.post(
            url,
            json=payload,
            timeout=10
        )

        result = resp.json()

        if result.get("code") == 200:
            print("Bark推送成功")
            return True

        print(f"Bark response: {result}", file=sys.stderr)
        return False

    except Exception as e:
        print(f"Bark推送失败: {e}", file=sys.stderr)
        return False


def send_pushdeer(rate_info, threshold, pushdeer_key):
    if not pushdeer_key:
        return False
    try:
        title = "💰 英镑汇率低于阈值!"
        text = f"卖出价: {rate_info['sell_rate']}\n阈值: {threshold}\n时间: {rate_info['fetch_time']}"
        url = "https://api2.pushdeer.com/message/push"
        data = {
            "pushkey": pushdeer_key,
            "text": title,
            "desp": text,
            "type": "text",
        }
        resp = requests.post(url, data=data, timeout=10)
        result = resp.json()
        return result.get("code") == 0
    except Exception as e:
        print(f"PushDeer推送失败: {e}", file=sys.stderr)
        return False


def send_serverchan(rate_info, threshold, sendkey):
    if not sendkey:
        return False
    try:
        title = "💰 英镑汇率低于阈值!"
        desp = f"## 英镑汇率提醒\n\n- 现汇卖出价: **{rate_info['sell_rate']}**\n- 设定阈值: {threshold}\n- 中行发布时间: {rate_info['pub_time']}\n- 监测时间: {rate_info['fetch_time']}\n\n建议: 可以考虑购汇！"
        url = f"https://sctapi.ftqq.com/{sendkey}.send"
        data = {"title": title, "desp": desp}
        resp = requests.post(url, data=data, timeout=10)
        result = resp.json()
        return result.get("code") == 0
    except Exception as e:
        print(f"Server酱推送失败: {e}", file=sys.stderr)
        return False


def send_telegram(rate_info, threshold, bot_token, chat_id):
    if not bot_token or not chat_id:
        return False
    try:
        text = (
            f"💰 *英镑汇率低于阈值!*\n\n"
            f"现汇卖出价: *{rate_info['sell_rate']}*\n"
            f"设定阈值: {threshold}\n"
            f"中行发布时间: {rate_info['pub_time']}\n"
            f"监测时间: {rate_info['fetch_time']}\n\n"
            f"建议: 可以考虑购汇！"
        )
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        resp = requests.post(url, data=data, timeout=10)
        result = resp.json()
        return result.get("ok") == True
    except Exception as e:
        print(f"Telegram推送失败: {e}", file=sys.stderr)
        return False


def send_wxpusher(rate_info, threshold, token, uids_str):
    if not token or not uids_str:
        return False
    try:
        uids = [uid.strip() for uid in uids_str.split(",") if uid.strip()]
        if not uids:
            return False
        content = (
            f"💰 <b>英镑汇率低于阈值!</b><br/><br/>"
            f"现汇卖出价: <b>{rate_info['sell_rate']}</b><br/>"
            f"设定阈值: {threshold}<br/>"
            f"中行发布时间: {rate_info['pub_time']}<br/>"
            f"监测时间: {rate_info['fetch_time']}<br/><br/>"
            f"建议: 可以考虑购汇！"
        )
        url = "https://wxpusher.zjiecode.com/api/send/message"
        data = {
            "appToken": token,
            "content": content,
            "contentType": 2,
            "uids": uids,
        }
        resp = requests.post(url, json=data, timeout=10)
        result = resp.json()
        return result.get("code") == 1000
    except Exception as e:
        print(f"WxPusher推送失败: {e}", file=sys.stderr)
        return False


def push_notifications(rate_info, threshold):
    bark_url = os.getenv("BARK_URL") or "https://api.day.app"
    bark_device_key = os.getenv("BARK_DEVICE_KEY", "")
    pushdeer_key = os.getenv("PUSHDEER_KEY", "")
    serverchan_key = os.getenv("SERVERCHAN_SENDKEY", "")
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    wxpusher_token = os.getenv("WXPUSHER_TOKEN", "")
    wxpusher_uids = os.getenv("WXPUSHER_UIDS", "")

    results = {}
    results["bark"] = send_bark(rate_info, threshold, bark_url, bark_device_key)
    results["pushdeer"] = send_pushdeer(rate_info, threshold, pushdeer_key)
    results["serverchan"] = send_serverchan(rate_info, threshold, serverchan_key)
    results["telegram"] = send_telegram(rate_info, threshold, tg_token, tg_chat_id)
    results["wxpusher"] = send_wxpusher(rate_info, threshold, wxpusher_token, wxpusher_uids)

    success = [k for k, v in results.items() if v]
    configured = []
    if bark_device_key:
        configured.append("bark")
    if pushdeer_key:
        configured.append("pushdeer")
    if serverchan_key:
        configured.append("serverchan")
    if tg_token:
        configured.append("telegram")
    if wxpusher_token:
        configured.append("wxpusher")
    fail = [k for k in configured if not results.get(k)]

    if success:
        print(f"推送成功: {', '.join(success)}")
    if fail:
        print(f"推送失败: {', '.join(fail)}", file=sys.stderr)


def generate_charts(data):
    history = data.get("history", [])
    if len(history) < 2:
        print("历史数据不足，暂不生成图表")
        return

    timestamps = []
    rates = []
    for item in history:
        try:
            ts = datetime.fromisoformat(item["timestamp"])
            timestamps.append(ts)
            rates.append(item["sell_rate"])
        except:
            continue

    if len(timestamps) < 2:
        return

    now = datetime.now(TIMEZONE)

    daily_cutoff = now - timedelta(hours=24)
    daily_data = [(t, r) for t, r in zip(timestamps, rates) if t >= daily_cutoff]
    if len(daily_data) >= 2:
        d_ts, d_rates = zip(*daily_data)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(d_ts, d_rates, "b-", linewidth=1.5, marker="o", markersize=2)
        ax.fill_between(d_ts, d_rates, alpha=0.1, color="blue")
        ax.set_title("GBP/CNY - Last 24 Hours", fontsize=14, fontweight="bold")
        ax.set_ylabel("Sell Rate (100 GBP to CNY)")
        ax.set_xlabel("Time")
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M", tz=TIMEZONE))
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "daily.png"), dpi=100)
        plt.close()
        print(f"日趋势图已生成 ({len(daily_data)} 个数据点)")

    weekly_cutoff = now - timedelta(days=7)
    weekly_data = [(t, r) for t, r in zip(timestamps, rates) if t >= weekly_cutoff]
    if len(weekly_data) >= 2:
        daily_agg = {}
        for t, r in weekly_data:
            day = t.strftime("%Y-%m-%d")
            if day not in daily_agg:
                daily_agg[day] = {"rates": [], "dt": t}
            daily_agg[day]["rates"].append(r)

        days = sorted(daily_agg.keys())
        day_ts = [daily_agg[d]["dt"] for d in days]
        day_avg = [np.mean(daily_agg[d]["rates"]) for d in days]
        day_high = [max(daily_agg[d]["rates"]) for d in days]
        day_low = [min(daily_agg[d]["rates"]) for d in days]

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(day_ts, day_avg, "b-", linewidth=2, marker="o", label="Avg", markersize=4)
        ax.fill_between(day_ts, day_low, day_high, alpha=0.15, color="blue", label="Range")
        ax.set_title("GBP/CNY - Last 7 Days", fontsize=14, fontweight="bold")
        ax.set_ylabel("Sell Rate (100 GBP to CNY)")
        ax.set_xlabel("Date")
        ax.grid(True, alpha=0.3)
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d", tz=TIMEZONE))
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "weekly.png"), dpi=100)
        plt.close()
        print(f"周趋势图已生成 ({len(days)} 天数据)")

    monthly_cutoff = now - timedelta(days=30)
    monthly_data = [(t, r) for t, r in zip(timestamps, rates) if t >= monthly_cutoff]
    if len(monthly_data) >= 2:
        daily_agg = {}
        for t, r in monthly_data:
            day = t.strftime("%Y-%m-%d")
            if day not in daily_agg:
                daily_agg[day] = {"rates": [], "dt": t}
            daily_agg[day]["rates"].append(r)

        days = sorted(daily_agg.keys())
        day_ts = [daily_agg[d]["dt"] for d in days]
        day_avg = [np.mean(daily_agg[d]["rates"]) for d in days]
        day_high = [max(daily_agg[d]["rates"]) for d in days]
        day_low = [min(daily_agg[d]["rates"]) for d in days]

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(day_ts, day_avg, "g-", linewidth=2, marker="o", label="Avg", markersize=3)
        ax.fill_between(day_ts, day_low, day_high, alpha=0.15, color="green", label="Range")
        ax.set_title("GBP/CNY - Last 30 Days", fontsize=14, fontweight="bold")
        ax.set_ylabel("Sell Rate (100 GBP to CNY)")
        ax.set_xlabel("Date")
        ax.grid(True, alpha=0.3)
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d", tz=TIMEZONE))
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "monthly.png"), dpi=100)
        plt.close()
        print(f"月趋势图已生成 ({len(days)} 天数据)")

    all_daily_agg = {}
    for t, r in zip(timestamps, rates):
        day = t.strftime("%Y-%m-%d")
        if day not in all_daily_agg:
            all_daily_agg[day] = {"rates": [], "dt": t}
        all_daily_agg[day]["rates"].append(r)

    if len(all_daily_agg) >= 2:
        days = sorted(all_daily_agg.keys())
        day_ts = [all_daily_agg[d]["dt"] for d in days]
        day_avg = [np.mean(all_daily_agg[d]["rates"]) for d in days]
        day_high = [max(all_daily_agg[d]["rates"]) for d in days]
        day_low = [min(all_daily_agg[d]["rates"]) for d in days]

        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(day_ts, day_avg, "purple", linewidth=2, marker="o", label="Avg", markersize=3)
        ax.fill_between(day_ts, day_low, day_high, alpha=0.12, color="purple", label="Range")
        ax.set_title("GBP/CNY - Historical Trend", fontsize=14, fontweight="bold")
        ax.set_ylabel("Sell Rate (100 GBP to CNY)")
        ax.set_xlabel("Date")
        ax.grid(True, alpha=0.3)
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d", tz=TIMEZONE))
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "all.png"), dpi=100)
        plt.close()
        print(f"历史趋势图已生成 ({len(days)} 天数据)")


def update_latest_file(rate_info, threshold):
    latest_info = {
        "current_rate": rate_info["sell_rate"],
        "threshold": threshold,
        "pub_time": rate_info["pub_time"],
        "fetch_time": rate_info["fetch_time"],
        "is_below_threshold": rate_info["sell_rate"] < threshold,
        "updated_at": datetime.now(TIMEZONE).isoformat(),
    }
    with open("latest_rate.json", "w", encoding="utf-8") as f:
        json.dump(latest_info, f, ensure_ascii=False, indent=2)


def cleanup_old_history(data):
    cutoff = datetime.now(TIMEZONE) - timedelta(days=90)
    history = data.get("history", [])
    new_history = []
    for item in history:
        try:
            ts = datetime.fromisoformat(item["timestamp"])
            if ts >= cutoff:
                new_history.append(item)
        except:
            new_history.append(item)
    data["history"] = new_history
    return data


def main():
    if not is_workday():
        today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
        print(f"Today is weekend/non-workday, skipping.")
        return

    threshold_str = os.getenv("THRESHOLD_PRICE", "920")
    try:
        threshold = float(threshold_str)
    except ValueError:
        threshold = 920.0
        print(f"Invalid threshold, using default: {threshold}", file=sys.stderr)

    print(f"Monitoring threshold: {threshold}")
    print(f"Fetching BOC GBP sell rate...")

    rate_info = get_boc_gbp_rate()
    if not rate_info:
        print("Failed to fetch GBP rate")
        sys.exit(1)

    print(f"Success!")
    print(f"  Currency: {rate_info['currency_name']}")
    print(f"  Sell Rate: {rate_info['sell_rate']}")
    print(f"  Published: {rate_info['pub_time']}")
    print(f"  Fetch Time: {rate_info['fetch_time']}")

    update_latest_file(rate_info, threshold)

    data = load_data()
    data["history"].append(rate_info)
    data = cleanup_old_history(data)

    print(f"Generating charts...")
    generate_charts(data)

    if rate_info["sell_rate"] < threshold:
        print(f"ALERT: Current rate {rate_info['sell_rate']} is below threshold {threshold}!")

        if should_alert(data, rate_info["sell_rate"], threshold):
            print("Adding calendar event...")
            cal = load_or_create_calendar()
            ics_file = add_event_to_calendar(cal, rate_info, threshold)
            print(f"Calendar updated: {ics_file}")

            print("Sending push notifications...")
            push_notifications(rate_info, threshold)

            data["last_alert_rate"] = rate_info["sell_rate"]
            data["last_alert_time"] = rate_info["timestamp"]
            data["alerts"].append(
                {
                    "time": rate_info["fetch_time"],
                    "rate": rate_info["sell_rate"],
                    "threshold": threshold,
                }
            )
            print("Alert sent!")
        else:
            last_rate = data.get("last_alert_rate", threshold)
            print(f"Current rate {rate_info['sell_rate']} not lower than last alert rate {last_rate}, skipping.")
    else:
        print(f"Current rate {rate_info['sell_rate']} is above threshold {threshold}, no alert needed.")
        data["last_alert_rate"] = None

    save_data(data)


if __name__ == "__main__":
    main()
