# -*- coding: utf-8 -*-
"""tests/b3312_yetkazish.py — 3312: 3306 tahrir oynasida «🚚 Yetkazish puli» (summa, $) va «📦 Allaqachon jo'natilgan» belgisi.
Jami = tovarlar + yetkazish; admin xabarida qator; Store'ga yetkazish / jonatildi; mijoz to'lov havolasida y / j; belgili buyurtmada
«✅ To'lov keldi» → to'g'ri «Yo'lda» («Yo'lda» isboti qayta so'ralmaydi); tahrirdan mijozga xabar YO'Q.

Ishga tushirish:  python tests/b3312_yetkazish.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get, bot._kk_sheet va bot._buyurtma_elon almashtirilgan, saqlash — o'chiq.
Buyurtmalar — soxta (uid 777003, №TT…); real mijozga tegilmaydi.
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
_VAQT = tempfile.mkdtemp(prefix='b3312-')
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
MIJOZ, ADMIN = 777003, bot.ADMIN_ID
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

    def json(self):
        return self._j


def _post(url, **kw):
    """Telegram o'rnida: yangi xabarga id beradi, tahrirda yuborilgan matnni qaytaradi (Telegram kabi)."""
    usul = url.rsplit('/', 1)[-1]
    d = kw.get('json') or kw.get('data') or {}
    SOROV.append((usul, d))
    if usul in ('sendMessage', 'copyMessage'):
        MID[0] += 1
        r = {'message_id': MID[0]}
        if usul == 'sendMessage':
            r.update(text=html.unescape(re.sub(r'<[^>]+>', '', d.get('text', ''))), entities=[])
        return Javob(200, {'ok': True, 'result': r})
    if usul == 'editMessageText':
        return Javob(200, {'ok': True, 'result': {'message_id': d['message_id'], 'text': d['text'], 'entities': d['entities']}})
    if usul == 'editMessageCaption':
        return Javob(200, {'ok': True, 'result': {'message_id': d['message_id'], 'caption': d['caption'],
                                                  'caption_entities': d['caption_entities']}})
    return Javob(200, {'ok': True, 'result': True})


STORE_OK = [True]


def _sheet(action, timeout=30, **p):
    SHEET.append((action, p))
    return {'ok': True} if STORE_OK[0] else None


ELONLAR = {'55': {'num': '55', '_narx': 120}, '56': {'num': '56', '_narx': None}}


def _elon(n):
    e = ELONLAR.get(str(n))
    return (dict(e), {}, '') if e else ({'num': str(n)}, {}, 'topilmadi')


bot.req.post = _post
bot.req.get = _post
bot.BOT_TOKEN = 'SINOV:TOKEN'
bot.TG_API = 'https://api.telegram.org/botSINOV:TOKEN'
bot._mijoz_saqlash = lambda: None
bot._mijoz_sync_belgila = lambda *a: None
bot._mijoz_sync_yoqilgan = lambda: False
bot._sotuv_sheet_yoz = lambda uid, b: True
bot._kk_sheet = _sheet
bot._buyurtma_elon = _elon
bot._narx_son = lambda e: e.get('_narx')
bot._buyurtma_sarlavha = lambda e, m, r=None: f"Tovar {e['num']}"
bot.check_init_data = lambda s, max_age=86400: {'admin': ADMIN, 'mijoz': MIJOZ}.get(s)
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


def tahrir(order, tovar, init='admin', **qosh):
    """Sayt «Saqlash» bosdi → (status, javob). qosh — yetkazish / jonatildi (kelmasa — so'rovda yo'q)."""
    SOROV.clear()
    SHEET.clear()
    d = {'initData': init, 'uid': str(MIJOZ), 'order': order, 'tovar': tovar}
    d.update(qosh)
    r = asyncio.run(bot.admin_buyurtma_tahrir_endpoint(Sorov(d)))
    return r.status, json.loads(r.body)


ESKI = [{'num': '21', 'nom': 'Tovar 21', 'narx': 500, 'soni': 1}, {'num': '22', 'nom': 'Tovar 22', 'narx': 30, 'soni': 2, 'chegirma': 5}]
BUYURTMA_HTML = ("🛒 <b>Yangi buyurtma</b> №{o}\n\n📱 <b>Tovar 21</b> · e'lon №21\n📱 <b>Tovar 22</b> × 2\n💵 560$\n\n"
                 "👤 S\n📞 +998900000001\n📍 Emu\n\n✅ <b>To'landi</b> · 08:00\n🕒 Buyurtma: 31.10.2026 07:50")


def yangi(order, holat='tolandi', xb=True):
    b = {'order': order, 'ts': 1, 'holat': holat, 'tovar': [dict(x) for x in ESKI], 'jami': 560, 'tur': 'emu', 'ism': 'S',
         'tel': '+998900000001', 'til': 'uz', 'joy': {'kurs': 12000}}
    if xb:
        t, e = bot._html_b_ents(BUYURTMA_HTML.format(o=order))
        ct, ce = bot._html_b_ents(bot._chek_admin_matn(b))
        b['admin_xb'] = [{'m': 501, 'c': 0, 't': t, 'e': e}, {'m': 502, 'c': 1, 't': ct, 'e': ce}]
    with bot._MIJOZ_LOCK:
        bot._mijoz_ochiq(MIJOZ)['buyurtma'].insert(0, b)
    for x in ESKI:
        bot._bron_qoy(x['num'], MIJOZ, order)


def yozuv(order):
    return next((b for b in bot._mijoz_ol(MIJOZ)['buyurtma'] if b.get('order') == order), None)


def sorov(usul):
    return [d for u, d in SOROV if u == usul]


def u16(t, o, ln):
    return t.encode('utf-16-le')[o * 2:(o + ln) * 2].decode('utf-16-le')


def bold(t, ents):
    return [u16(t, x['offset'], x['length']) for x in ents if x['type'] == 'bold']


ESKI_T = [{'num': '21', 'soni': 1, 'narx': 500}, {'num': '22', 'soni': 2, 'narx': 30}]   # o'sha tarkib — faqat yetkazish o'zgaradi

print('— kirish: _tahrir_yetkazish')
ky = bot._tahrir_yetkazish
sinov("kelmagan maydon — yozuvdagi qiymat", ky({}, {'yetkazish': 7, 'jonatildi': True}) == (7, True) and ky({}, {}) == (0, False))
sinov("'12.345' → 12.35, jonatildi 1 → True", ky({'yetkazish': '12.345', 'jonatildi': 1}, {}) == (12.35, True))
sinov("0 → yo'q, jonatildi false", ky({'yetkazish': 0, 'jonatildi': False}, {'yetkazish': 9, 'jonatildi': True}) == (0, False))
sinov("manfiy / matn / juda katta — rad", ky({'yetkazish': -1}, {}) is None and ky({'yetkazish': 'x'}, {}) is None
      and ky({'yetkazish': 10001}, {}) is None)

print("— «🚚 Yetkazish puli» 15$ + «📦 jo'natilgan» qo'shildi (tarkib o'sha)")
yangi('TY01', holat='kutilmoqda')
st, j = tahrir('TY01', ESKI_T, yetkazish=15, jonatildi=True)
b = yozuv('TY01')
sinov('200, ok, store, xabar=tahrir', st == 200 and j.get('ok') and j.get('store') is True and j.get('xabar') == 'tahrir', repr(j)[:300])
sinov('jami = 500 + 30×2 + 15 = 575', b['jami'] == 575, repr(b['jami']))
sinov("yozuvda yetkazish 15, jonatildi True", b.get('yetkazish') == 15 and b.get('jonatildi') is True, repr(b)[:300])
sinov("tovar — o'zgarmadi (qoldiq / e'lon tegilmadi)", [(x['num'], x['soni'], x['narx']) for x in b['tovar']] == [('21', 1, 500), ('22', 2, 30)])
sinov('javobdagi buyurtma: yetkazish, jonatildi, jami', (j['buyurtma'].get('yetkazish'), j['buyurtma'].get('jonatildi'),
                                                          j['buyurtma'].get('jami')) == (15, True, 575), repr(j['buyurtma'])[:300])
m = sorov('editMessageText')
t = m[0]['text'] if m else ''
sinov("admin xabari: «🚚 Yetkazish puli: 15$», «📦 Allaqachon jo'natilgan», «💵 Jami 575$»",
      "🚚 Yetkazish puli: 15$\n📦 Allaqachon jo'natilgan\n💵 Jami 575$" in t, t)
bl = bold(t, m[0]['entities'] if m else [])
sinov("bold: «Yetkazish puli», «📦 Allaqachon jo'natilgan»", 'Yetkazish puli' in bl and "📦 Allaqachon jo'natilgan" in bl, repr(bl))
sinov("mijozga HECH NARSA ketmadi", not sorov('sendMessage') and not sorov('copyMessage')
      and all(str(d.get('chat_id')) == str(ADMIN) for _, d in SOROV if 'chat_id' in d), repr(SOROV)[:300])
sh = [p for a, p in SHEET if a == 'buyurtmaTahrir']
d = json.loads(sh[0]['data']) if sh else {}
sinov("Store: buyurtmaTahrir — yetkazish 15, jonatildi true, jami 575",
      (d.get('yetkazish'), d.get('jonatildi'), d.get('jami')) == (15, True, 575), repr(d)[:300])
sinov("Store: tovar ro'yxatida yetkazish YO'Q (Sotuvlar'ga tovar bo'lib tushmaydi)",
      [x['num'] for x in d.get('tovar') or []] == ['21', '22'], repr(d.get('tovar')))

print("— mijozning to'lov havolasi, chek qatorlari, Store yozuvi, admin ro'yxati")
u = bot._chek_tolov_url(b)
sinov("to'lov havolasi: y=15, j=1, s = 575 × 12000", 'y=15' in u and 'j=1' in u and 's=6900000' in u and 'u=575' in u, u)
q = bot._chek_tovar_qator(b)
sinov("chek tovar qatori: «🚚 Yetkazish / Доставка · 15$»", q.endswith('🚚 Yetkazish / Доставка · 15$\n'), q)
sd = bot._buyurtma_sheet_dict(MIJOZ, b)
sinov('_buyurtma_sheet_dict: yetkazish 15, jonatildi True', (sd.get('yetkazish'), sd.get('jonatildi')) == (15, True), repr(sd)[:200])
ad = bot._admin_buyurtma_dict(MIJOZ, b)
sinov('_admin_buyurtma_dict: yetkazish 15, jonatildi True', (ad.get('yetkazish'), ad.get('jonatildi')) == (15, True))
b0 = {k: v for k, v in b.items() if k not in ('yetkazish', 'jonatildi')}
u0 = bot._chek_tolov_url(b0)
sinov("yetkazishsiz buyurtma — havolada y / j yo'q, qator yo'q", 'y=' not in u0 and 'j=' not in u0
      and 'Yetkazish' not in bot._chek_tovar_qator(b0), u0)

print("— faqat jonatildi (yetkazish maydoni kelmadi) — yetkazish saqlanadi")
st, j = tahrir('TY01', ESKI_T, jonatildi=False)
b = yozuv('TY01')
sinov("jonatildi o'chdi, yetkazish 15 qoldi, jami 575", 'jonatildi' not in b and b.get('yetkazish') == 15 and b['jami'] == 575, repr(b)[:300])
st, j = tahrir('TY01', ESKI_T, jonatildi=True)
sinov("jonatildi qayta yoqildi", yozuv('TY01').get('jonatildi') is True)

print("— eski sayt (yetkazish / jonatildi umuman yo'q) — o'zgarmaydi")
st, j = tahrir('TY01', ESKI_T)
b = yozuv('TY01')
sinov("200, xabar='-', yozuv o'sha", st == 200 and j.get('xabar') == '-' and b.get('yetkazish') == 15 and b.get('jonatildi') is True
      and b['jami'] == 575, repr(j)[:200])

print("— buzuq yetkazish → 400, yozuv o'zgarmadi")
st, j = tahrir('TY01', ESKI_T, yetkazish=-5)
sinov('400 parametr', st == 400 and j.get('error') == 'parametr' and not SHEET and not SOROV, repr(j))
sinov("yozuv o'sha (575)", yozuv('TY01')['jami'] == 575)

print("— «📦 jo'natilgan» buyurtma: «✅ To'lov keldi» → to'g'ri «🚚 Yo'lda», isbot so'ralmaydi")
x0 = yozuv('TY01')['admin_xb'][0]
xb = {'message_id': 501, 'chat': {'id': ADMIN}, 'text': x0['t'], 'entities': x0['e']}
SOROV.clear()
SHEET.clear()
bot._YOLDA_KUT.clear()
asyncio.run(bot.buyurtma_holat_tugma(ADMIN, 501, f'bh:tolandi:{MIJOZ}:TY01', xb))
b = yozuv('TY01')
sinov("holat — yolda", b['holat'] == 'yolda', b['holat'])
sinov("«Yo'lda» isboti so'ralmadi (kutish yo'q)", not bot._YOLDA_KUT, repr(bot._YOLDA_KUT))
m = [x for x in sorov('editMessageText') if x.get('message_id') == 501]
t = m[0]['text'] if m else ''
sinov("zanjir: «✅ To'landi · HH:MM → 🚚 Yo'lda · HH:MM»", re.search(r"✅ To'landi · \d\d:\d\d → 🚚 Yo'lda · \d\d:\d\d", t) is not None, t)
rm = str(m[0].get('reply_markup') if m else '')
sinov("keyingi tugma — «Yetkazildi», «Yo'lda» tugmasi yo'q", f'bh:yetkazildi:{MIJOZ}:TY01' in rm and f'bh:yolda:{MIJOZ}:TY01' not in rm, rm[:300])
mj = [d for d in sorov('sendMessage') if str(d.get('chat_id')) == str(MIJOZ)]
sinov("mijozga — to'lov qabul qilindi xabari (bitta)", len(mj) == 1, repr(SOROV)[:400])

print("— belgisiz buyurtma: «✅ To'landi» → tolandi (eski xulq)")
yangi('TY02', holat='kutilmoqda')
asyncio.run(bot.buyurtma_holat_tugma(ADMIN, 0, f'bh:tolandi:{MIJOZ}:TY02'))
sinov('holat — tolandi', yozuv('TY02')['holat'] == 'tolandi')

print("— yetkazish o'chirildi (0) — jami qaytdi, kalitlar yo'q")
yangi('TY03', holat='kutilmoqda')
tahrir('TY03', ESKI_T, yetkazish=20, jonatildi=True)
sinov('20$ bilan jami 580', yozuv('TY03')['jami'] == 580)
st, j = tahrir('TY03', ESKI_T, yetkazish=0, jonatildi=False)
b = yozuv('TY03')
sinov("200, jami 560 (asl), yetkazish / jonatildi kalitlari yo'q", st == 200 and b['jami'] == 560 and 'yetkazish' not in b
      and 'jonatildi' not in b, repr(b)[:300])
t = sorov('editMessageText')[0]['text'] if sorov('editMessageText') else ''
sinov("admin xabarida yetkazish qatori yo'q", 'Yetkazish' not in t and "jo'natilgan" not in t and '💵 Jami 560$' in t, t)
sh = [p for a, p in SHEET if a == 'buyurtmaTahrir']
d = json.loads(sh[0]['data']) if sh else {}
sinov('Store: yetkazish 0, jonatildi false', (d.get('yetkazish'), d.get('jonatildi')) == (0, False), repr(d)[:200])

print("— tovar ham, yetkazish ham o'zgardi: 22 → 1 dona × 25$ + yetkazish 7.5$")
st, j = tahrir('TY03', [{'num': '21', 'soni': 1, 'narx': 500}, {'num': '22', 'soni': 1, 'narx': 25}], yetkazish=7.5)
sinov('jami 532.5', yozuv('TY03')['jami'] == 532.5, repr(yozuv('TY03')['jami']))

print(f'\n{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
