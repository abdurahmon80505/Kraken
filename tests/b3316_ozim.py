# -*- coding: utf-8 -*-
"""tests/b3316_ozim.py — 3316: 🏪 «O'zim olib ketaman» — sayt tur='ozim' yuboradi: manzil / filial so'ralmaydi,
admin xabarida «📍 🏪 O'zim olib ketaman»; EMU / BTS da filial hali ham shart.

Ishga tushirish:  python tests/b3316_ozim.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get va bot._kk_sheet almashtirilgan, saqlash — o'chiq.
Buyurtmalar — soxta (uid 777001, №TO…); real mijozga tegilmaydi.
"""
import asyncio
import atexit
import logging
import os
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
_VAQT = tempfile.mkdtemp(prefix='b3316-')
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
SHEET = []
MIJOZ, ADMIN = 777001, bot.ADMIN_ID


def sinov(nom, shart, sabab=''):
    if shart:
        NATIJA[0] += 1
        print(f'  ✓ {nom}')
    else:
        NATIJA[1] += 1
        print(f'  ✗ {nom} — {sabab}')


class Javob:
    status_code = 200
    content = b''

    def json(self):
        return {'ok': True, 'result': {'message_id': 1}}


def _post(url, **kw):
    SOROV.append(kw.get('json') or kw.get('data') or {})
    return Javob()


bot.req.post = _post
bot.req.get = _post
bot.BOT_TOKEN = 'SINOV:TOKEN'
bot.TG_API = 'https://api.telegram.org/botSINOV:TOKEN'
bot._mijoz_saqlash = lambda: None
bot._mijoz_sync_belgila = lambda *a: None
bot._mijoz_sync_yoqilgan = lambda: False
bot.check_init_data = lambda s, max_age=86400: int(s) if str(s).isdigit() else None
bot._init_data_user = lambda s: {'id': MIJOZ, 'username': 'sinov_mijoz'}
bot._kk_init_til = lambda s: 'uz'
bot.fetch_elon_by_num = lambda n: (None, None)
bot.time.sleep = lambda s: None

ELON = {'11': {'num': '11', 'price': '100', 'status': 'active', 'specId': ''}}
bot.elon_cache_get = lambda n: (ELON.get(str(n)), {})
bot.elon_status = lambda e: e.get('status', 'active')
bot._buyurtma_sarlavha = lambda e, m, r=None: 'Tovar ' + e['num']


def _sheet(action, timeout=30, **p):
    SHEET.append((action, p))
    return {'ok': True}


bot._kk_sheet = _sheet


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


class So:
    def __init__(self, d):
        self.d = d

    async def json(self):
        return self.d


def buyurtma(order, **extra):
    bot._BUYURTMA_SONI.clear()
    SOROV.clear()
    SHEET.clear()
    d = {'initData': str(MIJOZ), 'num': '11', 'nums': ['11'], 'order': order, 'name': 'Sinov', 'phone': '+998 90 000 00 01',
         'kurs': 12000, **extra}
    r = asyncio.run(bot.buyurtma_endpoint(So(d)))
    return r.status


def admin_matn():
    return '\n'.join(x['text'] for x in SOROV if str(x.get('chat_id')) == str(ADMIN) and 'text' in x)


print('— 📍 qatori')
sinov("ozim — «🏪 O'zim olib ketaman»", bot._buyurtma_joy_matn({'tur': 'ozim'}) == "🏪 O'zim olib ketaman",
      bot._buyurtma_joy_matn({'tur': 'ozim'}))
sinov("ozim — manzil yuborilsa ham e'tiborsiz", bot._buyurtma_joy_matn({'tur': 'ozim', 'manzil': '<b>x</b>'}) == "🏪 O'zim olib ketaman")
sinov("tartib: yandex, ozim, emu, bts", list(bot._BUYURTMA_TUR) == ['yandex', 'ozim', 'emu', 'bts'], repr(list(bot._BUYURTMA_TUR)))

print('— /buyurtma')
st = buyurtma('TO01', tur='ozim')
sinov("ozim, manzilsiz → 200", st == 200, st)
sinov("admin xabarida «📍 🏪 O'zim olib ketaman»", "📍 🏪 O'zim olib ketaman" in admin_matn(), admin_matn()[:400])
st = buyurtma('TO02', tur='emu')
sinov("EMU, filialsiz → 400 (o'zgarmagan)", st == 400, st)
st = buyurtma('TO03', tur='bts', manzil='Toshkent, Chilonzor filiali')
sinov("BTS, filial bilan → 200, matnda filial", st == 200 and 'BTS: Toshkent, Chilonzor filiali' in admin_matn(), admin_matn()[:400])

print(f'{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
