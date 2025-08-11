from aiohttp import web
from datetime import datetime
import asyncio
import json

# Глобальний статус
status = {
    "start_time": datetime.now(),
    "alert_active": False,
    "messages_received": 0,
    "last_messages": [],  # останні сирі повідомлення (dict)
    "logs": [],           # текстові логи
}

# ====== SSE інфраструктура ======
_subscribers: set[asyncio.Queue] = set()
_sub_lock = asyncio.Lock()

def _serialize_status():
    """Підготувати безпечний для JSON знімок статусу (дати -> ISO рядки)."""
    last_messages_serializable = []
    for msg in status["last_messages"][-30:]:
        msg_copy = dict(msg)
        if isinstance(msg_copy.get("date"), datetime):
            msg_copy["date"] = msg_copy["date"].isoformat()
        last_messages_serializable.append(msg_copy)

    return {
        "uptime": str(datetime.now() - status["start_time"]).split('.')[0],
        "alert_active": status["alert_active"],
        "messages_received": status["messages_received"],
        "last_messages": last_messages_serializable,
        "logs": status["logs"][-30:],
    }

async def push_update(snapshot: dict | None = None):
    """Публікує знімок статусу всім підписникам SSE."""
    data = snapshot or _serialize_status()
    payload = f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    async with _sub_lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(payload)
            except Exception:
                dead.append(q)
        for q in dead:
            _subscribers.discard(q)

async def sse_handler(request: web.Request):
    """SSE endpoint: /events — тримає з’єднання відкритим і шле оновлення."""
    resp = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
        }
    )
    await resp.prepare(request)

    q: asyncio.Queue = asyncio.Queue()
    async with _sub_lock:
        _subscribers.add(q)

    # Перший снапшот одразу
    await resp.write(f"data: {json.dumps(_serialize_status(), ensure_ascii=False)}\n\n".encode('utf-8'))

    try:
        while True:
            payload = await q.get()
            await resp.write(payload.encode('utf-8'))
    except (asyncio.CancelledError, ConnectionResetError, RuntimeError):
        pass
    finally:
        async with _sub_lock:
            _subscribers.discard(q)
        try:
            await resp.write_eof()
        except Exception:
            pass
    return resp
# ====== Кінець SSE інфраструктури ======


async def index(request):
    html = f"""
    <!DOCTYPE html>
    <html lang="uk">
    <head>
        <meta charset="UTF-8" />
        <title>Статус Бота</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; }}
            header {{ background: #2a9d8f; color: white; padding: 1rem; font-size: 1.1rem; text-align:center; }}
            main {{ display: grid; grid-template-columns: 340px 1fr; grid-template-rows: auto 1fr; height: calc(100vh - 3rem); }}
            .controls {{ grid-column: 1 / -1; padding: 0.8rem 1rem; border-bottom: 1px solid #ddd; display: flex; gap: 0.5rem; align-items: center; }}
            aside {{ padding: 1rem; border-right: 1px solid #ddd; overflow-y: auto; }}
            section {{ padding: 1rem; display: flex; flex-direction: column; overflow: hidden; }}
            #logs {{ flex-grow: 1; border-top: 1px solid #ddd; padding-top: 1rem; overflow-y: auto; background: #f9f9f9; font-size: 0.9rem; }}
            h2 {{ margin-top: 0; }}
            .alert-active {{ color: #e76f51; font-weight: bold; }}
            .alert-inactive {{ color: #264653; font-weight: normal; }}
            .message {{ margin-bottom: 0.5rem; border-bottom: 1px solid #ccc; padding-bottom: 0.3rem; }}
            a {{ color: #0a66c2; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            select, input[type="text"] {{ padding: 6px 8px; }}
            button {{ padding: 8px 12px; cursor: pointer; border: 0; border-radius: 8px; }}
            .btn-alarm {{ background: #e76f51; color: #fff; }}
            .btn-clear {{ background: #2a9d8f; color: #fff; }}
            .hint {{ font-size: 12px; color: #666; margin-left: 8px; }}
        </style>
    </head>
    <body>
        <header id="header_bar">
            Статус тривоги: <span id="alert_status" class="{ 'alert-active' if status['alert_active'] else 'alert-inactive' }">
                {"АКТИВНА" if status['alert_active'] else "ВІДСУТНЯ"}
            </span>
            | Отримано повідомлень: {status['messages_received']}
            | Час роботи: {str(datetime.now() - status['start_time']).split('.')[0]}
        </header>

        <div class="controls">
            <label for="district">Район:</label>
            <select id="district">
                <option value="Київська область">Київська область</option>
                <option value="Броварський район">Броварський район</option>
            </select>

            <input type="text" id="threat" placeholder="Тип загрози (необов'язково) — ракета/шахед/балістика…" style="flex:1; min-width:260px;" />

            <button class="btn-alarm" onclick="manualAlarm()">Дати тривогу</button>
            <button class="btn-clear" onclick="manualClear()">Відбій тривоги</button>
            <span class="hint">Кнопки працюють як «ручні» події — бот надішле алерт/відбій у канал.</span>
        </div>

        <main>
            <aside>
                <h2>Останні повідомлення</h2>
                <div id="messages">
                    {"".join([f'<div class="message"><a href="{m.get("url","#")}" target="_blank">{(m.get("text","") or "")[:100]}</a></div>' for m in reversed(status['last_messages'][-30:])])}
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
            function applySnapshot(data) {{
                const st = document.getElementById('alert_status');
                st.textContent = data.alert_active ? "АКТИВНА" : "ВІДСУТНЯ";
                st.className = data.alert_active ? "alert-active" : "alert-inactive";

                const header = document.getElementById('header_bar');
                header.innerHTML = `Статус тривоги: <span id="alert_status" class="${{data.alert_active ? "alert-active" : "alert-inactive"}}">${{data.alert_active ? "АКТИВНА" : "ВІДСУТНЯ"}}</span> | Отримано повідомлень: ${{data.messages_received}} | Час роботи: ${{data.uptime}}`;

                const msgs = (data.last_messages || []).map(m => `
                    <div class="message">
                        <a href="${{m.url || "#"}}" target="_blank">${{(m.text || "").slice(0,100)}}</a>
                    </div>
                `).reverse().join('');
                document.getElementById('messages').innerHTML = msgs;

                document.getElementById('logs').innerHTML = (data.logs || []).slice(-30).join('<br>');
            }}

            // Підписка на SSE
            const ev = new EventSource('/events');
            ev.onmessage = (e) => {{
                try {{
                    const data = JSON.parse(e.data);
                    applySnapshot(data);
                }} catch (err) {{
                    console.error('Bad SSE data', err);
                }}
            }};
            ev.onerror = (e) => {{
                console.warn('SSE error, fallback to polling for a while...', e);
            }};

            // Фолбек-пулінг (на випадок, якщо SSE тимчасово впаде)
            async function pollOnce() {{
                try {{
                    const res = await fetch('/status', {{ cache: 'no-store' }});
                    if (res.ok) {{
                        const data = await res.json();
                        applySnapshot(data);
                    }}
                }} catch (e) {{
                    console.error('poll error', e);
                }}
            }}
            setInterval(pollOnce, 15000);

            async function postJSON(url, body) {{
                const res = await fetch(url, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(body || {{}})
                }});
                if (!res.ok) throw new Error('Request failed');
                return await res.json();
            }}

            function readControls() {{
                const district = document.getElementById('district').value;
                const threat = document.getElementById('threat').value.trim();
                return {{ district, threat: threat || null }};
            }}

            async function manualAlarm() {{
                const data = readControls();
                try {{
                    await postJSON('/manual-alarm', data);
                }} catch(e) {{
                    console.error(e);
                    alert('Не вдалося встановити тривогу');
                }}
            }}

            async function manualClear() {{
                const data = readControls();
                try {{
                    await postJSON('/manual-clear', data);
                }} catch(e) {{
                    console.error(e);
                    alert('Не вдалося зняти тривогу');
                }}
            }}
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')


async def status_handler(request):
    """JSON-ендпоінт як фолбек та для дебага."""
    return web.json_response(_serialize_status())


# ====== Ручні події з веб-UI ======
async def manual_alarm_handler(request: web.Request):
    """
    Встановлює тривогу так, наче прийшло повідомлення з Telegram:
    штовхає "alarm" у чергу telegram_checker, оновлює логи та SSE.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    district = payload.get("district") or "Київська область"
    threat = payload.get("threat") or None

    # Локальний імпорт, щоб не створювати циклічну залежність на рівні модулів
    from alert_sources import telegram_checker as tg_checker

    now_id = int(datetime.now().timestamp() * 1000)
    fake = {
        "type": "alarm",
        "district": district,
        "text": f"[Manual] Повітряна тривога — {district} (з веб)",
        "url": "manual://web",
        "id": now_id,
    }
    if threat:
        fake["threat_type"] = threat

    await tg_checker.message_queue.put(fake)

    status["logs"].append(f"🔴 [Manual] Дано тривогу: {district}" + (f" (загроза: {threat})" if threat else ""))
    if len(status["logs"]) > 100:
        status["logs"] = status["logs"][-100:]

    await push_update()
    return web.json_response({"ok": True})


async def manual_clear_handler(request: web.Request):
    """
    Знімає тривогу як реальним повідомленням: штовхає "all_clear" у чергу.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    district = payload.get("district") or "Київська область"

    from alert_sources import telegram_checker as tg_checker

    now_id = int(datetime.now().timestamp() * 1000)
    fake = {
        "type": "all_clear",
        "district": district,
        "text": f"[Manual] Відбій тривоги — {district} (з веб)",
        "url": "manual://web",
        "id": now_id,
    }
    await tg_checker.message_queue.put(fake)

    status["logs"].append(f"🟢 [Manual] Відбій тривоги: {district}")
    if len(status["logs"]) > 100:
        status["logs"] = status["logs"][-100:]

    await push_update()
    return web.json_response({"ok": True})
# ====== Кінець ручних подій ======


async def start_web_server():
    app = web.Application()
    app.add_routes([
        web.get('/', index),
        web.get('/status', status_handler),     # фолбек
        web.get('/events', sse_handler),        # live-оновлення
        web.post('/manual-alarm', manual_alarm_handler),
        web.post('/manual-clear', manual_clear_handler),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("🌐 Web server started at http://0.0.0.0:8080")
