import os
import logging
import asyncio
import base64
import json
import urllib.parse
from io import BytesIO
from aiohttp import web
import requests as req

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', 8080))
TG_API = f'https://api.telegram.org/bot{BOT_TOKEN}'
CHANNEL = '@Kraken_mobile'
SAYT_URL = 'https://krakenmobileshop.netlify.app/'
SHEET_URL = os.environ.get('SHEET_URL', '')

# Cache — har 5 daqiqada yangilanadi
_konkurs_cache = {'data': None, 'time': 0}
user_states = {}

def send_message(chat_id, text, keyboard=None):
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if keyboard:
        payload['reply_markup'] = keyboard
    try:
        req.post(f'{TG_API}/sendMessage', json=payload, timeout=10)
    except Exception as e:
        logger.error(f'sendMessage error: {e}')

def is_channel_member(user_id):
    try:
        r = req.get(f'{TG_API}/getChatMember',
            params={'chat_id': CHANNEL, 'user_id': user_id},
            timeout=8)
        status = r.json().get('result', {}).get('status', '')
        logger.info(f'channel check {user_id}: {status}')
        return status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f'getChatMember error: {e}')
        return True  # xato bo'lsa bloklamas

def get_active_konkurs():
    import time
    now = time.time()
    if _konkurs_cache['data'] and now - _konkurs_cache['time'] < 300:
        return _konkurs_cache['data']
    if not SHEET_URL:
        return None
    try:
        encoded = urllib.parse.quote('direct')
        url = f"{SHEET_URL}?action=getKonkurs&callback=direct"
        r = req.get(url, timeout=10)
        text = r.text.strip()
        if text.startswith('direct(') and text.endswith(')'):
            data = json.loads(text[7:-1])
        else:
            data = r.json()
        if data and data.get('id'):
            _konkurs_cache['data'] = data
            _konkurs_cache['time'] = now
            return data
    except Exception as e:
        logger.error(f'getKonkurs error: {e}')
    return None

def save_participant(konkurs_id, user_id, username, full_name, phone):
    if not SHEET_URL:
        return None
    try:
        data = {
            'konkurs_id': str(konkurs_id),
            'user_id': str(user_id),
            'username': username or '',
            'full_name': full_name or '',
            'phone': str(phone),
        }
        encoded = urllib.parse.quote(json.dumps(data, ensure_ascii=False))
        url = f"{SHEET_URL}?action=joinKonkurs&callback=direct&data={encoded}"
        r = req.get(url, timeout=15)
        text = r.text.strip()
        logger.info(f'save response: {text[:200]}')
        if text.startswith('direct(') and text.endswith(')'):
            return json.loads(text[7:-1])
        return r.json()
    except Exception as e:
        logger.error(f'save_participant error: {e}')
        return None

# === /start ===
async def handle_start(chat_id, deep_link='', user={}):
    if deep_link == 'konkurs':
        await handle_konkurs_join(chat_id, user)
        return
    gif_file_id = 'CgACAgIAAxkBAAMvaf3qQRiu8Kk4qBQZdISLTSIIDJYAAsGZAAJG3OhLX3fB57eReYE7BA'
    req.post(f'{TG_API}/sendAnimation', json={
        'chat_id': chat_id,
        'animation': gif_file_id,
        'caption': (
            "🇺🇿 *Barcha aktual smartfonlarimiz saytimizga joylandi*\n"
            "🇷🇺 *Все актуальные смартфоны уже на нашем сайте*\n\n"
            "Kirish uchun bosing / Нажмите, чтобы перейти 👇"
        ),
        'parse_mode': 'Markdown',
        'reply_markup': {"inline_keyboard": [[{
            "text": "🛍 Saytga kirish / Перейти на сайт",
            "web_app": {"url": SAYT_URL}
        }]]}
    }, timeout=10)

# === KONKURS ===
async def handle_konkurs_join(chat_id, user={}):
    konkurs = get_active_konkurs()
    if not konkurs:
        send_message(chat_id, "😕 Hozirda aktiv konkurs yo'q.\n\nKanalimizni kuzating: @Kraken_mobile")
        return

    # Kanal a'zoligini tekshirish
    if not is_channel_member(chat_id):
        send_message(chat_id,
            "❗ Konkursda qatnashish uchun avval kanalga a'zo bo'ling!\n\n"
            "👉 @Kraken_mobile\n\n"
            "A'zo bo'lgach, /konkurs yozing.",
            keyboard={"inline_keyboard": [[{
                "text": "📢 Kanalga a'zo bo'lish",
                "url": "https://t.me/Kraken_mobile"
            }]]})
        return

    # State ga yozib darhol telefon so'raymiz
    user_states[chat_id] = {
        'step': 'phone',
        'konkurs_id': konkurs['id'],
        'prize': konkurs.get('prize', ''),
        'user_id': user.get('id', chat_id),
        'username': user.get('username', ''),
        'full_name': ((user.get('first_name') or '') + ' ' + (user.get('last_name') or '')).strip()
    }

    send_message(chat_id,
        f"🎁 *{konkurs.get('prize', 'Sovrin')}* konkursida qatnashish uchun\n"
        f"📱 Telefon raqamingizni ulashing:",
        keyboard={
            "keyboard": [[{"text": "📱 Raqamni ulashish", "request_contact": True}]],
            "resize_keyboard": True,
            "one_time_keyboard": True
        })

async def handle_phone(chat_id, phone, user):
    state = user_states.pop(chat_id, {})
    if not state:
        return

    full_name = state.get('full_name') or user.get('first_name', '')
    username = state.get('username') or user.get('username', '')
    user_id = state.get('user_id', chat_id)
    konkurs_id = state.get('konkurs_id', '')
    prize = state.get('prize', '')

    res = save_participant(konkurs_id, user_id, username, full_name, phone)
    _konkurs_cache['time'] = 0

    if res and res.get('msg') == 'already':
        send_message(chat_id,
            "✅ Siz allaqachon bu konkursda qatnashyapsiz!\n\n🍀 Omad tilaymiz!",
            keyboard={"remove_keyboard": True})
        return

    # 1. Tabriklash + klaviatura olib tashlash
    send_message(chat_id,
        f"🎉 *{prize}* konkursiga muvaffaqiyatli qatnashdingiz!",
        keyboard={"remove_keyboard": True})

    # 2. Reklama + mini app
    req.post(f'{TG_API}/sendAnimation', json={
        'chat_id': chat_id,
        'animation': 'CgACAgIAAxkBAAMvaf3qQRiu8Kk4qBQZdISLTSIIDJYAAsGZAAJG3OhLX3fB57eReYE7BA',
        'caption': (
            "🇺🇿 *Konkurs tugagunicha smartfonlarimizni ko'rishingiz mumkin!*\n"
            "🇷🇺 *Пока идёт конкурс — смотрите наши смартфоны!*\n\n"
            "📱 Barcha aktual modellar saytimizda 👇"
        ),
        'parse_mode': 'Markdown',
        'reply_markup': {"inline_keyboard": [[{
            "text": "🛍 Saytga kirish / Перейти на сайт",
            "web_app": {"url": SAYT_URL}
        }]]}
    }, timeout=10)


async def webhook(request):
    try:
        data = await request.json()
        message = data.get('message', {})
        text = message.get('text', '')
        chat_id = message.get('chat', {}).get('id')
        user = message.get('from', {})
        contact = message.get('contact')

        if not chat_id:
            return web.json_response({'ok': True})

        if text.startswith('/start'):
            parts = text.split(' ', 1)
            deep_link = parts[1].strip() if len(parts) > 1 else ''
            await handle_start(chat_id, deep_link, user)

        elif text == '/konkurs':
            await handle_konkurs_join(chat_id, user)

        elif contact:
            phone = contact.get('phone_number', '')
            if chat_id in user_states:
                await handle_phone(chat_id, phone, user)

        elif text and chat_id in user_states:
            # Qo'lda yozilgan raqam
            await handle_phone(chat_id, text, user)

        return web.json_response({'ok': True})
    except Exception as e:
        logger.error(f'Webhook error: {e}')
        return web.json_response({'ok': False})

# === RASM YUKLASH ===
async def upload_image(request):
    try:
        data = await request.json()
        image_b64 = data.get('image', '')
        listing_num = data.get('num', 0)
        if not image_b64:
            return web.json_response({'error': 'No image'}, status=400)
        if ',' in image_b64:
            image_b64 = image_b64.split(',')[1]
        image_bytes = base64.b64decode(image_b64)
        r = req.post(
            f'{TG_API}/sendPhoto',
            data={'chat_id': CHANNEL, 'caption': f'📸 Elon №{listing_num}'},
            files={'photo': ('photo.jpg', BytesIO(image_bytes), 'image/jpeg')},
            timeout=30
        )
        result = r.json()
        if not result.get('ok'):
            return web.json_response({'error': result}, status=500)
        file_id = result['result']['photo'][-1]['file_id']
        fi = req.get(f'{TG_API}/getFile?file_id={file_id}').json()
        file_path = fi['result']['file_path']
        url = f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}'
        return web.json_response({'success': True, 'file_id': file_id, 'url': url})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def get_image_url(request):
    try:
        file_id = request.query.get('file_id', '')
        fi = req.get(f'{TG_API}/getFile?file_id={file_id}').json()
        file_path = fi['result']['file_path']
        url = f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}'
        return web.json_response({'url': url})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def health(request):
    return web.json_response({'status': 'ok'})

async def keep_alive():
    render_url = os.environ.get('RENDER_URL', '')
    if not render_url:
        return
    while True:
        await asyncio.sleep(600)
        try:
            req.get(f'{render_url}/health', timeout=10)
        except:
            pass

@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        return web.Response(headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        })
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

async def main():
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_post('/webhook', webhook)
    app.router.add_post('/upload', upload_image)
    app.router.add_get('/image', get_image_url)
    app.router.add_get('/health', health)
    app.router.add_route('OPTIONS', '/{path_info:.*}', lambda r: web.Response())
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    render_url = os.environ.get('RENDER_URL', '')
    if render_url:
        r = req.post(f'{TG_API}/setWebhook', json={'url': f'{render_url}/webhook'})
        logger.info(f'Webhook set: {r.json()}')
    asyncio.create_task(keep_alive())
    logger.info(f'Bot started on port {PORT}')
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
