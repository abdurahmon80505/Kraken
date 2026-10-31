# -*- coding: utf-8 -*-
"""tests/epaqa_tuzatishlar.py — «bot-epaqa»: botni to'liq tekshirishda topilgan chala joylar tuzatishi (har bo'lim — bitta commit).

Ishga tushirish:  python tests/epaqa_tuzatishlar.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get va bot._kk_sheet almashtirilgan, saqlash — vaqtinchalik papkada.
Mijozlar — soxta (uid 777005, №TE…); real mijozga tegilmaydi.
"""
import asyncio
import atexit
import html
import json
import logging
import os
import re
import shutil
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

for k in ('BOT_TOKEN', 'MAIN_CHANNEL_ID', 'WEBHOOK_SECRET', 'POST_CHANNEL_ID', 'POST_KANALLAR', 'TEST_CHANNEL_ID',
          'CHANNEL_ID', 'GURUH_KANAL_ID', 'ESKI_BOT_TOKEN', 'RENDER_URL', 'ADMIN_GURUH', 'SHEET_URL'):
    os.environ.pop(k, None)
_VAQT = tempfile.mkdtemp(prefix='epaqa-')
atexit.register(shutil.rmtree, _VAQT, True)
os.environ['BRON_FAYL'] = os.path.join(_VAQT, 'bron.json')
os.environ['MIJOZ_FAYL'] = os.path.join(_VAQT, 'mijoz.json')

import requests


def _tarmoq_yoq(*a, **kw):
    raise AssertionError(f'tarmoq so\'rovi: {a[:1]}')


requests.post = requests.get = _tarmoq_yoq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot  # noqa: E402

logging.disable(logging.CRITICAL)
NATIJA = [0, 0]
SOROV = []
MIJOZ, ADMIN = 777005, bot.ADMIN_ID
MID = [100]


def sinov(nom, shart, sabab=''):
    if shart:
        NATIJA[0] += 1
        print(f'  ✓ {nom}')
    else:
        NATIJA[1] += 1
        print(f'  ✗ {nom} — {sabab}')


class Javob:
    def __init__(self, kod=200, j=None):
        self.status_code, self._j = kod, j or {}
        self.text = json.dumps(self._j)

    def json(self):
        return self._j


def _post(url, **kw):
    """Telegram o'rnida: yangi xabarga id beradi, tahrirda yuborilgan matnni qaytaradi (Telegram kabi)."""
    usul = url.rsplit('/', 1)[-1]
    d = kw.get('json') or kw.get('data') or {}
    SOROV.append((usul, d))
    if usul in ('sendMessage', 'copyMessage', 'sendPhoto'):
        MID[0] += 1
        r = {'message_id': MID[0]}
        if usul == 'sendMessage':
            r.update(text=html.unescape(re.sub(r'<[^>]+>', '', d.get('text', ''))), entities=[])
        return Javob(200, {'ok': True, 'result': r})
    if usul == 'editMessageText':
        return Javob(200, {'ok': True, 'result': {'message_id': d['message_id'], 'text': d['text'], 'entities': d.get('entities')}})
    if usul == 'editMessageCaption':
        return Javob(200, {'ok': True, 'result': {'message_id': d['message_id'], 'caption': d['caption'],
                                                  'caption_entities': d.get('caption_entities')}})
    return Javob(200, {'ok': True, 'result': True})


bot.req.post = _post
bot.req.get = _post
bot.BOT_TOKEN = 'SINOV:TOKEN'
bot.TG_API = 'https://api.telegram.org/botSINOV:TOKEN'
bot._mijoz_saqlash = lambda: None
bot._mijoz_sync_belgila = lambda *a: None
bot._mijoz_sync_yoqilgan = lambda: False
bot._sotuv_sheet_yoz = lambda uid, b: True
bot._kk_sheet = lambda action, timeout=30, **p: {'ok': True}
bot.time.sleep = lambda s: None


def _fonsiz(self, ex, f, *a):
    fut = self.create_future()
    try:
        fut.set_result(f(*a))
    except Exception as e:
        fut.set_exception(e)
    return fut


asyncio.SelectorEventLoop.run_in_executor = _fonsiz
if hasattr(asyncio, 'ProactorEventLoop'):
    asyncio.ProactorEventLoop.run_in_executor = _fonsiz


class Sorov:
    def __init__(self, d):
        self._d = d

    async def json(self):
        return self._d


def sorov(usul):
    return [d for u, d in SOROV if u == usul]


# ── A. Ishga tushish: setWebhook yiqilmaydi / osilib qolmaydi ──────────────────────────────────────────────────────────
print('— A. _webhook_ornat: Telegram javob bermasa ham bot ishlayveradi')
WH = []


def _wh_post(url, **kw):
    WH.append((url.rsplit('/', 2)[-2][3:], url.rsplit('/', 1)[-1], kw))
    raise requests.ConnectionError('tarmoq uzildi')


bot.req.post = _wh_post
bot.ESKI_BOT_TOKEN = 'ESKI:TOKEN'
try:
    bot._webhook_ornat('https://sinov.onrender.com')
    yiqilmadi = True
except Exception as e:
    yiqilmadi = repr(e)
bot.req.post = _post
sinov('tarmoq xatosi — istisno tashqariga chiqmadi', yiqilmadi is True, yiqilmadi)
sinov('yangi bot: /webhook, timeout bor', WH and WH[0][0] == 'SINOV:TOKEN' and WH[0][2]['json']['url'].endswith('/webhook')
      and WH[0][2].get('timeout'), repr(WH)[:300])
sinov("yangi bot xatosi eski botni to'xtatmadi: eski bot ham urinildi (/webhook-eski)",
      len(WH) == 2 and WH[1][0] == 'ESKI:TOKEN' and WH[1][2]['json']['url'].endswith('/webhook-eski'), repr(WH)[:300])
sinov("ikki bot aralashmadi: eski botga faqat message + callback_query",
      len(WH) == 2 and WH[1][2]['json']['allowed_updates'] == ['message', 'callback_query']
      and 'chat_member' in WH[0][2]['json']['allowed_updates'], repr(WH)[:300])
bot.ESKI_BOT_TOKEN = ''
SOROV.clear()
bot._webhook_ornat('https://sinov.onrender.com')
sinov('oddiy holat: bitta setWebhook (eski token yo\'q)', [u for u, _ in SOROV] == ['setWebhook'], repr(SOROV)[:200])


print(f'\n{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
