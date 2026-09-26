# ncdr-telegram-alert
ncdr-telegram-alert

# NCDR Telegram Alert

NCDR 民生示警 → GitHub Actions → Telegram Bot

## 功能

- 每 5 分鐘檢查 NCDR
- 桃園市
- 新竹市
- 新竹縣
- 地震
- 颱風
- 豪雨
- 大雨
- 淹水
- 土石流
- 停班停課
- CAP ID 防重複
- 警報內容變更偵測
- Telegram 自動推播
- 30 天狀態自動清理
- API 異常通知

## GitHub Secrets

需要：

NCDR_API_KEY

NCDR_ALERT_LIST_URL

TELEGRAM_BOT_TOKEN

TELEGRAM_CHAT_ID

## 手動執行

GitHub:

Actions
→ NCDR Telegram Alert
→ Run workflow

## 設定地區與災害類型

修改：

config/config.json

即可。
