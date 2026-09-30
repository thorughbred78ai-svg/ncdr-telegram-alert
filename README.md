# ncdr-telegram-alert

NCDR Telegram Alert Bot

自動取得台灣 {"fallbackMarkdown":"國家災害防救科技中心","reference":{"alt":"國家災害防救科技中心","category":"organization","extra_params":{"disambiguation":"NCDR Taiwan disaster alerts"},"name":"國家災害防救科技中心","prompt_text":"國家災害防救科技中心","status":"done","type":"entity"},"referenceKey":"0","showLoginRequiredCard":false}（NCDR）即時防災資訊，依指定地區與災害類型進行過濾，並透過 Telegram Bot 推播災害示警。

目前主要監控：

桃園市

新北市

支援災害類型：

地震

颱風

豪雨

大雨

淹水

土石流

停班停課

功能
1. NCDR Atom Feed

程式使用 NCDR Atom Feed：

https://alerts.ncdr.nat.gov.tw/RssAtomFeed.ashx


會先取得 Atom Feed，再針對符合設定的災害類型下載對應 CAP 詳細資料。

NCDR Feed 本身通常包含大量歷史或其他類型的警報，因此程式會先進行類型過濾，再下載符合類型的 CAP。

2. 災害類型過濾

災害類型由：

config/config.json


控制。

目前設定：

{
  "areas": [
    "桃園市",
    "新北市"
  ],
  "alert_types": [
    "地震",
    "颱風",
    "豪雨",
    "大雨",
    "淹水",
    "土石流",
    "停班停課"
  ]
}


程式會比對：

Atom title

Atom category

CAP event

只要其中符合設定的災害類型，就進一步進行地區判斷。

地區過濾
3. 一般災害

颱風、豪雨、大雨、淹水、土石流、停班停課等非地震災害，主要使用 CAP 的：

areaDesc


進行地區判斷。

例如 CAP：

areaDesc = 桃園市


或：

areaDesc = 新北市


即可符合設定。

如果 CAP 沒有提供符合地區的資訊，程式也會使用 Atom summary 作為備援判斷。

地震處理
4. 地震使用震度地區判斷

地震不能只看震央位置。

例如：

花蓮縣政府東方 136.0 公里


即使震央位於花蓮外海，桃園市或新北市仍可能有震度。

因此地震會讀取 CAP 裡各個 area 的：

areaDesc


以及：

geocode


例如：

areaDesc = 最大震度1級地區


並讀取：

valueName = Taiwan_Geocode_103


例如：

value = 10003


再將縣市代碼轉換為縣市名稱。

5. Taiwan_Geocode_103

目前 NCDR 地震 CAP 實際使用：

Taiwan_Geocode_103


因此程式不再只依賴：

Taiwan_Geocode_100


地震判斷會從所有地震 area 的 geocode 找出實際受到震度影響的縣市。

例如：

最大震度1級地區
    Taiwan_Geocode_103 = 10003


會判斷為：

桃園市


只要震度區域包含：

桃園市


或：

新北市


就會進入推播流程。

6. 地震不使用震央所在地作為唯一判斷

例如：

花蓮縣政府東方 136 公里


並不代表只有花蓮受到影響。

實際判斷使用：

震度區域


因此可以正確處理：

震央：花蓮外海

最大震度：
桃園市 1 級
新北市 1 級


這種情況。

Telegram
7. Telegram Bot 推播

符合條件的 Alert 會透過 Telegram Bot 發送。

需要設定：

TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID


Telegram 發送成功時會取得：

message_id


並保存至 state。

例如：

TELEGRAM HTTP STATUS: 200
TELEGRAM MESSAGE ID: 199

8. Telegram 錯誤處理

Telegram API 發生錯誤時，程式會顯示完整 API 回應。

例如：

TELEGRAM HTTP STATUS: 400

========== TELEGRAM ERROR ==========
response_text = {
  "ok": false,
  "error_code": 400,
  "description": "Bad Request: chat not found"
}
====================================


方便確認：

Chat ID 是否正確

Bot 是否加入群組

Bot 是否有發送權限

Telegram API 是否拒絕訊息

12 小時去重
9. 相同 Alert 12 小時內不重複推播

程式會使用 Alert 的：

id


作為主要識別。

例如：

CWA-EQ115067-2026-0930-130024


第一次看到：

NEW ALERT


成功推播後，會記錄：

hash
sent_at
telegram_message_id

10. 12 小時內

如果相同 Alert ID 在 12 小時內再次從 NCDR Feed 出現：

SKIP 12H


即使內容有些微變化，也不會再次推播。

例如：

SKIP 12H:
CWA-EQ115067-2026-0930-130024


注意：

sent_at 不會因為再次讀取 NCDR 而更新。

12 小時的計算基準仍然是「上一次實際 Telegram 推播時間」。

11. 超過 12 小時但內容沒有變

超過 12 小時後，如果：

hash


仍然相同，則：

SKIP SAME


不會重複推播。

12. 超過 12 小時且內容更新

如果：

Alert ID 相同


且：

超過 12 小時


同時：

hash 不同


則判斷為 NCDR 更新：

UPDATE


Telegram 會重新推播，訊息標題會顯示：

🔄 NCDR 災害示警更新

State
13. state.json

程式使用 state 保存推播紀錄。

state 主要保存：

{
  "CWA-EQ115067-2026-0930-130024": {
    "hash": "...",
    "sent_at": "2026-09-30T07:40:00+00:00",
    "telegram_message_id": 199
  }
}


用途：

12 小時去重

判斷 Alert 是否更新

保存 Telegram message ID

避免 GitHub Actions 每次執行都重新推播

14. State 清理

State 不會永久保存。

程式會依：

state_retention_days


清理過期資料。

預設可以設定為：

{
  "state_retention_days": 30
}

訊息格式
15. Telegram 推播內容

一般新警報：

🚨 NCDR 災害示警

━━━━━━━━━━━━━━
⚠️ 地震
━━━━━━━━━━━━━━

📍 影響地區
桃園市

🕐 生效時間
2026/9/30 下午 01:22:11

⛔ 失效時間
2026/9/30 下午 02:00:00

📋 示警內容
......

━━━━━━━━━━━━━━
資料來源：NCDR


更新警報：

🔄 NCDR 災害示警更新

專案結構

目前專案主要結構：

ncdr-telegram-alert/
│
├── config/
│   └── config.json
│
├── src/
│   ├── main.py
│   ├── ncdr.py
│   ├── telegram.py
│   └── state.py
│
├── requirements.txt
│
└── .github/
    └── workflows/
        └── ...

requirements.txt

目前使用：

requests>=2.32.0,<3

Config
16. config/config.json

範例：

{
  "areas": [
    "桃園市",
    "新北市"
  ],
  "alert_types": [
    "地震",
    "颱風",
    "豪雨",
    "大雨",
    "淹水",
    "土石流",
    "停班停課"
  ],
  "state_retention_days": 30,
  "error_notification_cooldown_minutes": 60
}

GitHub Actions
17. GitHub Actions Secrets

需要在 GitHub Repository：

Settings
→ Secrets and variables
→ Actions


設定：

NCDR_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID


目前 NCDR Atom Feed 可以直接取得資料時，NCDR_API_KEY 是否需要使用取決於實際部署設定。

18. 執行

本機：

python src/main.py


GitHub Actions：

Run python src/main.py

執行流程

整體流程：

GitHub Actions
       │
       ▼
  src/main.py
       │
       ▼
   NCDR Feed
       │
       ▼
  災害類型過濾
       │
       ├── 不符合 → SKIP
       │
       ▼
    下載 CAP
       │
       ▼
    地區判斷
       │
       ├── 不符合 → SKIP
       │
       ▼
   建立 Alert
       │
       ▼
   讀取 State
       │
       ▼
  ┌──────────────────┐
  │ 12 小時內？       │
  └────────┬─────────┘
           │
      YES  │  NO
       │   │
       ▼   ▼
   SKIP 12H
           │
           ▼
       Hash 是否相同？
        │         │
       YES       NO
        │         │
        ▼         ▼
    SKIP SAME   UPDATE
                    │
                    ▼
              Telegram
                    │
                    ▼
                 State

NCDR Filter Debug

程式會輸出過濾資訊，方便 GitHub Actions Debug。

例如：

========== NCDR FILTER SUMMARY ==========
Feed entries   = 763
Type matched   = 3
Area matched   = 2
CAP errors     = 0
Final alerts   = 2
==========================================


地震符合：

TYPE MATCH:
CWA-EQ115067-2026-0930-130024 | 地震

AREA MATCH:
CWA-EQ115067-2026-0930-130024
| type=地震
| matched_area=桃園市


不符合：

EARTHQUAKE AREA SKIP:
CWA-EQ115065-2026-0927-153302

NCDR Process Summary

主程式完成後會輸出：

========================================
NCDR PROCESS SUMMARY
NCDR alerts      = 2
NEW              = 2
UPDATE           = 0
SKIP 12 HOURS    = 0
SKIP SAME        = 0
SKIP INVALID     = 0
========================================

完成：新增 2，更新 0，12小時內跳過 0，相同內容跳過 0


欄位說明：

欄位	說明
NCDR alerts	NCDR 過濾後的警報數
NEW	第一次推播
UPDATE	超過 12 小時且內容有更新
SKIP 12 HOURS	12 小時內已推播
SKIP SAME	超過 12 小時但內容沒有變化
SKIP INVALID	缺少必要資料
錯誤通知

如果 NCDR 取得資料失敗，主程式會避免短時間內重複發送系統錯誤通知。

設定：

{
  "error_notification_cooldown_minutes": 60
}


例如：

⚠️ NCDR Bot 系統異常

目前無法取得 NCDR 資料。

目前行為摘要

目前版本的核心規則：

從 NCDR Atom Feed 取得警報。

先依災害類型過濾。

地震使用 CAP 震度區域與 Taiwan_Geocode_103 判斷。

其他災害使用 CAP areaDesc，必要時使用 Atom summary 備援。

桃園市或新北市符合即可進入推播。

第一次看到 Alert ID → Telegram 推播。

12 小時內相同 Alert ID → 不重複推播。

超過 12 小時且內容相同 → 不推播。

超過 12 小時且內容更新 → UPDATE 推播。

Telegram 成功後才寫入 state。

NCDR API 或 Telegram 發生錯誤時保留錯誤資訊供 GitHub Actions Debug。

注意事項

Telegram Bot 必須能夠對指定的 TELEGRAM_CHAT_ID 發送訊息。

如果出現：

Bad Request: chat not found


請檢查：

TELEGRAM_CHAT_ID

Bot 是否已加入群組

Bot 是否有發送訊息權限

私人聊天是否已先對 Bot 發送 /start

License

本專案為個人自動化災害資訊通知用途。

NCDR 災害資訊來源：

國家災害防救科技中心（NCDR）


Telegram 推播僅作為資訊通知用途，實際災害資訊請以官方發布內容為準。
