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
ADMIN_USERNAME = 'Krakens_admin'

# Cache
_konkurs_cache = {'data': None, 'time': 0}
user_states = {}

def send_msg(chat_id, text, keyboard=None):
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if keyboard:
        payload['reply_markup'] = keyboard
    try:
        req.post(f'{TG_API}/sendMessage', json=payload, timeout=8)
    except Exception as e:
        logger.error(f'sendMessage: {e}')

def is_member(user_id):
    try:
        r = req.get(f'{TG_API}/getChatMember',
            params={'chat_id': CHANNEL, 'user_id': user_id}, timeout=6)
        status = r.json().get('result', {}).get('status', '')
        return status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f'getChatMember: {e}')
        return False

def get_konkurs():
    import time
    now = time.time()
    if _konkurs_cache['data'] and now - _konkurs_cache['time'] < 120:
        return _konkurs_cache['data']
    if not SHEET_URL:
        return None
    try:
        r = req.get(f"{SHEET_URL}?action=getKonkurs&callback=d", timeout=10)
        text = r.text.strip()
        data = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
        if data and data.get('id'):
            _konkurs_cache['data'] = data
            _konkurs_cache['time'] = now
            return data
    except Exception as e:
        logger.error(f'get_konkurs: {e}')
    return None

def save_participant(konkurs_id, user_id, username, full_name, phone):
    if not SHEET_URL:
        return None
    try:
        data = json.dumps({
            'konkurs_id': str(konkurs_id),
            'user_id': str(user_id),
            'username': username or '',
            'full_name': full_name or '',
            'phone': str(phone),
        }, ensure_ascii=False)
        r = req.get(
            f"{SHEET_URL}?action=joinKonkurs&callback=d&data={urllib.parse.quote(data)}",
            timeout=12)
        text = r.text.strip()
        return json.loads(text[2:-1]) if text.startswith('d(') else r.json()
    except Exception as e:
        logger.error(f'save_participant: {e}')
        return None

def end_konkurs(konkurs_id):
    if not SHEET_URL:
        return None
    try:
        r = req.get(
            f"{SHEET_URL}?action=endKonkurs&callback=d&id={urllib.parse.quote(str(konkurs_id))}",
            timeout=15)
        text = r.text.strip()
        return json.loads(text[2:-1]) if text.startswith('d(') else r.json()
    except Exception as e:
        logger.error(f'end_konkurs: {e}')
        return None

def not_member_msg(chat_id):
    send_msg(chat_id,
        "❗ *Konkursda qatnashish uchun kanalga a'zo bo'ling!*\n"
        "❗ *Для участия подпишитесь на канал!*",
        keyboard={"inline_keyboard": [
            [{"text": "📢 @Kraken_mobile ga a'zo bo'lish", "url": "https://t.me/Kraken_mobile"}],
            [{"text": "✅ A'zo bo'ldim — qatnashish", "callback_data": "check_member"}]
        ]})

async def start_konkurs_flow(chat_id, user):
    k = get_konkurs()
    if not k:
        send_msg(chat_id, "😕 Hozirda aktiv konkurs yo'q.\n\nKanalimizni kuzating: @Kraken_mobile")
        return

    if not is_member(chat_id):
        not_member_msg(chat_id)
        return

    user_states[chat_id] = {
        'step': 'phone',
        'konkurs_id': k['id'],
        'prize': k.get('prize', ''),
        'user_id': user.get('id', chat_id),
        'username': user.get('username', ''),
        'full_name': ((user.get('first_name') or '') + ' ' + (user.get('last_name') or '')).strip()
    }

    send_msg(chat_id,
        f"🎁 *{k.get('prize','Sovrin')}* konkursida qatnashish uchun\n"
        f"📱 Telefon raqamingizni ulashing:",
        keyboard={
            "keyboard": [[{"text": "📱 Raqamni ulashish", "request_contact": True}]],
            "resize_keyboard": True, "one_time_keyboard": True
        })

async def handle_phone(chat_id, phone, user):
    state = user_states.pop(chat_id, {})
    if not state:
        return

    # Kanal a'zoligini yana tekshirish
    if not is_member(chat_id):
        not_member_msg(chat_id)
        return

    full_name = state.get('full_name') or user.get('first_name', '')
    username = state.get('username') or user.get('username', '')
    user_id = state.get('user_id', chat_id)
    konkurs_id = state.get('konkurs_id', '')
    prize = state.get('prize', '')

    res = save_participant(konkurs_id, user_id, username, full_name, phone)
    _konkurs_cache['time'] = 0  # cache yangilash

    if res and res.get('msg') == 'already':
        send_msg(chat_id,
            "✅ Siz allaqachon bu konkursda qatnashyapsiz!\n\n🍀 Omad tilaymiz!",
            keyboard={"remove_keyboard": True})
        return

    # 1. Tabriklash
    send_msg(chat_id,
        f"🎉 *{prize}* konkursiga muvaffaqiyatli qatnashdingiz!\n\n"
        f"🏆 G'olib e'lon qilinganda kanalimizda xabar beramiz!\n"
        f"📢 @Kraken_mobile",
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

def notify_participants(konkurs_id, winner_user_id, winner_name, prize):
    """Barcha qatnashuvchilarga xabar yuborish"""
    if not SHEET_URL:
        return
    try:
        r = req.get(f"{SHEET_URL}?action=getParticipants&callback=d&id={urllib.parse.quote(str(konkurs_id))}", timeout=15)
        text = r.text.strip()
        data = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
        participants = data.get('participants', [])

        for p in participants:
            uid = p.get('user_id', '')
            if not uid:
                continue
            try:
                if str(uid) == str(winner_user_id):
                    # G'olibga maxsus xabar
                    req.post(f'{TG_API}/sendMessage', json={
                        'chat_id': uid,
                        'text': (
                            f"🏆 *Tabriklaymiz!*\n\n"
                            f"Siz *{prize}* konkursida g'olib bo'ldingiz! 🎉\n\n"
                            f"Sovg'angizni olish uchun adminga yozing 👇"
                        ),
                        'parse_mode': 'Markdown',
                        'reply_markup': {"inline_keyboard": [[{
                            "text": "📩 Adminga yozish",
                            "url": f"https://t.me/{ADMIN_USERNAME}"
                        }]]}
                    }, timeout=5)
                else:
                    # Boshqa qatnashuvchilarga
                    req.post(f'{TG_API}/sendMessage', json={
                        'chat_id': uid,
                        'text': (
                            f"🎁 *{prize}* konkursi yakunlandi!\n\n"
                            f"🏆 G'olib: *{winner_name}*\n\n"
                            f"Har oy konkurslar o'tkaziladi — kanalimizni kuzating!\n"
                            f"📢 @Kraken_mobile"
                        ),
                        'parse_mode': 'Markdown'
                    }, timeout=5)
            except:
                pass
    except Exception as e:
        logger.error(f'notify_participants: {e}')

async def webhook(request):
    try:
        data = await request.json()
        message = data.get('message', {})
        text = message.get('text', '')
        chat_id = message.get('chat', {}).get('id')
        user = message.get('from', {})
        contact = message.get('contact')

        # Callback query
        cq = data.get('callback_query', {})
        if cq:
            cq_chat = cq.get('message', {}).get('chat', {}).get('id')
            cq_user = cq.get('from', {})
            cq_data = cq.get('data', '')
            cq_id = cq.get('id')
            req.post(f'{TG_API}/answerCallbackQuery', json={'callback_query_id': cq_id}, timeout=5)
            if cq_data == 'check_member' and cq_chat:
                if is_member(cq_chat):
                    await start_konkurs_flow(cq_chat, cq_user)
                else:
                    send_msg(cq_chat,
                        "❌ Hali a'zo emassiz! Avval kanalga a'zo bo'ling.",
                        keyboard={"inline_keyboard": [
                            [{"text": "📢 Kanalga a'zo bo'lish", "url": "https://t.me/Kraken_mobile"}],
                            [{"text": "✅ A'zo bo'ldim", "callback_data": "check_member"}]
                        ]})
            return web.json_response({'ok': True})

        if not chat_id:
            return web.json_response({'ok': True})

        if text.startswith('/start'):
            parts = text.split(' ', 1)
            deep = parts[1].strip() if len(parts) > 1 else ''
            if deep == 'konkurs':
                await start_konkurs_flow(chat_id, user)
            else:
                req.post(f'{TG_API}/sendAnimation', json={
                    'chat_id': chat_id,
                    'animation': 'CgACAgIAAxkBAAMvaf3qQRiu8Kk4qBQZdISLTSIIDJYAAsGZAAJG3OhLX3fB57eReYE7BA',
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

        elif text == '/konkurs':
            await start_konkurs_flow(chat_id, user)

        elif contact and chat_id in user_states:
            phone = contact.get('phone_number', '')
            await handle_phone(chat_id, phone, user)

        elif text and chat_id in user_states:
            await handle_phone(chat_id, text, user)

        return web.json_response({'ok': True})
    except Exception as e:
        logger.error(f'Webhook: {e}')
        return web.json_response({'ok': False})

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
            timeout=30)
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
        return web.json_response({'url': f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def notify_endpoint(request):
    """Admin g'olibni aniqlaganda barcha qatnashuvchilarga xabar"""
    try:
        data = await request.json()
        konkurs_id = data.get('konkurs_id', '')
        winner_user_id = data.get('winner_user_id', '')
        winner_name = data.get('winner_name', '')
        prize = data.get('prize', '')
        if konkurs_id and winner_user_id:
            asyncio.create_task(asyncio.get_event_loop().run_in_executor(
                None, notify_participants, konkurs_id, winner_user_id, winner_name, prize))
        return web.json_response({'ok': True})
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
    app.router.add_post('/notify', notify_endpoint)
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
        logger.info(f'Webhook: {r.json()}')
    asyncio.create_task(keep_alive())
    logger.info(f'Started on port {PORT}')
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
