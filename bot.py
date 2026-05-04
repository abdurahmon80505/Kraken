import os
import logging
import asyncio
import base64
from io import BytesIO
from aiohttp import web
import telegram

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))
PORT = int(os.environ.get('PORT', 8080))

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
        bot = telegram.Bot(token=BOT_TOKEN)
        photo = BytesIO(image_bytes)
        photo.name = f'listing_{listing_num}.jpg'
        msg = bot.send_photo(chat_id=ADMIN_ID, photo=photo, caption=f"Elon №{listing_num}")
        file_id = msg.photo[-1].file_id
        file_info = bot.get_file(file_id)
        url = f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}'
        return web.json_response({'success': True, 'file_id': file_id, 'url': url})
    except Exception as e:
        logger.error(f'Upload error: {e}')
        return web.json_response({'error': str(e)}, status=500)

async def get_image_url(request):
    try:
        file_id = request.query.get('file_id', '')
        if not file_id:
            return web.json_response({'error': 'No file_id'}, status=400)
        bot = telegram.Bot(token=BOT_TOKEN)
        file_info = bot.get_file(file_id)
        url = f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}'
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

async def main():
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_post('/upload', upload_image)
    app.router.add_get('/image', get_image_url)
    app.router.add_get('/health', health)
    app.router.add_route('OPTIONS', '/{path_info:.*}', lambda r: web.Response())
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f'Server started on port {PORT}')
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
