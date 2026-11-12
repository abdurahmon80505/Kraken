# -*- coding: utf-8 -*-
"""tests/b3394-bot.py — 3394 (2026-11-12): ADMIN sinov xaridi.

Ishga tushirish:  python tests/b3394-bot.py <bot papkasi>   (sukut — BOT_PAPKA yoki Kraken_bot)
  Internetsiz — soxta Telegram / Sheets, soxta mijoz 42 va admin 777.
Tekshiriladi: admin (imzodagi ID) /buyurtma — javobda sinov, adminga «🧪 SINOV», 3490: botda YOZUV YO'Q («Buyurtmalarim»
bo'sh), bron yo'q, raqam profilga qo'shilmaydi, mijoz xabari yo'q, Sheets'ga hech narsa; Store / Ombor sotuvi yozilmaydi; chek
xabarida «🧪 SINOV»; admin ro'yxatida sinov belgisi. Mijoz — o'zgarishsiz (sinov yo'q, bron bor, Sheets'ga yoziladi).
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

if not hasattr(bot, '_SINOV_BOSH'):
    print("  · 3394: o'tkazildi — bu bot.py da admin sinov xaridi yo'q (GitHub Kraken bot bilan: BOT_PAPKA=<klon> yoki argument)")
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
_asl_bron_qoy_haqiqiy = bot._bron_qoy
bot._bron_qoy = lambda num, uid, order: bron.append((num, uid, order))
_asl_tel = bot._mijoz_tel_qosh
bot._mijoz_tel_qosh = lambda uid, tel, tur: tel_qosh.append((uid, tel))


def _yubor(uid, num, order, *a, tayyor=None, **k):
    admin_xabar.append(tayyor['matn'])
    return True, None


bot._buyurtma_yubor = _yubor
mijoz_xabar = []
bot._chek_mijozga_xabar = lambda uid, order: mijoz_xabar.append((uid, order))
if hasattr(bot, '_admin_sinov_xabar'):   # 3490: admin sinovi — tugmasiz alohida xabar
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
    for x in (sheet, admin_xabar, bron, tel_qosh, mijoz_xabar):
        x.clear()
    bot._MIJOZ.clear(), bot._MIJOZ_SYNC.clear(), bot._BUYURTMA_KORILGAN.clear(), bot._BUYURTMA_SONI.clear()


def _buy(uid, order):
    r = asyncio.run(bot.buyurtma_endpoint(_So({
        'initData': _imzo(uid), 'num': '261', 'nums': ['261', '262'], 'order': order, 'name': 'Sinov', 'phone': '+998 90 123 45 67',
        'tur': 'emu', 'manzil': 'Toshkent, Chilonzor', 'kurs': 12700})))
    return r.status, json.loads(r.text)


def _b(uid, order):
    return next(x for x in bot._mijoz_ol(uid)['buyurtma'] if x['order'] == order)


def t_admin():
    _yangi()
    kod, j = _buy(ADMIN, 'SIN001')
    assert kod == 200 and j.get('ok') and j.get('sinov') is True, (kod, j)
    assert len(admin_xabar) == 1 and admin_xabar[0].startswith('🧪 <b>SINOV</b>'), admin_xabar
    assert not bot._mijoz_ol(ADMIN)['buyurtma'], bot._mijoz_ol(ADMIN)   # 3490: «Buyurtmalarim»ga yozilmaydi
    assert not bron, bron                      # sinovda tovar band qilinmaydi
    assert not tel_qosh, tel_qosh              # raqam profilga qo'shilmaydi
    assert not mijoz_xabar, mijoz_xabar        # 3490: «buyurtma qabul qilindi / 💳 To'lash» xabari yo'q
    assert not [k for k in bot._MIJOZ_SYNC if k[0] != 't'], bot._MIJOZ_SYNC
    bot._mijoz_sync_yubor()
    assert not sheet, sheet                    # Sheets'ga HECH NARSA
    kod, j = _buy(ADMIN, 'SIN001')             # takror bosilsa — ikkinchi xabar yo'q
    assert kod == 200 and len(admin_xabar) == 1, (kod, j, admin_xabar)


def t_mijoz():
    _yangi()
    kod, j = _buy(MIJOZ, 'MIJ001')
    assert kod == 200 and j.get('ok') and j.get('xabar') is True and 'sinov' not in j, (kod, j)
    assert not admin_xabar[0].startswith('🧪'), admin_xabar
    b = _b(MIJOZ, 'MIJ001')
    assert 'sinov' not in b, b
    assert [x[0] for x in bron] == ['261', '262'], bron
    assert tel_qosh == [(MIJOZ, '+998 90 123 45 67')], tel_qosh
    assert mijoz_xabar == [(MIJOZ, 'MIJ001')], mijoz_xabar
    bot._mijoz_sync_yubor()
    assert [a for a, _ in sheet] == ['buyurtmaYoz'], sheet


def t_sotuv_chek_royxat():
    _yangi()
    b = {'order': 'SIN002', 'ts': time.time(), 'holat': 'tolandi', 'sinov': True, 'jami': 50,
         'tovar': [{'num': '261', 'nom': 'Anker hub', 'narx': 25, 'soni': 1}, {'num': '262', 'nom': 'Anker hub', 'narx': 25, 'soni': 1}]}
    chaq = []
    asl = bot._kk_store if hasattr(bot, '_kk_store') else None
    bot.req.post = lambda *a, **k: chaq.append(a) or (_ for _ in ()).throw(AssertionError('tarmoq'))
    assert bot._sotuv_sheet_yoz(ADMIN, b) is True and not chaq and not sheet, (chaq, sheet)
    assert bot._sotuv_sheet_yoz(ADMIN, dict(b, sinov=False)) is True and not chaq, chaq   # 3490: belgisiz bo'lsa ham — admin
    m = bot._chek_admin_matn(b)
    assert m.startswith('🧪 <b>SINOV</b>') and 'SIN002' in m, m
    assert bot._chek_admin_matn(b, davomi=True).startswith('🧪')
    assert not bot._chek_admin_matn(dict(b, sinov=False)).startswith('🧪')
    d = bot._admin_buyurtma_dict(ADMIN, b)
    assert d['sinov'] is True and bot._admin_buyurtma_dict(MIJOZ, dict(b, sinov=False))['sinov'] is False, d
    del asl


def t_imzosiz_qoriqchi():
    """3490: imzosiz / buzuq imzo — 401, hech narsa yozilmaydi; har yozish nuqtasi adminni o'zi rad etadi."""
    _yangi()
    for d in ({}, {'initData': ''}, {'initData': _imzo(ADMIN)[:-4] + 'abcd'}):
        r = asyncio.run(bot.buyurtma_endpoint(_So(dict(d, num='261', order='IMZ001', name='X', phone='+998901234567', tur='emu',
                                                         manzil='Toshkent', kurs=12700))))
        assert r.status == 401, (d, r.status)
    assert not admin_xabar and not bron and not sheet and not bot._MIJOZ.get(str(ADMIN)), (admin_xabar, bron, sheet)
    if not hasattr(bot, '_admin_mi'):
        return
    assert bot._admin_mi(ADMIN) and bot._admin_mi(str(ADMIN)) and not bot._admin_mi(MIJOZ) and not bot._admin_mi(None)
    asl_b, asl_q = dict(bot._BRON), bot._bron_saqlash
    bot._bron_saqlash = lambda: None
    try:
        bot._BRON.clear()
        _asl_bron_qoy_haqiqiy('500', ADMIN, 'X1')
        _asl_bron_qoy_haqiqiy('501', MIJOZ, 'X2')
        assert '500' not in bot._BRON and bot._BRON['501']['uid'] == MIJOZ, bot._BRON
    finally:
        bot._BRON.clear(), bot._BRON.update(asl_b)
        bot._bron_saqlash = asl_q
    bot._mijoz_buyurtma_yoz(ADMIN, 'X3', '261', [], 'Ism', '+998901234567', {'tur': 'emu'})
    assert not bot._mijoz_ol(ADMIN)['buyurtma'] and not tel_qosh, (bot._mijoz_ol(ADMIN), tel_qosh)


sinov("admin xaridi: javobda sinov, adminga «🧪 SINOV», botda yozuv yo'q, bron / raqam / mijoz xabari yo'q, Sheets'ga hech narsa", t_admin)
sinov("imzosiz / buzuq imzo — 401, hech narsa yozilmaydi; bron / «Buyurtmalarim» admin uchun o'zi rad etadi (3490)", t_imzosiz_qoriqchi)
sinov("mijoz xaridi — o'zgarishsiz (sinov yo'q, bron bor, mijoz xabari bor, Sheets'ga buyurtma yoziladi)", t_mijoz)
sinov("sinov: Store / Ombor sotuvi yozilmaydi, chek xabarida «🧪 SINOV», admin ro'yxatida belgi", t_sotuv_chek_royxat)
print('  %s 3394 bot: %s' % ('✓' if not xato else '✗', '0 xato' if not xato else '%d xato' % xato))
sys.exit(1 if xato else 0)
