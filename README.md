# Air Alert Bot

Telegram-бот для відстеження повітряних тривог, пересилання новин під час тривоги та окремих зведень з обстановкою.

## Що вміє бот

- Ловить офіційні повідомлення `air_alert_ua` про тривогу і відбій.
- Реагує на одиночні та багаторайонні повідомлення.
- Під час тривоги пересилає релевантні новини з моніторингових каналів.
- Навіть без тривоги пересилає окремі зведення з `war_monitor` і `ukraine_pyxx`.
- Працює як сервіс на Raspberry Pi через `systemd`.

## Структура проєкту

```text
air-alert-bot/
├── alert_sources/
│   ├── channels.json
│   └── telegram_checker.py
├── utils/
├── web/
├── main.py
├── requirements.txt
├── state.json
└── README.md
```

## Необхідні змінні `.env`

```env
API_ID=...
API_HASH=...
BOT_TOKEN=...
CHANNEL_ID=...
USER_CHAT_ID=...
TG_2FA_PASSWORD=...
```

## Перший запуск на Raspberry Pi

```bash
cd /home/vlntnmrzv
git clone https://github.com/Valentynmrzv/air-alert-bot.git
cd air-alert-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Після цього:

1. Створи `.env`
2. Авторизуй Telegram-сесію
3. Запусти бота вручну або як сервіс

## Ручний запуск

```bash
cd /home/vlntnmrzv/air-alert-bot
source venv/bin/activate
python main.py
```

## Сервіс systemd

Запуск:

```bash
sudo systemctl start air-alert-bot.service
```

Зупинка:

```bash
sudo systemctl stop air-alert-bot.service
```

Перезапуск:

```bash
sudo systemctl restart air-alert-bot.service
```

Статус:

```bash
sudo systemctl status air-alert-bot.service
```

Логи в реальному часі:

```bash
sudo journalctl -u air-alert-bot.service -f
```

Останні 2000 рядків логу:

```bash
sudo journalctl -u air-alert-bot.service -n 2000
```

Перевірка автозапуску:

```bash
sudo systemctl is-enabled air-alert-bot.service
```

Увімкнути автозапуск після перезавантаження:

```bash
sudo systemctl enable air-alert-bot.service
```

## Оновлення коду з Git на Raspberry Pi

Стандартне оновлення:

```bash
cd /home/vlntnmrzv/air-alert-bot
git pull origin main
sudo systemctl restart air-alert-bot.service
sudo journalctl -u air-alert-bot.service -f
```

Якщо є локальні зміни і `git pull` не проходить:

```bash
cd /home/vlntnmrzv/air-alert-bot
git status
git restore alert_sources/telegram_checker.py
git pull origin main
sudo systemctl restart air-alert-bot.service
```

Якщо хочеш спершу зберегти локальний файл:

```bash
cd /home/vlntnmrzv/air-alert-bot
cp alert_sources/telegram_checker.py alert_sources/telegram_checker.py.bak
git restore alert_sources/telegram_checker.py
git pull origin main
```

Оновлення залежностей після зміни `requirements.txt`:

```bash
cd /home/vlntnmrzv/air-alert-bot
source venv/bin/activate
pip install -r requirements.txt
deactivate
sudo systemctl restart air-alert-bot.service
```

## Авторизація Telegram-сесії

Запуск без збереження QR у файл:

```bash
cd /home/vlntnmrzv/air-alert-bot
source venv/bin/activate
python qr_session_no_prompt.py
```

Запис QR/сесії у файл:

```bash
cd /home/vlntnmrzv/air-alert-bot
source venv/bin/activate
python qr_session_to_file.py
```

Перевірка, чи жива сесія:

```bash
cd /home/vlntnmrzv/air-alert-bot
source venv/bin/activate
python check_session.py
```

## Корисні команди для діагностики

Час і синхронізація:

```bash
date
timedatectl
```

Навантаження:

```bash
top -b -n 1 | head -20
free -h
df -h
```

Мережа:

```bash
ping -c 20 1.1.1.1
ping -c 20 8.8.8.8
```

Останні 200 рядків логу сервісу:

```bash
sudo journalctl -u air-alert-bot.service -n 200
```

## Локальна розробка

Запуск:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Перевірка синтаксису:

```bash
python -c "from pathlib import Path; [compile(Path(p).read_text(encoding='utf-8'), p, 'exec') for p in ['main.py', 'alert_sources/telegram_checker.py', 'utils/filter.py', 'test_filter_official.py']]"
```

## Git-команди для розробки

Статус:

```bash
git status
```

Додати зміни:

```bash
git add .
```

Коміт:

```bash
git commit -m "Describe your change"
```

Пуш:

```bash
git push origin main
```

## Швидка шпаргалка

Оновити код і перезапустити бота:

```bash
cd /home/vlntnmrzv/air-alert-bot
git pull origin main
sudo systemctl restart air-alert-bot.service
sudo journalctl -u air-alert-bot.service -f
```

Запустити вручну:

```bash
cd /home/vlntnmrzv/air-alert-bot
source venv/bin/activate
python main.py
```

Подивитися лог:

```bash
sudo journalctl -u air-alert-bot.service -f
```
