#!/usr/bin/env python3
"""
毎朝ブリーフィング - 株価・ニュース・AI要約をGmailで送信
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
GMAIL_USER   = os.environ["GMAIL_USER"]      # azabumin@gmail.com
GMAIL_PASS   = os.environ["GMAIL_APP_PASS"]  # 16桁アプリパスワード
TO_EMAIL     = os.environ.get("TO_EMAIL", GMAIL_USER)
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]

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
        result = data["chart"]["result"][0]
        meta   = result["meta"]
        price  = meta.get("regularMarketPrice", 0)
        prev   = meta.get("chartPreviousClose", meta.get("previousClose", price))
        change = price - prev
        pct    = (change / prev * 100) if prev else 0
        arrow  = "🟢" if change >= 0 else "🔴"
        sign   = "+" if change >= 0 else ""
        return f"{arrow} {name} ({code.replace('.T','')})  ¥{price:,.0f}  {sign}{change:+.0f} ({sign}{pct:.2f}%)"
    except Exception as e:
        return f"⚠️ {name} ({code}) 取得失敗: {e}"

# ── RSSニュース取得 ───────────────────────────────────
def get_rss(url, label, count=4):
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

# ── Claude AI ブリーフィング ───────────────────────────
def get_ai_briefing(stocks_text, jp_news, kr_news):
    try:
        prompt = f"""以下の情報をもとに、投資家向けの簡潔な朝のブリーフィングを日本語で200字以内で書いてください。

【株価】
{stocks_text}

【日本ニュース】
{jp_news}

【韓国ニュース】
{kr_news}

市場への影響、注目点を簡潔にまとめてください。"""

        payload = json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        return data["content"][0]["text"].strip()
    except Exception as e:
        return f"AI ブリーフィング生成失敗: {e}"

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
    jp_news = get_rss(
        "https://www3.nhk.or.jp/rss/news/cat0.xml",
        "NHK日本ニュース"
    )
    kr_news = get_rss(
        "https://www.yonhapnewstv.co.kr/category/news/headline/feed/",
        "韓国連合ニュース"
    )

    # AI ブリーフィング
    ai_text = get_ai_briefing(stocks_text, jp_news, kr_news)

    # メール本文
    body = f"""📊 毎朝ブリーフィング｜{date}
{"="*40}

━━━ 株価状況 ━━━
{stocks_text}

━━━ 日本ニュース TOP4 (NHK) ━━━
{jp_news}

━━━ 韓国ニュース TOP4 (聯合ニュース) ━━━
{kr_news}

━━━ AI ブリーフィング ━━━
{ai_text}

{"="*40}
配信時刻: {now.strftime("%H:%M")} JST
"""

    subject = f"📊 [{date}] 毎朝ブリーフィング"
    send_email(subject, body)
    print(f"✅ メール送信完了: {TO_EMAIL}")

if __name__ == "__main__":
    main()
