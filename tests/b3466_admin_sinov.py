# -*- coding: utf-8 -*-
"""tests/b3466-bot.py — 3466 (2026-11-13): admin buyurtmasi ro'yxatga / jadvalga / bandlikka yozilmaydi.

Ishga tushirish:  python tests/b3466-bot.py <bot papkasi>   (sukut — BOT_PAPKA yoki Kraken_bot)
  Internetsiz — soxta Telegram / Sheets, soxta mijoz 42 va admin 777.
Tekshiriladi: admin sinov xaridi /admin_buyurtmalar ro'yxatida YO'Q (mijozniki bor); 3394 dan oldin yozilgan admin yozuvi
(Sheets / fayl / sayt zaxirasidan) — sinov bo'ladi, Sheets'ga qayta yozilmaydi, admin nomidagi bron ochiladi; mijoz yozuvi va
broni — o'zgarishsiz.
"""
import os
import sys
import json
import time
import hmac
import asyncio
import hashlib
import logging
import tempfile
import urllib.parse

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ILDIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KB = os.path.join(ILDIZ, 'Kraken_bot')
sys.path.insert(0, os.path.abspath((sys.argv[1] if len(sys.argv) > 1 else '') or os.environ.get('BOT_PAPKA')
                                   or (_KB if os.path.isdir(_KB) else ILDIZ)))   # Kraken repo: tests/ ning ota papkasi
_TMP = tempfile.mkdtemp()
TOKEN = '123456:SINOV'
for _k, _v in {'BOT_TOKEN': TOKEN, 'BOT_USERNAME': 'sinov_bot', 'SHEET_URL': '', 'API_KEY': '',
               'CHANNEL_ID': '@sinov_kanal', 'ADMIN_ID': '777', 'ADMIN_USERNAME': 'nuqta_tech_admin',
               'MIJOZ_FAYL': os.path.join(_TMP, 'mijoz.json'), 'BRON_FAYL': os.path.join(_TMP, 'bron.json')}.items():
    os.environ[_k] = _v
for _k in ('ADMIN_GURUH', 'RENDER_INSTANCE_ID', 'ESKI_BOT_TOKEN'):
    os.environ.pop(_k, None)

import bot  # noqa: E402

if not hasattr(bot, '_admin_sinov_belgila'):
    print("  · 3466: o'tkazildi — bu bot.py da 3466 tuzatishi yo'q (GitHub Kraken bot bilan: BOT_PAPKA=<klon> yoki argument)")
    sys.exit(0)

logging.disable(logging.CRITICAL)
xato = 0


def sinov(nom, fn):
    global xato
    try:
        fn()
        print('  ✓ ' + nom)
    except Exception as e:
        xato += 1
        print('  ✗ %s — %s: %s' % (nom, type(e).__name__, str(e)[:600]))


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

MIJOZ, ADMIN = 42, 777
sheet = []       # (action, params)
admin_xabar = []
bron = []
tel_qosh = []

bot._kk_sheet = lambda action, timeout=30, **p: (sheet.append((action, p)), {'ok': True})[1]
bot._mijoz_sync_yoqilgan = lambda: True
bot._buyurtma_tayyorla = lambda uid, num, order, *a, **k: {'matn': f'🛒 <b>Yangi buyurtma</b> №{order}', 'bron': True}
bot._mijoz_tovarlar = lambda num, qolgan, *a, **k: [{'num': n, 'nom': 'Anker hub', 'narx': 25, 'soni': 1} for n in [num] + list(qolgan)]
bot._buyurtma_sovga_qoy = lambda *a, **k: None
bot._chek_mijozga_xabar = lambda *a, **k: None
bot._bron_olish = lambda num: None
bot._bron_qoy = lambda num, uid, order: bron.append((num, uid, order))
_asl_tel = bot._mijoz_tel_qosh
bot._mijoz_tel_qosh = lambda uid, tel, tur: tel_qosh.append((uid, tel))


def _yubor(uid, num, order, *a, tayyor=None, **k):
    admin_xabar.append(tayyor['matn'])
    return True, None


bot._buyurtma_yubor = _yubor


def _imzo(uid, til='uz'):
    p = {'auth_date': str(int(time.time())), 'query_id': 'Q1',
         'user': json.dumps({'id': uid, 'first_name': 'Sinov', 'language_code': til})}
    chek = '\n'.join(f'{k}={v}' for k, v in sorted(p.items()))
    secret = hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
    p['hash'] = hmac.new(secret, chek.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(p)


class _So:
    def __init__(self, jsn):
        self.jsn = jsn

    async def json(self):
        return self.jsn


def _yangi():
    for x in (sheet, admin_xabar, bron, tel_qosh):
        x.clear()
    bot._MIJOZ.clear(), bot._MIJOZ_SYNC.clear(), bot._BUYURTMA_KORILGAN.clear(), bot._BUYURTMA_SONI.clear()


def _buy(uid, order):
    r = asyncio.run(bot.buyurtma_endpoint(_So({
        'initData': _imzo(uid), 'num': '261', 'nums': ['261', '262'], 'order': order, 'name': 'Sinov', 'phone': '+998 90 123 45 67',
        'tur': 'emu', 'manzil': 'Toshkent, Chilonzor', 'kurs': 12700})))
    return r.status, json.loads(r.text)


def _b(uid, order):
    return next(x for x in bot._mijoz_ol(uid)['buyurtma'] if x['order'] == order)


def _royxat():
    r = asyncio.run(bot.admin_buyurtmalar_endpoint(_So({'initData': _imzo(ADMIN)})))
    return r.status, json.loads(r.text)


def t_royxat():
    _yangi()
    _buy(ADMIN, 'SIN010')
    _buy(MIJOZ, 'MIJ010')
    kod, j = _royxat()
    assert kod == 200 and j.get('ok'), (kod, j)
    orders = [x['order'] for x in j['buyurtma']]
    assert orders == ['MIJ010'], orders            # admin sinovi ro'yxatda yo'q
    assert _b(ADMIN, 'SIN010').get('sinov') is True   # yozuv botda qoladi (chek / to'lov sahifasi ishlaydi)
    kod, _ = asyncio.run(bot.admin_buyurtmalar_endpoint(_So({'initData': _imzo(MIJOZ)}))).status, None
    assert kod == 401, kod


def t_sheets_eski():
    """3394 dan oldin Sheets'ga tushgan admin qatori (SJ8N8H kabi): yuklanganda sinov, Sheets'ga qayta yozilmaydi, bron ochiladi."""
    _yangi()
    bot._BRON.clear()
    bot._BRON['153'] = {'uid': ADMIN, 'order': 'SJ8N8H', 'ts': time.time()}
    bot._BRON['261'] = {'uid': MIJOZ, 'order': 'MIJ020', 'ts': time.time()}
    bot._mijoz_sheet_birlash({'tels': [], 'buyurtma': [
        {'user_id': str(ADMIN), 'order': 'SJ8N8H', 'ts': 1794486463, 'holat': 'kutilmoqda', 'tovar': [{'num': '153'}], 'jami': 350},
        {'user_id': str(MIJOZ), 'order': 'MIJ020', 'ts': 1794486000, 'holat': 'kutilmoqda', 'tovar': [{'num': '261'}], 'jami': 25}]})
    assert _b(ADMIN, 'SJ8N8H').get('sinov') is True
    assert 'sinov' not in _b(MIJOZ, 'MIJ020')
    assert '153' not in bot._BRON and bot._BRON.get('261', {}).get('uid') == MIJOZ, bot._BRON
    assert [x['order'] for x in _royxat()[1]['buyurtma']] == ['MIJ020']
    bot._mijoz_sync_belgila('b', str(ADMIN), 'SJ8N8H')   # masalan, admin bekor qildi — navbatga tushdi
    bot._mijoz_sync_yubor()
    assert not [p for a, p in sheet if a == 'buyurtmaYoz' and 'SJ8N8H' in (p.get('data') or '')], sheet


def t_fayl_zaxira():
    """Fayldan yuklanganda va sayt zaxirasidan kelgan admin buyurtmasi — sinov, bron qo'yilmaydi."""
    _yangi()
    bot._BRON.clear()
    with open(bot.MIJOZ_FAYL, 'w', encoding='utf-8') as f:
        json.dump({str(ADMIN): {'tels': {}, 'buyurtma': [{'order': 'ESKI01', 'ts': 1, 'holat': 'kutilmoqda'}]}}, f)
    bot._mijoz_yuklash()
    assert _b(ADMIN, 'ESKI01').get('sinov') is True
    asl = bot._bron_olish
    bot._bron_olish = lambda num: bot._BRON.get(str(num))
    bot._bron_qoy = lambda num, uid, order: bot._BRON.__setitem__(str(num), {'uid': uid, 'order': order, 'ts': 0})
    n = bot._buyurtma_zaxira_birlash({'buyurtma': [
        {'user_id': str(ADMIN), 'order': 'ZAX001', 'ts': 5, 'tovar': [{'num': '300'}]},
        {'user_id': str(MIJOZ), 'order': 'ZAX002', 'ts': 6, 'tovar': [{'num': '301'}]}]})
    bot._bron_olish = asl
    assert n == 2, n
    assert _b(ADMIN, 'ZAX001').get('sinov') is True and 'sinov' not in _b(MIJOZ, 'ZAX002')
    assert '300' not in bot._BRON and bot._BRON.get('301', {}).get('uid') == MIJOZ, bot._BRON


sinov("admin sinov xaridi /admin_buyurtmalar ro'yxatida yo'q, mijozniki bor; yozuv botda qoladi", t_royxat)
sinov("Sheets'dagi eski admin qatori (SJ8N8H) — sinov, ro'yxatda yo'q, Sheets'ga qayta yozilmaydi, bron ochiladi", t_sheets_eski)
sinov("fayl / sayt zaxirasidan kelgan admin buyurtmasi — sinov, bron yo'q; mijozniki o'zgarishsiz", t_fayl_zaxira)
print('  %s 3466 bot: %s' % ('✓' if not xato else '✗', '0 xato' if not xato else '%d xato' % xato))
sys.exit(1 if xato else 0)
