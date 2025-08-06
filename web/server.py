from aiohttp import web
from datetime import datetime

status = {
    "start_time": datetime.now(),
    "alert_active": False,
    "messages_received": 0,
    "last_messages": [],  # Тут зберігатимуться останні повідомлення
    "logs": [],           # Логи або події, які хочемо показати
}

async def index(request):
    # Проста сторінка з базовою розміткою
    html = f"""
    <!DOCTYPE html>
    <html lang="uk">
    <head>
        <meta charset="UTF-8" />
        <title>Статус Бота</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; }}
            header {{ background: #2a9d8f; color: white; padding: 1rem; font-size: 1.2rem; text-align:center; }}
            main {{ display: flex; height: calc(100vh - 3rem); }}
            aside {{ width: 30%; border-right: 1px solid #ddd; padding: 1rem; overflow-y: auto; }}
            section {{ flex-grow: 1; padding: 1rem; display: flex; flex-direction: column; }}
            #logs {{ flex-grow: 1; border-top: 1px solid #ddd; padding-top: 1rem; overflow-y: auto; background: #f9f9f9; font-size: 0.9rem; }}
            h2 {{ margin-top: 0; }}
            .alert-active {{ color: #e76f51; font-weight: bold; }}
            .alert-inactive {{ color: #264653; font-weight: normal; }}
            .message {{ margin-bottom: 0.5rem; border-bottom: 1px solid #ccc; padding-bottom: 0.3rem; }}
        </style>
    </head>
    <body>
        <header>
            Статус тривоги: <span id="alert_status" class="{ 'alert-active' if status['alert_active'] else 'alert-inactive' }">
                {"АКТИВНА" if status['alert_active'] else "ВІДСУТНЯ"}
            </span>
            | Отримано повідомлень: {status['messages_received']}
            | Час роботи: {str(datetime.now() - status['start_time']).split('.')[0]}
        </header>
        <main>
            <aside>
                <h2>Останні повідомлення</h2>
                <div id="messages">
                    {"".join([f'<div class="message">{m["text"][:100]}</div>' for m in reversed(status['last_messages'][-30:])])}
                </div>
            </aside>
            <section>
                <h2>Логи / Статус</h2>
                <div id="logs">
                    {"<br>".join(status['logs'][-30:])}
                </div>
            </section>
        </main>

        <script>
            // Автооновлення кожні 5 секунд
            async function fetchStatus() {{
                try {{
                    const res = await fetch('/status');
                    const data = await res.json();
                    document.getElementById('alert_status').textContent = data.alert_active ? "АКТИВНА" : "ВІДСУТНЯ";
                    document.getElementById('alert_status').className = data.alert_active ? "alert-active" : "alert-inactive";
                    document.getElementById('messages').innerHTML = data.last_messages.map(m => `<div class="message">${{m.text.slice(0, 100)}}</div>`).reverse().join('');
                    document.getElementById('logs').innerHTML = data.logs.slice(-30).join('<br>');
                    document.querySelector('header').innerHTML = `Статус тривоги: <span id="alert_status" class="${{data.alert_active ? "alert-active" : "alert-inactive"}}">${{data.alert_active ? "АКТИВНА" : "ВІДСУТНЯ"}}</span> | Отримано повідомлень: ${{data.messages_received}} | Час роботи: ${{data.uptime}}`;
                }} catch(e) {{
                    console.error('Fetch error:', e);
                }}
            }}
            setInterval(fetchStatus, 5000);
            fetchStatus();
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def status_handler(request):
    uptime = datetime.now() - status["start_time"]
    data = {
        "uptime": str(uptime).split('.')[0],
        "alert_active": status["alert_active"],
        "messages_received": status["messages_received"],
        "last_messages": status["last_messages"][-30:],  # останні 30
        "logs": status["logs"][-30:],  # останні 30
    }
    return web.json_response(data)

async def start_web_server():
    app = web.Application()
    app.add_routes([
        web.get('/', index),
        web.get('/status', status_handler)
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("🌐 Web server started at http://0.0.0.0:8080")

