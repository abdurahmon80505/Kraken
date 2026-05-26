import os
import logging
import asyncio
import base64
import json
from io import BytesIO
from aiohttp import web
import requests as req

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', 8080))
TG_API = f'https://api.telegram.org/bot{BOT_TOKEN}'
CHANNEL = '@kraken_mobile_shop'
SAYT_URL = 'https://krakenmobileshop.netlify.app/'
SHEET_URL = os.environ.get('SHEET_URL', '')

# === STATE (xotirada) ===
# {chat_id: {'step': 'name'|'phone', 'name': '...', 'konkurs_id': '...'}}
user_states = {}

# === SHEETS GA YOZISH ===
def save_participant(konkurs_id, user_id, username, full_name, phone):
    if not SHEET_URL:
        return
    data = {
        'konkurs_id': konkurs_id,
        'user_id': str(user_id),
        'username': username or '',
        'full_name': full_name or '',
        'phone': phone or '',
    }
    try:
        url = f"{SHEET_URL}?action=joinKonkurs&data={json.dumps(data)}"
        req.get(url, timeout=10)
        logger.info(f'Participant saved: {full_name}')
    except Exception as e:
        logger.error(f'Sheet error: {e}')

def get_active_konkurs():
    if not SHEET_URL:
        logger.error('SHEET_URL not set!')
        return None
    try:
        url = f"{SHEET_URL}?action=getKonkurs&callback=direct"
        r = req.get(url, timeout=15)
        text = r.text.strip()
        logger.info(f'getKonkurs response: {text[:200]}')
        # callback=direct bo'lsa "direct({...})" formatda keladi
        if text.startswith('direct(') and text.endswith(')'):
            import json
            data = json.loads(text[7:-1])
        else:
            data = r.json()
        logger.info(f'getKonkurs data: {data}')
        if data and data.get('id'):
            return data
        return None
    except Exception as e:
        logger.error(f'getKonkurs error: {e}')
    return None

# === /start ===
async def handle_start(chat_id, deep_link=''):
    gif_file_id = 'CgACAgIAAxkBAAMvaf3qQRiu8Kk4qBQZdISLTSIIDJYAAsGZAAJG3OhLX3fB57eReYE7BA'
    text = (
        "🇺🇿 *Barcha aktual smartfonlarimiz saytimizga joylandi*\n"
        "🇷🇺 *Все актуальные смартфоны уже на нашем сайте*\n"
        "\n"
        "Kirish uchun bosing / Нажмите, чтобы перейти 👇"
    )
    keyboard = {
        "inline_keyboard": [
            [{
                "text": "🛍 Saytga kirish / Перейти на сайт",
                "web_app": {"url": SAYT_URL}
            }]
        ]
    }

    # Agar konkurs deep link bo'lsa
    if deep_link == 'konkurs':
        await handle_konkurs_join(chat_id)
        return

    req.post(f'{TG_API}/sendAnimation', json={
        'chat_id': chat_id,
        'animation': gif_file_id,
        'caption': text,
        'parse_mode': 'Markdown',
        'reply_markup': keyboard
    })

# === KONKURS QATNASHISH ===
async def handle_konkurs_join(chat_id):
    konkurs = get_active_konkurs()
    if not konkurs:
        req.post(f'{TG_API}/sendMessage', json={
            'chat_id': chat_id,
            'text': '😕 Hozirda aktiv konkurs yo\'q.\n\nKanalimizni kuzating: @Kraken_mobile'
        })
        return

    user_states[chat_id] = {
        'step': 'name',
        'konkurs_id': konkurs['id'],
        'prize': konkurs.get('prize', '')
    }

    req.post(f'{TG_API}/sendMessage', json={
        'chat_id': chat_id,
        'text': (
            f"🎁 *{konkurs.get('prize', 'Sovrin')}* konkursida qatnashish uchun:\n\n"
            f"📝 Ismingizni yozing:"
        ),
        'parse_mode': 'Markdown',
        'reply_markup': {'remove_keyboard': True}
    })

async def handle_name_step(chat_id, name, user):
    state = user_states.get(chat_id, {})
    state['name'] = name
    state['step'] = 'phone'
    user_states[chat_id] = state

    req.post(f'{TG_API}/sendMessage', json={
        'chat_id': chat_id,
        'text': f"👋 Salom, *{name}*!\n\n📱 Telefon raqamingizni ulashing:",
        'parse_mode': 'Markdown',
        'reply_markup': {
            'keyboard': [[{
                'text': '📱 Raqamni ulashish',
                'request_contact': True
            }]],
            'resize_keyboard': True,
            'one_time_keyboard': True
        }
    })

async def handle_phone_step(chat_id, phone, user):
    state = user_states.get(chat_id, {})
    konkurs_id = state.get('konkurs_id', '')
    name = state.get('name', '')
    username = user.get('username', '')
    user_id = user.get('id', chat_id)

    # Sheetga yozish
    save_participant(
        konkurs_id=konkurs_id,
        user_id=user_id,
        username=username,
        full_name=name,
        phone=phone
    )

    # State tozalash
    if chat_id in user_states:
        del user_states[chat_id]

    req.post(f'{TG_API}/sendMessage', json={
        'chat_id': chat_id,
        'text': (
            f"🎉 *Tabriklaymiz!*\n\n"
            f"Siz konkursda muvaffaqiyatli ro'yxatdan o'tdingiz!\n\n"
            f"👤 Ism: {name}\n"
            f"📱 Telefon: {phone}\n\n"
            f"🍀 G'olib e'lon qilinganda kanalimizda xabar beramiz!\n"
            f"📢 @Kraken_mobile"
        ),
        'parse_mode': 'Markdown',
        'reply_markup': {
            'inline_keyboard': [[{
                'text': '🛍 Saytga qaytish',
                'web_app': {'url': SAYT_URL}
            }]]
        }
    })

# === WEBHOOK ===
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

        # /start
        if text.startswith('/start'):
            parts = text.split(' ')
            deep_link = parts[1] if len(parts) > 1 else ''
            await handle_start(chat_id, deep_link)
            return web.json_response({'ok': True})

        # /konkurs
        if text == '/konkurs':
            await handle_konkurs_join(chat_id)
            return web.json_response({'ok': True})

        # Telefon raqami (contact)
        if contact:
            phone = contact.get('phone_number', '')
            state = user_states.get(chat_id, {})
            if state.get('step') == 'phone':
                await handle_phone_step(chat_id, phone, user)
            return web.json_response({'ok': True})

        # State bo'yicha javob
        state = user_states.get(chat_id)
        if state:
            if state.get('step') == 'name' and text:
                await handle_name_step(chat_id, text, user)
            elif state.get('step') == 'phone' and text:
                # Qo'lda yozilgan raqam
                await handle_phone_step(chat_id, text, user)

        return web.json_response({'ok': True})
    except Exception as e:
        logger.error(f'Webhook error: {e}')
        return web.json_response({'ok': False})

# === RASM YUKLASH (o'zgarishsiz) ===
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
            files={'photo': ('photo.jpg', BytesIO(image_bytes), 'image/jpeg')}
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
        if not file_id:
            return web.json_response({'error': 'No file_id'}, status=400)
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
            logger.info('Keep-alive ping sent')
        except Exception as e:
            logger.warning(f'Keep-alive failed: {e}')

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
    logger.info(f'Server started on port {PORT}')
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
