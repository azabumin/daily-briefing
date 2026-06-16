#!/usr/bin/env python3
"""
毎朝ブリーフィング - 株価・ニュースをGmailで送信 (AI無し版)
対象銘柄: リベラウェア(218A.T), 理経(8226.T)
"""

import os
import smtplib
import urllib.request
import urllib.parse
import json
import xml.etree.ElementTree as ET
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

# ── 設定 ──────────────────────────────────────────────
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASS = os.environ["GMAIL_APP_PASS"]
TO_EMAIL   = os.environ.get("TO_EMAIL", GMAIL_USER)

STOCKS = [
    {"code": "218A.T", "name": "リベラウェア"},
    {"code": "8226.T", "name": "理経"},
]

JST = timezone(timedelta(hours=9))

# ── 株価取得 ──────────────────────────────────────────
def get_stock(code, name):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(code)}?interval=1d&range=2d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        meta   = data["chart"]["result"][0]["meta"]
        price  = meta.get("regularMarketPrice", 0)
        prev   = meta.get("chartPreviousClose", meta.get("previousClose", price))
        change = price - prev
        pct    = (change / prev * 100) if prev else 0
        arrow  = "🟢" if change >= 0 else "🔴"
        sign   = "+" if change >= 0 else ""
        return f"{arrow} {name} ({code.replace('.T','')})  ¥{price:,.0f}  {sign}{change:.0f}円 ({sign}{pct:.2f}%)"
    except Exception as e:
        return f"⚠️ {name} ({code}) 取得失敗: {e}"

# ── RSSニュース取得 ───────────────────────────────────
def get_rss(url, count=4):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            root = ET.fromstring(r.read())
        items = root.findall(".//item")[:count]
        lines = []
        for item in items:
            title = (item.findtext("title") or "").strip()
            if title:
                lines.append(f"・{title}")
        return "\n".join(lines) if lines else "ニュース取得失敗"
    except Exception as e:
        return f"取得失敗: {e}"

# ── メール送信 ────────────────────────────────────────
def send_email(subject, body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())

# ── メイン ────────────────────────────────────────────
def main():
    now  = datetime.now(JST)
    date = now.strftime("%Y/%m/%d (%a)")

    # 株価
    stocks_lines = [get_stock(s["code"], s["name"]) for s in STOCKS]
    stocks_text  = "\n".join(stocks_lines)

    # ニュース
    jp_news = get_rss("https://www3.nhk.or.jp/rss/news/cat0.xml")
    kr_news = get_rss("https://www.yonhapnewstv.co.kr/category/news/headline/feed/")

    # メール本文
    body = f"""📊 毎朝ブリーフィング｜{date}
{"="*40}

━━━ 株価状況 ━━━
{stocks_text}

━━━ 日本ニュース TOP4 (NHK) ━━━
{jp_news}

━━━ 韓国ニュース TOP4 (聯合ニュース) ━━━
{kr_news}

{"="*40}
配信時刻: {now.strftime("%H:%M")} JST
"""

    subject = f"📊 [{date}] 毎朝ブリーフィング"
    send_email(subject, body)
    print(f"✅ メール送信完了: {TO_EMAIL}")

if __name__ == "__main__":
    main()
