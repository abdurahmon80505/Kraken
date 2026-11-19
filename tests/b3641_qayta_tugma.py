# -*- coding: utf-8 -*-
"""tests/b3641_qayta_tugma.py — 3641: admin tugmalari doim bir xil tartibda (keyingi qadam → bron → manzil → «Mijozga yozish»
oxirida); sovg'a (0$) — to'lov tugmasi yo'q; bot qayta yonganda adminga yetgan buyurtma QAYTA yuborilmaydi, yetmagani esa
asl ko'rinishida (sovg'a, manzil, holat) ketadi; Sheets rad etgan yozuv navbatni to'xtatmaydi.

Ishga tushirish:  python tests/b3641_qayta_tugma.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get va bot._kk_sheet almashtirilgan, saqlash — o'chiq.
Buyurtmalar — soxta (uid 777001, №TG…); real mijozga tegilmaydi.
"""
import asyncio
import atexit
import json
import logging
import os
import shutil
import sys
import tempfile
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

for k in ('BOT_TOKEN', 'MAIN_CHANNEL_ID', 'WEBHOOK_SECRET', 'POST_CHANNEL_ID', 'POST_KANALLAR', 'TEST_CHANNEL_ID',
          'CHANNEL_ID', 'GURUH_KANAL_ID', 'ESKI_BOT_TOKEN', 'RENDER_URL', 'ADMIN_GURUH', 'SHEET_URL'):
    os.environ.pop(k, None)
_VAQT = tempfile.mkdtemp(prefix='b3641-')
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




def qatorlar(x):
    """Tugmalar ro'yxati — har qator: callback 'bh:yolda' kabi qisqa belgi yoki 'url' / 'bron' / 'joy'."""
    rm = (x.get('reply_markup') if 'reply_markup' in x else x) or {}
    nat = []
    for r in rm.get('inline_keyboard') or []:
        t = r[0]
        cb = t.get('callback_data') or ''
        if 'url' in t:
            nat.append('url')
        elif cb.startswith('bron_och'):
            nat.append('bron')
        elif cb.startswith('bh:'):
            nat.append(':'.join(cb.split(':')[:2]))
        else:
            nat.append('joy')
    return nat


def matnlar(x):
    return [t.get('text') for r in (x.get('reply_markup') or {}).get('inline_keyboard') or [] for t in r]


def klava(holat, b=None, bron=('11',)):
    return qatorlar(bot._buyurtma_klava(MIJOZ, 'TX01', holat, list(bron), b))


print('— tugmalar tartibi (3641)')
sinov("kutilmoqda: To'lov keldi → To'lovni kutmay → bron → Mijozga yozish (oxirida)",
      klava('kutilmoqda', {}) == ['bh:tolandi', 'bh:yolda', 'bron', 'url'], klava('kutilmoqda', {}))
sinov("kutilmoqda + manzil: manzil tugmalari bron'dan keyin, Mijozga yozish — oxirida",
      klava('kutilmoqda', {'joy': {'tur': 'bts', 'manzil': 'Sinov', 'bts': 'Toshkent'}})[-1] == 'url'
      and klava('kutilmoqda', {})[:3] == ['bh:tolandi', 'bh:yolda', 'bron'])
sinov("to'landi: faqat 🚚 Yo'lda (+ Mijozga yozish)", klava('tolandi', {}) == ['bh:yolda', 'url'], klava('tolandi', {}))
sinov("yo'lda: 📦 Yetkazildi + 🧾 Chek (3761) (+ Mijozga yozish)", klava('yolda', {}) == ['bh:yetkazildi', 'bh:yolda', 'url'], klava('yolda', {}))
sinov("yetkazildi: Yakunlandi → Baho so'ramay yopish → Mijozga yozish", klava('yetkazildi', {}) == ['bh:-', 'bh:yopildi', 'url'],
      klava('yetkazildi', {}))
sinov("bekor: 📍 holat → Mijozga yozish", klava('bekor', {}) == ['bh:-', 'url'], klava('bekor', {}))
sinov("naqd kutilmoqda: Yo'lda → bron → Mijozga yozish (To'lov keldi yo'q)",
      klava('kutilmoqda', {'tolov': 'naqd'}) == ['bh:yolda', 'bron', 'url'], klava('kutilmoqda', {'tolov': 'naqd'}))
k = bot._buyurtma_klava(MIJOZ, 'TX01', 'kutilmoqda', ['11'], {'sovga': True})
sinov("sovg'a tasdiqlanmagan: «✅ Sovg'a — tasdiqlash» → bron → Mijozga yozish; «To'lov» so'zi yo'q",
      qatorlar(k) == ['bh:tolandi', 'bron', 'url'] and not any("To'lov" in t for t in matnlar({'reply_markup': k}))
      and "Sovg'a" in matnlar({'reply_markup': k})[0], repr(k))
sinov("sovg'a to'landi: 🚚 Yo'lda (+ Mijozga yozish)", klava('tolandi', {'sovga': True}) == ['bh:yolda', 'url'])

print("— sovg'a (0$) buyurtma")
st = buyurtma('TG01', ['11'], ['sovgakod1'], tur='bts', bts='Toshkent')
b = yozuv('TG01')
adm = xabarlar(ADMIN)[0]
sinov("sovg'a: admin xabari — 🎁, «To'landi», «To'lov kutilmoqda» yo'q", st == 200 and "Sovg'a" in adm['text']
      and "To'lov kutilmoqda" not in adm['text'], adm['text'][:300])
sinov("sovg'a: tugmalar — 🚚 Yo'lda birinchi, Mijozga yozish oxirida, To'lov tugmasi yo'q",
      qatorlar(adm)[0] == 'bh:yolda' and qatorlar(adm)[-1] == 'url' and not any("To'lov" in t for t in matnlar(adm)), matnlar(adm))
sd = bot._buyurtma_sheet_dict(MIJOZ, b)
jy = json.loads(sd.get('joy') or '{}')
sinov("yozuvda savat havolasi saqlanadi (qayta yasashda 0$ / chegirma qaytadi)", (b.get('joy') or {}).get('savat') == ['sovgakod1'], repr(b.get('joy')))
sinov("Sheets'ga: joy (manzil) + _sovga, manba 'bot', telefon joy ichida yo'q",
      jy.get('_sovga') == 1 and jy.get('tur') == 'bts' and 'tel' not in jy and sd.get('manba') == 'bot', repr(sd)[:300])

print('— oddiy (to\'lanadigan) buyurtma')
st = buyurtma('TG02', ['12'])
adm = xabarlar(ADMIN)[0]
sinov("to'lanadigan: «To'lov kutilmoqda», tugmalar To'lov keldi → To'lovni kutmay → bron → … → Mijozga yozish",
      "To'lov kutilmoqda" in adm['text'] and qatorlar(adm)[:3] == ['bh:tolandi', 'bh:yolda', 'bron'] and qatorlar(adm)[-1] == 'url',
      repr(qatorlar(adm)))
bot._buyurtma_holat_qoy(MIJOZ, 'TG02', 'tolandi')
k = klava('tolandi', yozuv('TG02'), [])
sinov("to'langach: keyingi qadam — faqat 🚚 Yo'lda (manzil tugmasi bo'lsa — o'rtada), Mijozga yozish oxirida",
      k[0] == 'bh:yolda' and k[-1] == 'url' and not {'bh:tolandi', 'bron'} & set(k), repr(k))
b2 = dict(yozuv('TG02'))


def qayta_yon(qatorlar_sheet):
    """Render qayta yongandek: xotira bo'sh, Sheets'dan (mijozHammasi) yuklanadi."""
    bot._MIJOZ.clear()
    bot._BUYURTMA_KORILGAN.clear() if hasattr(bot, '_BUYURTMA_KORILGAN') else None
    bot._mijoz_sheet_birlash({'tels': [], 'buyurtma': qatorlar_sheet})


def sheet_qator(b, **ust):
    d = bot._buyurtma_sheet_dict(MIJOZ, b)
    d.update(ust)
    return d


def ish():
    SOROV.clear()
    return bot._buyurtma_xabar_ish()


print('— qayta yuborish (bot qayta yonganda) — 18:36 / 18:53 hodisasi')
b1 = dict(yozuv('TG01'))
eski = time.time() - 17 * 60
qayta_yon([sheet_qator(b1, admin_xabar='kutilmoqda', ts=eski)])
z = yozuv('TG01')
sinov("Sheets'dan tiklandi: joy (BTS), sovg'a belgisi, manba 'bot'", z and z.get('sovga') and (z.get('joy') or {}).get('tur') == 'bts'
      and z.get('manba') == 'bot', repr(z)[:300])
n = ish()
sinov("to'langan sovg'a (admin ko'rgan) — Sheets belgisi 'kutilmoqda' bo'lsa ham QAYTA YUBORILMAYDI", n == 0 and not xabarlar(ADMIN)
      and yozuv('TG01').get('admin_xabar') == '-', repr(xabarlar(ADMIN))[:200])

qayta_yon([sheet_qator(b1, admin_xabar='kutilmoqda', holat='kutilmoqda', ts=eski)])
n = ish()
sinov("bot qabul qilgan, 15 daq.dan eski, 'kutilmoqda' — qayta yuborilmaydi (Sheets belgisi eskirgan)", n == 0 and not xabarlar(ADMIN))

qayta_yon([sheet_qator(b1, admin_xabar='kutilmoqda', holat='kutilmoqda', manba='sayt', ts=time.time() - 200)])
yozuv('TG01').pop('sovga', None)
n = ish()
adm = (xabarlar(ADMIN) or [{}])[0]
sinov("haqiqatan yetmagan (sayt zaxirasi): qayta yuborildi — ♻️, 🎁 Sovg'a, BTS, «To'lov kutilmoqda» YO'Q",
      n == 1 and '♻️' in adm.get('text', '') and "Sovg'a" in adm.get('text', '') and "To'lov kutilmoqda" not in adm.get('text', ''),
      adm.get('text', '')[:400])
sinov("qayta yuborilgan sovg'a: To'lov keldi / To'lovni kutmay tugmasi yo'q; Mijozga yozish — oxirida",
      adm and not any("To'lov" in t for t in matnlar(adm)) and qatorlar(adm)[-1] == 'url' and qatorlar(adm)[0] in ('bh:yolda', 'bh:tolandi'),
      repr(matnlar(adm)))

qayta_yon([sheet_qator(b2, admin_xabar='kutilmoqda', ts=time.time() - 200)])
n = ish()
sinov("to'langan (holat 'tolandi') buyurtma — qayta yuborilmaydi", n == 0 and not xabarlar(ADMIN))

qayta_yon([sheet_qator(b2, admin_xabar='kutilmoqda', holat='kutilmoqda', ts=time.time() - 200)])
n = ish()
adm = (xabarlar(ADMIN) or [{}])[0]
sinov("yangi (≤15 daq), to'lanmagan, xabari yetmagan — qayta yuboriladi, holat «To'lov kutilmoqda», tugmalar tartibda",
      n == 1 and "To'lov kutilmoqda" in adm.get('text', '') and qatorlar(adm)[:3] == ['bh:tolandi', 'bh:yolda', 'bron']
      and qatorlar(adm)[-1] == 'url', repr(qatorlar(adm)))

qayta_yon([sheet_qator(b2, admin_xabar='kutilmoqda', holat='kutilmoqda', ts=eski)])
with bot._MIJOZ_LOCK:
    yozuv('TG02')['_xabar'] = {'matn': 'Sinov matni', 'bron': ['12'], 'b': {}}
n = ish()
sinov("`_xabar` bor (shu ishga tushishda yubora olmagan) — eski bo'lsa ham qayta yuboriladi", n == 1 and len(xabarlar(ADMIN)) == 1)

print('— boshqa buyurtma bekor qilinsa birinchisi qayta yuborilmaydi')
bot._MIJOZ.clear()
buyurtma('TG05', ['11'], ['sovgakod1'], tur='bts', bts='Toshkent')
buyurtma('TG06', ['12'])
for o in ('TG05', 'TG06'):
    yozuv(o)['ts'] = time.time() - 600
r = asyncio.run(bot.buyurtma_bekor_endpoint(So({'initData': str(MIJOZ), 'order': 'TG06'})))
sinov('ikkinchisi bekor qilindi', r.status == 200 and yozuv('TG06')['holat'] == 'bekor')
n = ish()
sinov("fon sikli: birinchi (sovg'a) buyurtma adminga QAYTA ketmaydi", n == 0 and not [x for x in xabarlar(ADMIN) if 'TG05' in x.get('text', '')],
      repr(xabarlar(ADMIN))[:200])

print('— Sheets sync: rad etilgan yozuv navbatni to\'xtatmaydi')
eski_y, eski_s = bot._mijoz_sync_yoqilgan, bot._kk_sheet
yozilgan = []


def _sh(action, timeout=30, **p):
    d = json.loads(p.get('data') or '{}')
    yozilgan.append(d.get('order'))
    return {'ok': False, 'msg': 'sinov rad'} if d.get('order') == 'TG05' else {'ok': True}


bot._mijoz_sync_yoqilgan = lambda: True
bot._kk_sheet = _sh
with bot._MIJOZ_SYNC_QULF:
    bot._MIJOZ_SYNC.clear()
    bot._MIJOZ_SYNC.update({('b', str(MIJOZ), 'TG05'), ('b', str(MIJOZ), 'TG06')})
n = bot._mijoz_sync_yubor()
sinov("TG05 rad (ok:false) — TG06 baribir yozildi; TG05 navbatda qoldi",
      n == 1 and set(yozilgan) == {'TG05', 'TG06'} and bot._MIJOZ_SYNC == {('b', str(MIJOZ), 'TG05')}, repr((n, yozilgan, bot._MIJOZ_SYNC)))
bot._mijoz_sync_yoqilgan, bot._kk_sheet = eski_y, eski_s
with bot._MIJOZ_SYNC_QULF:
    bot._MIJOZ_SYNC.clear()

print('— 3749: tugma maxfiylik xatosi; «yetmadi» belgisi; №S792WH bir marta')


def mijozga():
    return [x for x in SOROV if str(x.get('chat_id')) == str(MIJOZ)]


eski_ts = time.time() - 3 * 3600
qayta_yon([sheet_qator(b1, admin_xabar='yetmadi', ts=eski_ts)])
n = ish()
adm = (xabarlar(ADMIN) or [{}])[0]
sinov("'yetmadi' + sovg'a (holat to'landi) + 3 soat eski — QAYTA yuboriladi (♻️), mijozga takror xabar yo'q",
      n == 1 and '♻️' in adm.get('text', '') and not mijozga() and ':' in str(yozuv('TG01').get('admin_xabar')),
      repr((n, yozuv('TG01').get('admin_xabar'), len(mijozga()))))
sinov("yetgach — ikkinchi aylanishda yuborilmaydi", ish() == 0)
qayta_yon([sheet_qator(b1, admin_xabar='12:30', ts=eski_ts)])
sinov("to'landi + admin_xabar HH:MM — yuborilmaydi", ish() == 0 and yozuv('TG01').get('admin_xabar') == '12:30')

qayta_yon([sheet_qator(b1, order='S792WH', admin_xabar='-', ts=eski_ts), sheet_qator(b2, admin_xabar='-', ts=eski_ts)])
n = ish()
sinov("№S792WH ('-') — bir marta qayta yuborildi; boshqa '-' buyurtma — yo'q",
      n == 1 and len(xabarlar(ADMIN)) == 1 and 'S792WH' in xabarlar(ADMIN)[0].get('text', '')
      and yozuv('TG02').get('admin_xabar') == '-', repr([x.get('text', '')[:80] for x in xabarlar(ADMIN)]))
sinov("№S792WH — keyingi aylanishda takror yo'q", ish() == 0)

# Haqiqiy _TgReq yo'li: soxta Telegram — tg://user tugmasi bo'lsa 400 BUTTON_USER_PRIVACY_RESTRICTED
eski_post, eski_asl = bot.req.post, bot.req._asl
del bot.req.post


class J400:
    status_code = 400

    def __init__(self, d):
        self.text = json.dumps({'ok': False, 'error_code': 400, 'description': d})

    def json(self):
        return json.loads(self.text)


class Soxta:
    def __init__(self, hammasi_xato=False):
        self.hammasi_xato = hammasi_xato

    def post(self, url, **kw):
        p = kw.get('json') or kw.get('data') or {}
        if self.hammasi_xato:
            return J400("Bad Request: can't parse entities")
        if 'tg://user' in json.dumps(p.get('reply_markup') or {}):
            return J400('Bad Request: BUTTON_USER_PRIVACY_RESTRICTED')
        return _post(url, **kw)


bot.req._asl = Soxta()
qayta_yon([sheet_qator(b1, admin_xabar='yetmadi', ts=eski_ts)])
SOROV.clear()
n = bot._buyurtma_xabar_ish()
adm = (xabarlar(ADMIN) or [{}])[-1]
sinov("profil tugmasi rad etildi (privacy) — xabar adminga TUGMASIZ yetdi, boshqa tugmalar joyida",
      n == 1 and 'tg://user' not in tugmalar(adm) and 'bh:' in tugmalar(adm), repr((n, tugmalar(adm)))[:300])
SOROV.clear()
h, _ = bot._kk_tg('sendMessage', {'chat_id': ADMIN, 'text': 'konkurs', 'reply_markup': {'inline_keyboard': [
    [{'text': 'Yozish', 'url': f'tg://user?id={MIJOZ}'}], [{'text': 'X', 'callback_data': 'x'}]]}})
sinov("konkurs (_kk_tg) — privacy xatosida ham 'yuborildi', tugmasiz", h == 'yuborildi' and 'tg://user' not in tugmalar(SOROV[-1]),
      repr(h))

bot.req._asl = Soxta(hammasi_xato=True)
qayta_yon([sheet_qator(b2, admin_xabar='kutilmoqda', holat='kutilmoqda', ts=time.time() - 200)])
n = bot._buyurtma_xabar_ish()
sinov("Telegram aniq rad etsa — belgi 'yetmadi' (qayta yonishdan keyin ham yuboriladi)",
      n == 0 and yozuv('TG02').get('admin_xabar') == 'yetmadi', repr(yozuv('TG02').get('admin_xabar')))
bot.req._asl, bot.req.post = eski_asl, eski_post


print(f'\n{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
