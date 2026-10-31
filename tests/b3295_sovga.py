# -*- coding: utf-8 -*-
"""tests/b3295_sovga.py — 3295: kelishilgan narx 0 — 🎁 sovg'a. Hammasi sovg'a: to'lov so'ralmaydi, buyurtma darhol «to'landi»,
Store'ga $0 sotuv; aralash savat: faqat pullik qism uchun to'lov. Qarorni faqat server hisobi beradi (mijoz yuborgan jami emas).

Ishga tushirish:  python tests/b3295_sovga.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get va bot._kk_sheet almashtirilgan, saqlash — o'chiq.
Buyurtmalar — soxta (uid 777001, №TS…); real mijozga tegilmaydi.
"""
import asyncio
import atexit
import json
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
_VAQT = tempfile.mkdtemp(prefix='b3295-')
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
SOTUV_OK = [True]
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

ELON = {'11': {'num': '11', 'price': '100', 'status': 'active', 'specId': ''},
        '12': {'num': '12', 'price': '50', 'status': 'active', 'specId': ''},
        '13': {'num': '13', 'price': '100', 'status': 'sold', 'specId': ''},
        '14': {'num': '14', 'price': '10', 'status': 'active', 'specId': '', 'soni': 5},
        '15': {'num': '15', 'price': '0', 'status': 'active', 'specId': ''}}
bot.elon_cache_get = lambda n: (ELON.get(str(n)), {})
bot.elon_status = lambda e: e.get('status', 'active')
bot._buyurtma_sarlavha = lambda e, m, r=None: 'Tovar ' + e['num']


def _havola(narxlar, qatorlar=()):
    return {'ok': True, 'narxlar': {k: {'narx': v, 'asl': 100} for k, v in narxlar.items()}, 'qatorlar': list(qatorlar)}


HAVOLA = {'sovgakod1': _havola({'11': 0}), 'hammakod1': _havola({'11': 0, '12': 0}), 'yopiqkod1': _havola({'13': 0}),
          'donakod01': _havola({'14': 0}, [{'num': '14', 'rang': '', 'soni': 1}]), 'buzuqkod1': _havola({'15': 0}),
          'manfiykod': _havola({'11': -5}), 'ikkirang1': _havola({'14': 0}, [{'num': '14', 'rang': 'Oq', 'soni': 1},
                                                                             {'num': '14', 'rang': 'Qora', 'soni': 2}])}


def _sheet(action, timeout=30, **p):
    SHEET.append((action, p))
    if action == 'savatOl':
        return HAVOLA.get(p.get('kod'), {'ok': False, 'msg': 'yoq'})
    if action == 'sotuvYoz':
        return {'ok': SOTUV_OK[0]}
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


def buyurtma(order, nums, savat=None, **extra):
    bot._BUYURTMA_SONI.clear()
    SOROV.clear()
    SHEET.clear()
    d = {'initData': str(MIJOZ), 'num': nums[0], 'nums': list(nums), 'order': order, 'name': 'Sinov', 'phone': '+998 90 000 00 01',
         'tur': 'emu', 'manzil': 'Sinov shahri', 'kurs': 12000, **extra}
    if savat:
        d['savat'] = savat
    r = asyncio.run(bot.buyurtma_endpoint(So(d)))
    return r.status


def yozuv(order):
    return next((b for b in bot._mijoz_ol(MIJOZ)['buyurtma'] if b.get('order') == order), None)


def xabarlar(chat):
    return [x for x in SOROV if str(x.get('chat_id')) == str(chat) and 'text' in x]


def sotuvlar():
    return [json.loads(p['data']) for a, p in SHEET if a == 'sotuvYoz']


def tugmalar(x):
    return json.dumps(x.get('reply_markup') or {}, ensure_ascii=False)


print('— narx')
sinov('0 — kelishilgan narx (0, 100)', bot._kel_narx({'num': '11', 'price': '100'}, {'11': 0}) == (0, 100.0))
sinov("Store narxidan katta / teng — Store", bot._kel_narx({'num': '11', 'price': '100'}, {'11': 120}) == (100.0, 0)
      and bot._kel_narx({'num': '11', 'price': '100'}, {'11': 100}) == (100.0, 0))
k, o = bot._savat_kel_narxlar(['sovgakod1'])
sinov('savatOl: 0 olinadi', k == {'11': 0} and o is False, repr(k))
k, o = bot._savat_kel_narxlar(['manfiykod'])
sinov('savatOl: manfiy — olinmaydi', k == {}, repr(k))
k, o = bot._savat_kel_narxlar(['ikkirang1'])
sinov("havola donasi — ranglar yig'indisi", k.get('_soni') == {'14': 3}, repr(k))

print("— hammasi sovg'a")
st = buyurtma('TS01', ['11'], ['sovgakod1'])
b = yozuv('TS01')
sinov("buyurtma → «to'landi», jami 0, belgi", st == 200 and b['holat'] == 'tolandi' and b['jami'] == 0 and b.get('sovga') and b.get('holat_ts'),
      repr(b)[:300])
adm = xabarlar(ADMIN)[0]
sinov("admin xabarida 🎁 Sovg'a, ✅ To'landi; ⏳ yo'q", "🎁 <b>Sovg'a — yangi buyurtma</b>" in adm['text'] and "✅ <b>To'landi</b>" in adm['text']
      and "To'lov kutilmoqda" not in adm['text'] and "Sovg'a — 0$" in adm['text'], adm['text'])
sinov("admin tugmasi: keyingisi 🚚 (3301: bajarilgani — matnda)", 'bh:yolda' in tugmalar(adm) and 'bh:tolandi' not in tugmalar(adm),
      tugmalar(adm))
mj = xabarlar(MIJOZ)
sinov("mijozga bitta xabar: sovg'a, to'lov tugmasi yo'q", len(mj) == 1 and "to'lov kerak emas" in mj[0]['text'] and not mj[0].get('reply_markup'), repr(mj))
sinov("Store'ga bitta $0 sotuv: narx 0, chegirma 100", [(s['order'], s['tovar'][0]['narx'], s['tovar'][0]['chegirma']) for s in sotuvlar()] == [('TS01', 0, 100.0)],
      repr(sotuvlar()))
sinov("holat qatori keyingi bosqichga ulanadi", (bot._buyurtma_holat_matn(bot._html.unescape(bot.re.sub(r'<[^>]+>', '', adm['text'])), [], 'yolda', 0) or [''])[0]
      .count("✅ To'landi") == 1, adm['text'])
st = buyurtma('TS01', ['11'], ['sovgakod1'])
sinov("takror yuborish — ikkinchi sotuv / xabar yo'q", st == 200 and not sotuvlar() and not xabarlar(MIJOZ), repr(SOROV))
st = buyurtma('TS02', ['11', '12'], ['hammakod1'])
b = yozuv('TS02')
sinov("savatda hammasi sovg'a — to'landi, jami 0", b['holat'] == 'tolandi' and b['jami'] == 0 and len(sotuvlar()) == 1, repr(b)[:300])

print('— aralash savat')
st = buyurtma('TS03', ['11', '12'], ['sovgakod1'])
b = yozuv('TS03')
sinov('kutilmoqda, jami — pullik qism, belgi yo\'q', b['holat'] == 'kutilmoqda' and b['jami'] == 50 and not b.get('sovga'), repr(b)[:300])
m = xabarlar(ADMIN)[0]['text']
sinov("adminga: oddiy sarlavha, 🎁 qator, Jami 50$, ⏳", 'Yangi buyurtma' in m and "🎁 Sovg'a (Store 100$)" in m and 'Jami 50$' in m and "To'lov kutilmoqda" in m, m)
mj = xabarlar(MIJOZ)[0]
sinov("mijozga: to'lov 50$ uchun, sovg'a qatori 🎁", 's=600000' in tugmalar(mj) and 'chk:TS03' in tugmalar(mj) and ' · 🎁' in mj['text'], repr(mj))
sinov("sotuv yozilmadi (to'lov hali yo'q)", not sotuvlar())

print('— mijoz sovg\'a qila olmaydi')
st = buyurtma('TS04', ['11'], usd=0, jami=0, price=0, narxlar={'11': 0})
b = yozuv('TS04')
sinov("kodsiz, jami / narx yuborsa ham — Store narxi", b['jami'] == 100 and b['holat'] == 'kutilmoqda' and not b.get('sovga'), repr(b)[:300])
st = buyurtma('TS05', ['11'], ['soxtakod1'])
b = yozuv('TS05')
sinov('havola o\'qilmadi — Store narxi, ogoh', b['jami'] == 100 and b['holat'] == 'kutilmoqda' and "havola o'qilmadi" in xabarlar(ADMIN)[0]['text'], repr(b)[:300])
st = buyurtma('TS06', ['15'], ['buzuqkod1'])
b = yozuv('TS06')
sinov("Store narxi o'zi 0 (buzuq e'lon) — sovg'a emas", b['holat'] == 'kutilmoqda' and not b.get('sovga'), repr(b)[:300])
bot._buyurtma_zaxira_birlash({'buyurtma': [{'user_id': MIJOZ, 'order': 'TS07', 'ts': 1, 'jami': 0, 'tur': 'emu', 'ism': 'S', 'tel': '+998900000001',
                                            'tovar': [{'num': '11', 'nom': 'T', 'narx': 0, 'soni': 1}], 'joy': {'manzil': 'x'}}]})
SOROV.clear(); SHEET.clear()
bot._buyurtma_xabar_ish()
b = yozuv('TS07')
sinov("sayt zaxirasi jami 0, havolasiz — to'lanmaydi, adminga Store narxi", b['holat'] == 'kutilmoqda' and not b.get('sovga') and not sotuvlar()
      and "To'lov kutilmoqda" in xabarlar(ADMIN)[0]['text'] and '100$' in xabarlar(ADMIN)[0]['text'], repr(b)[:300])

print('— sayt zaxirasidan sovg\'a')
bot._buyurtma_zaxira_birlash({'buyurtma': [{'user_id': MIJOZ, 'order': 'TS08', 'ts': 1, 'jami': 0, 'tur': 'emu', 'ism': 'S', 'tel': '+998900000001',
                                            'tovar': [{'num': '11', 'nom': 'T', 'narx': 0, 'soni': 1}], 'joy': {'manzil': 'x', 'savat': ['sovgakod1']}}]})
SOROV.clear(); SHEET.clear()
bot._buyurtma_xabar_ish()
b = yozuv('TS08')
sinov("fon sikli: to'landi, tugma 🚚, mijozga xabar, $0 sotuv", b['holat'] == 'tolandi' and 'bh:yolda' in tugmalar(xabarlar(ADMIN)[0])
      and "to'lov kerak emas" in xabarlar(MIJOZ)[0]['text'] and len(sotuvlar()) == 1 and sotuvlar()[0]['tovar'][0]['chegirma'] == 100.0, repr(b)[:300])

print("— admin tasdig'i shart")
st = buyurtma('TS09', ['13'], ['yopiqkod1'])
b = yozuv('TS09')
m = xabarlar(ADMIN)[0]
sinov("e'lon yopiq — kutilmoqda, adminga «tekshiring», sotuv yo'q", b['holat'] == 'kutilmoqda' and b.get('sovga') and 'tekshiring' in m['text'] and 'bh:tolandi' in tugmalar(m)
      and not sotuvlar(), m['text'])
sinov("mijozga baribir to'lov so'ralmaydi", "to'lov kerak emas" in xabarlar(MIJOZ)[0]['text'] and not xabarlar(MIJOZ)[0].get('reply_markup'), repr(xabarlar(MIJOZ)))
SHEET.clear()
asyncio.run(bot.buyurtma_holat_tugma(str(ADMIN), 5, f'bh:tolandi:{MIJOZ}:TS09'))
sinov("admin «To'lov keldi» — $0 sotuv yoziladi", yozuv('TS09')['holat'] == 'tolandi' and len(sotuvlar()) == 1, repr(SHEET))
st = buyurtma('TS10', ['14'], ['donakod01'], sonlar={'14': 3})
b = yozuv('TS10')
sinov("3301: mijoz havoladagidan ko'p dona so'radi — havoladagicha yoziladi, adminga ⚠️", b['tovar'][0]['soni'] == 1 and b['holat'] == 'tolandi' and len(sotuvlar()) == 1
      and 'havoladagicha yozildi' in xabarlar(ADMIN)[0]['text'], repr(b)[:300])
st = buyurtma('TS11', ['14'], ['donakod01'], sonlar={'14': 1})
sinov("havoladagi dona — o'zi to'lanadi", yozuv('TS11')['holat'] == 'tolandi' and len(sotuvlar()) == 1, repr(yozuv('TS11'))[:300])

print('— Store javob bermasa')
SOTUV_OK[0] = False
st = buyurtma('TS12', ['11'], ['sovgakod1'])
sinov("holat saqlanadi, admin ogohlantiriladi", yozuv('TS12')['holat'] == 'tolandi' and any('sotuv yozuvi tushmadi' in x['text'] for x in xabarlar(ADMIN)), repr(xabarlar(ADMIN)))
SOTUV_OK[0] = True
SHEET.clear()
asyncio.run(bot.buyurtma_holat_tugma(str(ADMIN), 5, f'bh:yolda:{MIJOZ}:TS12'))
sinov("«🚚 Yo'lda» bosilganda qayta yoziladi", len(sotuvlar()) == 1, repr(SHEET))

print(f'{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
