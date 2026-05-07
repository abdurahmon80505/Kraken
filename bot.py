import os
import logging
import asyncio
import base64
from io import BytesIO
from aiohttp import web
import requests as req

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', 8080))
TG_API = f'https://api.telegram.org/bot{BOT_TOKEN}'
CHANNEL = '@kraken_mobile_shop'
SAYT_URL = 'https://krakenmobileshop.netlify.app/'  # ← O'zingiznikini yozing

# === /start komandasi ===
async def handle_start(chat_id):
    gif_file_id = 'CgACAgIAAxkBAAMhafvyjF0CZyhUTDgohAirQYATyi0AAn6kAALY09lLnY0h9qSQRV47BA'
    text = (
        "*Sotuvdagi barcha smartfonlarimizni ushbu saytimizga joylashtirdik*\n"
        "\n"
        "Bu yerdan o'zingizga kerakli Pixel smartfonini topishingiz mumkin — "
        "qulay interfeys, aktual e'lonlar va narxlar\n"
        "\n"
        "Kirish uchun bosing 👇"
    )
    keyboard = {
        "inline_keyboard": [
            [{
                "text": "🛍 Saytga kirish",
                "web_app": {"url": SAYT_URL}
            }]
        ]
    }
    req.post(f'{TG_API}/sendAnimation', json={
        'chat_id': chat_id,
        'animation': gif_file_id,
        'caption': text,
        'parse_mode': 'Markdown',
        'reply_markup': keyboard
    })

# === Telegram dan xabarlar keladi (webhook) ===
async def webhook(request):
    try:
        data = await request.json()
        message = data.get('message', {})
        text = message.get('text', '')
        chat_id = message.get('chat', {}).get('id')
        
        if text == '/start' and chat_id:
            await handle_start(chat_id)
        
        return web.json_response({'ok': True})
    except Exception as e:
        logger.error(f'Webhook error: {e}')
        return web.json_response({'ok': False})

# === Rasm yuklash (eski kod) ===
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

async def keep_alive():
    """Render free plan uxlab qolmasligi uchun har 10 daqiqada o'ziga ping"""
    render_url = os.environ.get('RENDER_URL', '')
    if not render_url:
        return
    while True:
        await asyncio.sleep(600)  # 10 daqiqa
        try:
            req.get(f'{render_url}/health', timeout=10)
            logger.info('Keep-alive ping sent')
        except Exception as e:
            logger.warning(f'Keep-alive failed: {e}')

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

    # Keep-alive task ni ishga tushiramiz
    asyncio.create_task(keep_alive())

    logger.info(f'Server started on port {PORT}')
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())