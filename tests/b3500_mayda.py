# -*- coding: utf-8 -*-
"""tests/b3500_mayda.py — 3500 (2026-11-13): 3499 dan qolgan mayda ishlar (bot qismi).

Ishga tushirish:  python tests/b3500_mayda.py <bot papkasi>   (sukut — BOT_PAPKA yoki Kraken_bot)
  Internetsiz — soxta Telegram / Sheets, soxta mijozlar 42, 43 va admin 777.
Tekshiriladi:
  1) admin sinov xaridi — _BUYURTMA_SONI limitiga kirmaydi; 24 soatdan eski _BUYURTMA_KORILGAN admin tarmog'ida ham tozalanadi
  2) Yandex joyi (lat / lon) — matn, chegaradan tashqari, NaN — havolaga tushmaydi («joy belgilanmagan»); to'g'risi — 6 xona
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
                                   or (_KB if os.path.isdir(_KB) else ILDIZ)))
_TMP = tempfile.mkdtemp()
TOKEN = '123456:SINOV'
for _k, _v in {'BOT_TOKEN': TOKEN, 'BOT_USERNAME': 'sinov_bot', 'SHEET_URL': '', 'API_KEY': '',
               'CHANNEL_ID': '@sinov_kanal', 'ADMIN_ID': '777', 'ADMIN_USERNAME': 'nuqta_tech_admin',
               'MIJOZ_FAYL': os.path.join(_TMP, 'mijoz.json'), 'BRON_FAYL': os.path.join(_TMP, 'bron.json')}.items():
    os.environ[_k] = _v
for _k in ('ADMIN_GURUH', 'RENDER_INSTANCE_ID', 'ESKI_BOT_TOKEN'):
    os.environ.pop(_k, None)

import bot  # noqa: E402

if not hasattr(bot, '_admin_buyurtma_tozala'):
    print("  · 3500: o'tkazildi — bu bot.py eski (GitHub Kraken bot bilan: BOT_PAPKA=<klon> yoki argument)")
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


def _kechikib(self, ex, f, *a):
    """Fon ishi «sekin» — haqiqiy Apps Script so'rovidek: natija 50 ms dan keyin (shu orada boshqa so'rov kira oladi)."""
    fut = self.create_future()

    def tayyor():
        try:
            fut.set_result(f(*a))
        except Exception as e:
            fut.set_exception(e)
    self.call_later(0.05, tayyor)
    return fut


_LOOPLAR = [asyncio.SelectorEventLoop] + ([asyncio.ProactorEventLoop] if hasattr(asyncio, 'ProactorEventLoop') else [])


def _executor(f):
    for L in _LOOPLAR:
        L.run_in_executor = f


_executor(_fonsiz)

MIJOZ, BOSHQA, ADMIN = 42, 43, 777
admin_xabar = []
mijoz_xabar = []

bot._kk_sheet = lambda action, timeout=30, **p: {'ok': True}
bot._mijoz_sync_yoqilgan = lambda: True
bot._buyurtma_tayyorla = lambda uid, num, order, *a, **k: {'matn': f'🛒 <b>Yangi buyurtma</b> №{order}', 'bron': [num]}
bot._mijoz_tovarlar = lambda num, qolgan, *a, **k: [{'num': n, 'nom': 'Anker hub', 'narx': 25, 'soni': 1} for n in [num] + list(qolgan)]
bot._buyurtma_sovga_qoy = lambda *a, **k: None
bot._chek_mijozga_xabar = lambda uid, order: mijoz_xabar.append((uid, order))
bot._bron_olish = lambda num: None
bot._bron_qoy = lambda num, uid, order: None
bot._bron_ogoh_yubor = lambda *a, **k: None
bot._mijoz_tel_qosh = lambda uid, tel, tur: None
bot._savat_kel_narxlar = lambda kodlar: ({}, False)
bot._havola_tenglash = lambda num, qolgan, sonlar, ranglar, kel: (num, qolgan, sonlar, ranglar)


def _yubor(uid, num, order, *a, tayyor=None, **k):
    admin_xabar.append(tayyor['matn'])
    return True, None


bot._buyurtma_yubor = _yubor
bot._admin_sinov_xabar = lambda matn, *a, **k: (admin_xabar.append(matn), True)[1]


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
    for x in (admin_xabar, mijoz_xabar):
        x.clear()
    for d in (bot._MIJOZ, bot._MIJOZ_SYNC, bot._BUYURTMA_KORILGAN, bot._BUYURTMA_SONI):
        d.clear()
    bot._BUYURTMA_JARAYON.clear()


def _malumot(uid, order, til='uz', **qosh):
    d = {'initData': _imzo(uid, til), 'num': '261', 'nums': ['261', '262'], 'order': order, 'name': 'Sinov',
         'phone': '+998 90 123 45 67', 'tur': 'emu', 'manzil': 'Toshkent, Chilonzor', 'kurs': 12700}
    d.update(qosh)
    return d


def _javob(r):
    return r.status, json.loads(r.text)


def _buy(uid, order, **qosh):
    return _javob(asyncio.run(bot.buyurtma_endpoint(_So(_malumot(uid, order, **qosh)))))


def _b(uid, order):
    return next(x for x in bot._mijoz_ol(uid)['buyurtma'] if x['order'] == order)


def _bor(uid, order):
    return any(x.get('order') == order for x in bot._mijoz_ol(uid)['buyurtma'])


# ── 1) admin sinov xaridi va limit ──
def t_admin_limit():
    _yangi()
    for i in range(7):                                              # admin — limitsiz (ilgari 6-si 429)
        kod, j = _buy(ADMIN, 'SAD%03d' % i)
        assert kod == 200 and j.get('sinov'), (i, kod, j)
    assert not bot._BUYURTMA_SONI.get(ADMIN), bot._BUYURTMA_SONI
    assert len(admin_xabar) == 7
    for i in range(5):                                              # mijoz — limit avvalgidek
        kod, j = _buy(MIJOZ, 'SMJ%03d' % i)
        assert kod == 200 and not j.get('sinov'), (i, kod, j)
    kod, j = _buy(MIJOZ, 'SMJ005')
    assert kod == 429, (kod, j)


def t_admin_tozalash():
    _yangi()
    eski = time.time() - 90000
    bot._BUYURTMA_KORILGAN[(ADMIN, 'ESKI01')] = eski
    bot._BUYURTMA_KORILGAN[(MIJOZ, 'ESKI02')] = eski
    bot._BUYURTMA_KORILGAN[(MIJOZ, 'YANGI1')] = time.time() - 60
    kod, j = _buy(ADMIN, 'SAD100')
    assert kod == 200 and j.get('sinov'), (kod, j)
    k = bot._BUYURTMA_KORILGAN
    assert (ADMIN, 'ESKI01') not in k and (MIJOZ, 'ESKI02') not in k, k   # ilgari admin tarmog'ida tozalanmasdi
    assert (MIJOZ, 'YANGI1') in k and (ADMIN, 'SAD100') in k, k
    kod, j = _buy(ADMIN, 'SAD100')                                  # takror — avvalgidek
    assert kod == 200 and j.get('takror'), (kod, j)



# ── 2) joy koordinatasi (sayt zaxirasidan kelgan yozuv ham shu matndan o'tadi) ──
def t_joy_chegara():
    jm = bot._buyurtma_joy_matn
    yaxshi = jm({'tur': 'yandex', 'lat': 41.2995671234, 'lon': '69.2401'})
    assert 'pt=69.2401,41.299567&' in yaxshi and 'Yandex' in yaxshi, yaxshi
    for joy in ({'lat': 95, 'lon': 69}, {'lat': 41, 'lon': 200}, {'lat': '41"><script>', 'lon': 69},
                {'lat': 'nan', 'lon': 69}, {'lat': 41, 'lon': 'inf'}, {'lat': 41}, {'lat': None, 'lon': None},
                {'lat': [41], 'lon': 69}, {}):
        m = jm(dict(joy, tur='yandex'))
        assert 'joy belgilanmagan' in m and 'href' not in m, (joy, m)   # ilgari — havolaga xom matn / 95 tushardi


sinov("admin sinov xaridi — limitga kirmaydi (7 marta), mijozda 6-si — 429", t_admin_limit)
sinov("admin sinov xaridida ham 24 soatdan eski «ko'rilgan» yozuvlar tozalanadi", t_admin_tozalash)
sinov("Yandex joyi — yaroqsiz koordinata havolaga tushmaydi, to'g'risi 6 xonagacha", t_joy_chegara)

print('3500 bot: %s' % ('0 xato' if not xato else f'{xato} XATO'))
sys.exit(1 if xato else 0)
