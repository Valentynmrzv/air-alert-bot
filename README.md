## ⚙️ Структура проєкту

```
air-alert-bot/
├── alert_sources/
│   ├── telegram_checker.py
│   ├── classifier.py (опційно)
│   └── channels.json
├── utils/
│   ├── sender.py
│   └── state_manager.py
├── main.py
├── state.json (автогенерується)
├── .env
├── requirements.txt
└── README.md
```

---

## 🔧 Необхідні змінні `.env`

```
API_ID=...
API_HASH=...
BOT_TOKEN=...
CHANNEL_ID=...
USER_CHAT_ID=...
```

---

## 🐍 Як запустити на Raspberry Pi

1. Створи віртуальне середовище:

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Встанови залежності:

```bash
pip install -r requirements.txt
```

3. Запусти бота:

```bash
python3 main.py
```

---

## 🥪 Як тестити на Replit

1. Імпортуй репозиторій або завантаж ZIP.
2. Додай секрети у вкладці **Secrets**:

   - `API_ID`
   - `API_HASH`
   - `BOT_TOKEN`
   - `CHANNEL_ID`
   - `USER_CHAT_ID`

3. Запусти файл `main.py`

---

## 📟 requirements.txt

```
python-dotenv
telethon
requests
```

---

## 🔁 Команди для Git (якщо працюєш локально)

### 1. Ініціалізація репозиторію:

```bash
git init
git remote add origin https://github.com/Valentynmrzv/air-alert-bot.git
```

### 2. Додавання змін:

```bash
git add .
git commit -m "Оновлення: стабільна версія бота"
git push origin main
```

--
