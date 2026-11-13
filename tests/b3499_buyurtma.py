# -*- coding: utf-8 -*-
"""tests/b3499-bot.py — 3499 (2026-11-13): bot buyurtma yo'lidagi yashirin xatolar.

Ishga tushirish:  python tests/b3499-bot.py <bot papkasi>   (sukut — BOT_PAPKA yoki Kraken_bot)
  Internetsiz — soxta Telegram / Sheets, soxta mijozlar 42, 43 va admin 777.
Tekshiriladi:
  1) boshqa mijozning buyurtma raqami — 409, chek kaliti (ck) berilmaydi, adminga xabar yo'q; sayt zaxirasidan ham olinmaydi
  2) sayt zaxirasidan kelgan buyurtma — jami mijoz yuborgan usd dan EMAS, server narxidan (1$ / juda katta summa — e'tiborsiz);
     zaxira oldin, /buyurtma keyin kelsa ham — jami server hisobidan; RU tilida ham to'g'ri summa
  3) bir buyurtma bir vaqtda ikki marta (havola narxini kutish paytida sayt qayta yubordi) — adminga BITTA xabar
  4) imzosiz — 401, bo'sh ism — 400
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
    print("  · 3499: o'tkazildi — bu bot.py eski (GitHub Kraken bot bilan: BOT_PAPKA=<klon> yoki argument)")
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


# ── 1) boshqa mijozning raqami ──
def t_raqam_band():
    _yangi()
    kod, j = _buy(MIJOZ, 'SAB123')
    assert kod == 200 and j.get('ok') and len(j.get('ck') or '') == 16, (kod, j)
    kod, j = _buy(BOSHQA, 'SAB123')
    assert kod == 409 and 'ck' not in j, (kod, j)             # kalit boshqaga berilmaydi
    assert len(admin_xabar) == 1 and not _bor(BOSHQA, 'SAB123'), (admin_xabar, bot._mijoz_ol(BOSHQA))
    assert bot._chek_uid_top('SAB123')[0] == MIJOZ
    kod, j = _buy(MIJOZ, 'SAB123')                              # o'zi takror yuborsa — avvalgidek takror, kalit bilan
    assert kod == 200 and j.get('takror') and j.get('ck'), (kod, j)


def t_zaxira_band():
    _yangi()
    _buy(MIJOZ, 'SAB124')
    n = bot._buyurtma_zaxira_birlash({'buyurtma': [
        {'user_id': str(BOSHQA), 'order': 'SAB124', 'ts': 5, 'tovar': [{'num': '300', 'narx': 10, 'soni': 1}]}]})
    assert n == 0 and not _bor(BOSHQA, 'SAB124'), bot._mijoz_ol(BOSHQA)
    assert bot._chek_uid_top('SAB124')[0] == MIJOZ


# ── 2) zaxiradagi jami — server narxidan ──
def t_zaxira_jami():
    _yangi()
    n = bot._buyurtma_zaxira_birlash({'buyurtma': [
        {'user_id': str(MIJOZ), 'order': 'ZJ0001', 'ts': 5, 'jami': 1, 'til': 'ru', 'joy': {'kurs': 12700},
         'tovar': [{'num': '300', 'nom': 'iPhone 13', 'narx': 250, 'soni': 2}]},
        {'user_id': str(MIJOZ), 'order': 'ZJ0002', 'ts': 6, 'jami': 1e15, 'joy': {'kurs': 12700},
         'tovar': [{'num': '301', 'nom': 'Kabel', 'narx': 3.5, 'soni': 1}]},
        {'user_id': str(MIJOZ), 'order': 'ZJ0003', 'ts': 7, 'jami': 40, 'joy': {'kurs': 12700},
         'tovar': [{'num': '302', 'nom': 'Topilmagan'}]}]})
    assert n == 3, n
    assert _b(MIJOZ, 'ZJ0001')['jami'] == 500, _b(MIJOZ, 'ZJ0001')       # mijoz 1$ yozgan edi
    assert _b(MIJOZ, 'ZJ0002')['jami'] == 3.5, _b(MIJOZ, 'ZJ0002')       # juda katta summa — e'tiborsiz
    assert _b(MIJOZ, 'ZJ0003')['jami'] is None                           # narx noma'lum — summa yo'q, «To'lash» chiqmaydi
    assert bot._chek_summa(_b(MIJOZ, 'ZJ0001'))[:2] == (500.0, 6350000)
    matn = bot._chek_buyurtma_matn(_b(MIJOZ, 'ZJ0001'))
    assert 'Итого: <b>500$ ≈ 6 350 000 so\'m</b>' in matn, matn         # RU
    assert bot._chek_tolov_url(_b(MIJOZ, 'ZJ0003')) == ''


def t_zaxira_keyin_buyurtma():
    """Fon sikli zaxirani /buyurtma dan OLDIN olib qo'ydi (jami — mijozniki), so'ng /buyurtma keldi → jami server hisobidan."""
    _yangi()
    bot._MIJOZ[str(MIJOZ)] = {'tels': {}, 'buyurtma': [
        {'order': 'ZJ0010', 'ts': time.time(), 'holat': 'kutilmoqda', 'tovar': [{'num': '261', 'narx': 25, 'soni': 1}],
         'jami': 1, 'manba': 'sayt', 'admin_xabar': 'kutilmoqda', 'joy': {'kurs': 12700}}]}
    kod, j = _buy(MIJOZ, 'ZJ0010')
    assert kod == 200 and j.get('ok'), (kod, j)
    b = _b(MIJOZ, 'ZJ0010')
    assert b['jami'] == 50 and len(b['tovar']) == 2, b                  # 261 + 262, 25$ dan
    assert len(admin_xabar) == 1


# ── 3) bir vaqtda ikki so'rov ──
def t_bir_vaqtda():
    _yangi()

    async def ikki():
        d = _malumot(MIJOZ, 'SBV001', savat=['abc12345'])
        return await asyncio.gather(bot.buyurtma_endpoint(_So(dict(d))), bot.buyurtma_endpoint(_So(dict(d))))
    _executor(_kechikib)
    try:
        r1, r2 = asyncio.run(ikki())
    finally:
        _executor(_fonsiz)
    j = sorted([_javob(r1), _javob(r2)], key=lambda x: bool(x[1].get('takror')))
    assert j[0][0] == 200 and j[0][1].get('ok') and not j[0][1].get('takror'), j
    assert j[1][0] == 200 and j[1][1].get('takror') and j[1][1].get('ck') == j[0][1].get('ck'), j
    assert len(admin_xabar) == 1, admin_xabar                           # ilgari — 2 ta
    assert [x['order'] for x in bot._mijoz_ol(MIJOZ)['buyurtma']] == ['SBV001']
    assert not bot._BUYURTMA_JARAYON


# ── 4) imzosiz / bo'sh maydon ──
def t_imzosiz_bosh():
    _yangi()
    kod, j = _javob(asyncio.run(bot.buyurtma_endpoint(_So(dict(_malumot(MIJOZ, 'SIM001'), initData='')))))
    assert kod == 401, (kod, j)
    kod, j = _buy(MIJOZ, 'SIM002', name='   ')
    assert kod == 400, (kod, j)
    assert not admin_xabar and not bot._BUYURTMA_JARAYON


sinov("boshqa mijozning raqami — 409, kalit yo'q, adminga xabar yo'q; o'zi takror yuborsa — takror", t_raqam_band)
sinov("sayt zaxirasida boshqa mijozning raqami — olinmaydi", t_zaxira_band)
sinov("sayt zaxirasidan kelgan buyurtma — jami server narxidan (1$, juda katta, noma'lum), RU matnda ham", t_zaxira_jami)
sinov("zaxira oldin, /buyurtma keyin — jami va tarkib server hisobidan", t_zaxira_keyin_buyurtma)
sinov("bir buyurtma bir vaqtda ikki marta (havola kutilayotganda) — adminga bitta xabar", t_bir_vaqtda)
sinov("imzosiz — 401, bo'sh ism — 400", t_imzosiz_bosh)

print('3499 bot: %s' % ('0 xato' if not xato else f'{xato} XATO'))
sys.exit(1 if xato else 0)
