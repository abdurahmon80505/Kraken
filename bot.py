import os
import json
import logging
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from aiohttp import web
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))
PORT = int(os.environ.get('PORT', 8080))

bot = Bot(token=BOT_TOKEN)

async def upload_image(request):
    """Admin saytdan rasm yuklaydi - Telegram serveriga saqlaydi"""
    try:
        data = await request.json()
        image_b64 = data.get('image', '')
        listing_num = data.get('num', 0)
        
        if not image_b64:
            return web.json_response({'error': 'No image'}, status=400)
        
        # Base64 ni bytes ga o'tkazamiz
        import base64
        if ',' in image_b64:
            image_b64 = image_b64.split(',')[1]
        image_bytes = base64.b64decode(image_b64)
        
        # Telegram ga yuboramiz
        from io import BytesIO
        photo = BytesIO(image_bytes)
        photo.name = f'listing_{listing_num}.jpg'
        
        msg = await bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo,
            caption=f'📸 E\'lon №{listing_num} rasmi'
        )
        
        # file_id ni qaytaramiz
        file_id = msg.photo[-1].file_id
        file_url = f'https://api.telegram.org/file/bot{BOT_TOKEN}/'
        
        # Rasm URL ni olish
        file = await bot.get_file(file_id)
        full_url = f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}'
        
        return web.json_response({
            'success': True,
            'file_id': file_id,
            'url': full_url
        })
        
    except Exception as e:
        logger.error(f'Upload error: {e}')
        return web.json_response({'error': str(e)}, status=500)

async def get_image_url(request):
    """file_id dan URL olish"""
    try:
        file_id = request.query.get('file_id', '')
        if not file_id:
            return web.json_response({'error': 'No file_id'}, status=400)
        
        file = await bot.get_file(file_id)
        url = f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}'
        
        return web.json_response({'url': url})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def health(request):
    return web.json_response({'status': 'ok', 'bot': 'Kraken Mobile Bot'})

async def main():
    app = web.Application()
    app.router.add_post('/upload', upload_image)
    app.router.add_get('/image', get_image_url)
    app.router.add_get('/health', health)
    
    # CORS headers
    @web.middleware
    async def cors_middleware(request, handler):
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_post('/upload', upload_image)
    app.router.add_get('/image', get_image_url)
    app.router.add_get('/health', health)
    app.router.add_route('OPTIONS', '/{path_info:.*}', lambda r: web.Response())
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f'Bot server started on port {PORT}')
    
    # Bot ni ham ishga tushuramiz
    application = Application.builder().token(BOT_TOKEN).build()
    await application.initialize()
    await application.start()
    
    # Davom etamiz
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
