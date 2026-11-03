# -*- coding: utf-8 -*-
"""tests/b32621_sharh_matn.py — 3262.1: matnli sharh hozircha o'chiq (SHARH_MATN = False). Mijoz yulduz bosadi → «Rahmat! ★★★★☆»,
matnga taklif ham «Yozmayman» tugmasi ham yo'q; baho adminga darhol; keyin yozgani sharh emas; sayt /buyurtma_sharh matnni olmaydi.
SHARH_MATN = True — eski oqim (matn so'raladi) qaytadi.

Ishga tushirish:  python tests/b32621_sharh_matn.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get almashtirilgan, saqlash — o'chiq. Mijoz — soxta (uid 777003, №TS…).
"""
import asyncio
import atexit
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
_VAQT = tempfile.mkdtemp(prefix='b32621-')
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
MIJOZ, ADMIN = 777003, bot.ADMIN_ID


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

    def json(self):
        return self._j


def _post(url, **kw):
    usul = url.rsplit('/', 1)[-1]
    d = kw.get('json') or kw.get('data') or {}
    SOROV.append((usul, d))
    return Javob(200, {'ok': True, 'result': {'message_id': 900}})


bot.req.post = _post
bot.req.get = _post
bot.BOT_TOKEN = 'SINOV:TOKEN'
bot.TG_API = 'https://api.telegram.org/botSINOV:TOKEN'
bot._mijoz_saqlash = lambda: None
bot._mijoz_sync_belgila = lambda *a: None
bot._mijoz_sync_yoqilgan = lambda: False
bot._sharh_tovar = lambda b: {'num': '101', 'spec': 'p9', 'model': 'Pixel 9'}
bot.check_init_data = lambda s, max_age=86400: {'mijoz': MIJOZ}.get(s)
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


def yangi(order, til='uz'):
    b = {'order': order, 'ts': 1, 'holat': 'yetkazildi', 'holat_ts': bot.SHARH_BOSHI + 10, 'til': til, 'ism': 'Sinov Mijoz',
         'tovar': [{'num': '101', 'narx': 100}]}
    with bot._MIJOZ_LOCK:
        bot._mijoz_ochiq(MIJOZ)['buyurtma'].insert(0, b)


def sharh(order):
    b = next((b for b in bot._mijoz_ol(MIJOZ)['buyurtma'] if b.get('order') == order), {})
    return (b.get('yetkaz') or {}).get('sharh') or {}


def sorov(usul):
    return [d for u, d in SOROV if u == usul]


TAKLIF = re.compile(r'yozing|напишите|Yozmayman|Пропустить|fikr|отзыв', re.I)

print("— odatiy sozlama")
sinov('SHARH_MATN = False', bot.SHARH_MATN is False, repr(bot.SHARH_MATN))
sinov("3 kunlik so'rov — faqat 1–5 ⭐, matnga taklif yo'q",
      not TAKLIF.search(bot._sharh_sor_matn({'til': 'uz', 'order': 'X'}, 'Pixel 9') + bot._sharh_sor_matn({'til': 'ru', 'order': 'X'}, 'Pixel 9')))

for til in ('uz', 'ru'):
    print(f'— yulduz bosildi ({til})')
    o = 'TS0' + ('1' if til == 'uz' else '2')
    yangi(o, til)
    SOROV.clear()
    bot._sharh_tugma_ish(MIJOZ, MIJOZ, 55, f'bb:4:{o}')
    t = sorov('editMessageText')
    sinov('xabar o\'sha joyida — «★★★★☆»', len(t) == 1 and '★★★★☆' in t[0]['text'], t)
    sinov("matnga taklif ham, tugma ham yo'q", t and not TAKLIF.search(t[0]['text']) and 'reply_markup' not in t[0], t)
    adm = [d for d in sorov('sendMessage') if str(d.get('chat_id')) == str(ADMIN)]
    sinov('adminga darhol bitta xabar', len(adm) == 1, sorov('sendMessage'))
    s = sharh(o)
    sinov("sharh: baho 4, matn bo'sh, kutish yo'q", s.get('baho') == 4 and s.get('matn') == '' and s.get('hol') != 'yoz', s)
    sinov("mijozdan matn kutilmaydi", bot._sharh_kutyapti(MIJOZ) == '')
    SOROV.clear()
    sinov('sikl qayta yubormaydi', bot._sharh_ish(s.get('ts', 0) + 3 * 3600) == (0, 0) and not sorov('sendMessage'))

print("— sayt /buyurtma_sharh: matn olinmaydi")
yangi('TS03')
SOROV.clear()
r = asyncio.run(bot.buyurtma_sharh_endpoint(Sorov({'initData': 'mijoz', 'order': 'TS03', 'baho': 5, 'matn': 'Tez yetkazildi'})))
s = sharh('TS03')
sinov('200, baho 5', r.status == 200 and s.get('baho') == 5, (r.status, s))
sinov("matn yozilmadi", s.get('matn') == '', s)
sinov('admin xabarida matn yo\'q', not any('Tez yetkazildi' in d.get('text', '') for d in sorov('sendMessage')))

print("— SHARH_MATN = True: eski oqim qaytadi")
bot.SHARH_MATN = True
yangi('TS04')
SOROV.clear()
bot._sharh_tugma_ish(MIJOZ, MIJOZ, 56, 'bb:5:TS04')
t = sorov('editMessageText')
sinov('matn so\'raladi + «Yozmayman» tugmasi', t and TAKLIF.search(t[0]['text']) and 'reply_markup' in t[0], t)
sinov('matn kutiladi', bot._sharh_kutyapti(MIJOZ) == 'TS04')
bot.SHARH_MATN = False

print(f'\n{NATIJA[0]} to\'g\'ri, {NATIJA[1]} xato')
sys.exit(1 if NATIJA[1] else 0)
