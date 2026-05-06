import os
import logging
import asyncio
from aiohttp import web
import requests as req

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', 8080))
TG_API = f'https://api.telegram.org/bot{BOT_TOKEN}'
SAYT_URL = 'https://krakenmobileshop.netlify.app'
RENDER_URL = 'https://kraken-taki.onrender.com'

async def handle_start(chat_id):
    keyboard = {
        "inline_keyboard": [[{
            "text": "🛍 Do'konimizga tashrif buyuring",
            "web_app": {"url": SAYT_URL}
        }]]
    }
    req.post(f'{TG_API}/sendMessage', json={
        'chat_id': chat_id,
        'text': '👋 Assalomu alaykum! Xush kelibsiz!\n\nQuyidagi tugma orqali do\'konimizga kiring 👇',
        'reply_markup': keyboard
    })

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

async def health(request):
    return web.json_response({'status': 'ok'})

async def main():
    app = web.Application()
    app.router.add_post('/webhook', webhook)
    app.router.add_get('/health', health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    r = req.post(f'{TG_API}/setWebhook', json={'url': f'{RENDER_URL}/webhook'})
    logger.info(f'Webhook set: {r.json()}')

    logger.info(f'Server ishlamoqda port: {PORT}')
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
