# -*- coding: utf-8 -*-
"""tests/b3232_tugma.py — 3232: «Mijozga yozish» (tg://user?id=…) tugmasi rad etilsa xabar tugmasiz yetadi + konkurs oqimi.

Ishga tushirish:  python tests/b3232_tugma.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: requests.post / get almashtirilgan. Telegram — soxta: so'rovda tg://user havolali tugma
bo'lsa haqiqiy Telegram kabi 400 «Bad Request: BUTTON_USER_INVALID» qaytaradi (Render jurnalida 2026-10-22 dan №S3CZVC
buyurtmasida shunday edi), qolganiga — 200 ok. `bot.req` (_TgReq) ning o'zi sinaladi: faqat ichidagi asl `requests` almashadi.
Chiqish: har sinov — «✓ nom» yoki «✗ nom — sabab»; oxirida «N ✓, M ✗», xato bo'lsa — chiqish kodi 1.
"""
import asyncio
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

for k in ('BOT_TOKEN', 'MAIN_CHANNEL_ID', 'WEBHOOK_SECRET', 'POST_CHANNEL_ID', 'POST_KANALLAR', 'TEST_CHANNEL_ID',
          'CHANNEL_ID', 'GURUH_KANAL_ID', 'ESKI_BOT_TOKEN', 'RENDER_URL', 'ADMIN_GURUH', 'SHEET_URL'):
    os.environ.pop(k, None)

import requests


def _tarmoq_yoq(*a, **kw):
    raise AssertionError(f'tarmoq so\'rovi: {a[:1]}')


requests.post = requests.get = _tarmoq_yoq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot  # noqa: E402

NATIJA = [0, 0]


def sinov(nom, shart, sabab=''):
    if shart:
        NATIJA[0] += 1
        print(f'  ✓ {nom}')
    else:
        NATIJA[1] += 1
        print(f'  ✗ {nom} — {sabab}')


class Javob:
    def __init__(self, kod, j):
        self.status_code = kod
        self._j = j
        self.text = json.dumps(j)

    def json(self):
        return self._j


def _markup(kw):
    p = kw.get('json') if isinstance(kw.get('json'), dict) else kw.get('data') or {}
    m = p.get('reply_markup')
    return json.loads(m) if isinstance(m, str) else m


def _tg_user_bor(m):
    return any(str(t.get('url') or '').startswith('tg://user')
               for q in (m or {}).get('inline_keyboard') or [] for t in q if isinstance(t, dict))


class SoxtaTelegram:
    """Asl `requests` o'rniga. Har so'rov: (usul, payload, javob kodi)."""
    def __init__(self):
        self.sorov = []
        self.boshqa_400 = False   # tugmadan boshqa 400 (HTML buzuq) — qayta yuborilmasligi kerak

    def post(self, url, **kw):
        usul = url.rsplit('/', 1)[-1]
        p = dict(kw.get('json') if isinstance(kw.get('json'), dict) else kw.get('data') or {})
        if _tg_user_bor(_markup(kw)):
            kod, j = 400, {'ok': False, 'error_code': 400, 'description': 'Bad Request: BUTTON_USER_INVALID'}
        elif self.boshqa_400:
            kod, j = 400, {'ok': False, 'error_code': 400, 'description': "Bad Request: can't parse entities"}
        else:
            kod, j = 200, {'ok': True, 'result': {'message_id': len(self.sorov) + 1}}
        self.sorov.append((usul, p, kod))
        return Javob(kod, j)

    def get(self, *a, **kw):
        raise AssertionError(f'tarmoq so\'rovi (get): {a[:1]}')

    def __getattr__(self, nom):
        return getattr(requests, nom)


def yangi_tg():
    tg = SoxtaTelegram()
    bot.req._asl = tg
    return tg


UID = 7000000001
KLAVA = bot._buyurtma_klava(UID, 'S3CZVC', 'kutilmoqda', ['1015'])

# ── 1. Klaviaturadan tg://user tugmasini olish ───────────────────────────────
print('1. _tg_user_tugmasiz')
yangi, olindi = bot._tg_user_tugmasiz(KLAVA)
sinov('buyurtma klaviaturasida «Mijozga yozish» bor (sabab shu)', _tg_user_bor(KLAVA))
sinov('1 ta tugma olindi', olindi == 1, olindi)
sinov('tg://user qolmadi', not _tg_user_bor(yangi))
sinov('holat / bron tugmalari joyida', sum(len(q) for q in yangi['inline_keyboard'])
      == sum(len(q) for q in KLAVA['inline_keyboard']) - 1, yangi)
sinov('bo\'sh qator qolmaydi', all(yangi['inline_keyboard']))
sinov('faqat tg://user tugmasi bo\'lsa — markup yo\'q (None)',
      bot._tg_user_tugmasiz({'inline_keyboard': [[{'text': 'x', 'url': 'tg://user?id=1'}]]}) == (None, 1))
sinov('https tugma tegilmaydi', bot._tg_user_tugmasiz({'inline_keyboard': [[{'text': 'x', 'url': 'https://t.me/a'}]]})[1] == 0)
sinov('markup emas (oddiy klaviatura) — tegilmaydi', bot._tg_user_tugmasiz({'keyboard': [[{'text': 'a'}]]})[1] == 0)

# ── 2. Buyurtma xabari adminga (№S3CZVC holati) ──────────────────────────────
print('2. Buyurtma xabari — tugma rad etilsa ham yetadi')
belgi = []
bot._buyurtma_xabar_belgila = lambda uid, order, q: belgi.append((uid, order, q))
tg = yangi_tg()
ok = bot._buyurtma_xabar_yubor(UID, 'S3CZVC', {'matn': '🛒 <b>Buyurtma</b> №S3CZVC', 'bron': ['1015']}, kutish=(0,))
sinov('_buyurtma_xabar_yubor → True', ok is True, tg.sorov)
sinov('2 so\'rov: 400 → tugmasiz 200', [s[2] for s in tg.sorov] == [400, 200], [s[2] for s in tg.sorov])
sinov('ikkinchisi adminga, HTML bilan', tg.sorov[-1][1].get('chat_id') == bot.ADMIN_ID
      and tg.sorov[-1][1].get('parse_mode') == 'HTML')
sinov('ikkinchisida tg://user yo\'q, holat tugmalari bor', not _tg_user_bor(tg.sorov[-1][1].get('reply_markup'))
      and any('callback_data' in t for q in tg.sorov[-1][1]['reply_markup']['inline_keyboard'] for t in q))
sinov('yozuvga «yuborildi» vaqti belgilandi (fon sikli qayta urinmaydi)', belgi and belgi[-1][1] == 'S3CZVC', belgi)

# ── 3. Boshqa yo'llar ────────────────────────────────────────────────────────
print('3. send_msg, multipart, mavzu, boshqa 400')
tg = yangi_tg()
sinov('send_msg (chek eslatma / bekor kabi) → True',
      bot.send_msg(bot.ADMIN_ID, 'x', {'inline_keyboard': [[{'text': 'Mijozga yozish', 'url': f'tg://user?id={UID}'}]]})
      is True)
sinov('faqat shu tugma bo\'lsa — reply_markup umuman yo\'q', 'reply_markup' not in tg.sorov[-1][1], tg.sorov[-1][1])
tg = yangi_tg()
h, _ = bot._kk_tg('sendPhoto', {'chat_id': 1, 'caption': 'c', 'reply_markup': KLAVA}, files={'photo': ('a.jpg', b'x')})
sinov('multipart (files=) — tugmasiz qayta → yuborildi', h == 'yuborildi', tg.sorov)
sinov('multipart: markup JSON matn bo\'lib qoldi', isinstance(tg.sorov[-1][1].get('reply_markup'), str))
tg = yangi_tg()
h, _ = bot._kk_tg('sendMessage', {'chat_id': bot.Joy(-100123, 55), 'text': 'x', 'reply_markup': KLAVA})
sinov('guruh mavzusi: tugmasiz qayta → yuborildi', h == 'yuborildi', tg.sorov)
sinov('guruh mavzusi saqlandi (message_thread_id)', tg.sorov[-1][1].get('message_thread_id') == 55, tg.sorov[-1][1])
tg = yangi_tg()
tg.boshqa_400 = True
h, _ = bot._kk_tg('sendMessage', {'chat_id': 1, 'text': 'x'}, urinish=1)
sinov('boshqa 400 (HTML) — tugma yo\'q, qayta yuborilmaydi', h == 'xato' and len(tg.sorov) == 1, tg.sorov)
tg = yangi_tg()
h, _ = bot._kk_tg('sendMessage', {'chat_id': 1, 'text': 'x', 'reply_markup': {'inline_keyboard': [[
    {'text': 'Ochish', 'url': 'https://t.me/nuqta_tech_mobile'}]]}})
sinov('tg://user yo\'q — bitta so\'rov, o\'zgarishsiz', h == 'yuborildi' and len(tg.sorov) == 1, tg.sorov)

# ── 4. Konkurs oqimi: qatnashish → xabar → admin bildirishnomasi ─────────────
print('4. Konkurs oqimi (soxta Telegram)')
K = {'id': 'K3232', 'prize': '🧪 TEST sovrin', 'status': 'active', 'end_time': '2099-01-01 00:00', 'yashirin': False}
bot.get_konkurs = lambda: K
bot.yetishmagan_kanallar = lambda uid: []
bot._mijoz_tel_qosh = lambda *a, **kw: None
bot.check_init_data = lambda s, max_age=86400: str(UID)
bot._kk_qatnash_yoz = lambda st, q, iz: {'ok': True, 'count': 20, 'shubha': [
    {'sabab': 'qurilma', 'username': '', 'ism': 'Avvalgi', 'user_id': 7000000002}]}
bot._kk_kop_yoz = lambda partiya: {x['qid']: bot._kk_qatnash_yoz(x, None, None) for x in partiya}   # 3322: navbat partiyasi
bot._kk_son_qadam.clear()   # 3324: «har 20» holati — qadam (ilgari _kk_son_yuborilgan)
USER = {'id': UID, 'username': '', 'first_name': 'Sinov'}


class Sorov:
    async def json(self):
        return {'initData': 'user=' + json.dumps({'id': UID, 'language_code': 'uz'}), 'id': 'c1', 'javob': 'olma',
                'qurilma': 'qurilma-12345678', 'iz': 'iz-12345678'}


async def oqim():
    holat = await bot.start_konkurs_flow(UID, USER)
    await bot.handle_phone(UID, '+998901234567', USER)
    bot._kk_captcha[UID] = {'id': 'c1', 'javob': 'olma', 'vaqt': time.time() - 5}
    r = await bot.konkurs_qatnash_endpoint(Sorov())
    t = bot._kk_navbat_ish.get('task')   # 3322: yozish va xabarlar — fon navbatida
    if t:
        await t
    for v in [v for v in asyncio.all_tasks() if v is not asyncio.current_task() and v is not bot._kk_navbat_ish.get('saqla')]:
        await v   # navbat xabarlari (qatnashchiga, adminga)
    return holat, json.loads(r.text)


tg = yangi_tg()
holat, javob = asyncio.run(oqim())
kimga = [(s[1].get('chat_id'), str(s[1].get('text') or '')) for s in tg.sorov]
sinov('/start konkurs → ok, xabar yetdi', holat == ('ok', True), holat)
sinov('qatnashish → ok:true', javob.get('ok') is True, javob)
sinov('qatnashchiga «qatnashyapsiz» keldi', any(c == UID and 'qatnashyapsiz' in t for c, t in kimga), kimga)
sinov('adminga «Konkursda 20 kishi» keldi', any(c == bot.ADMIN_ID and '20 kishi' in t for c, t in kimga), kimga)
sinov('adminga «bir qurilmadan» ogohlantirishi keldi', any(c == bot.ADMIN_ID and 'bir qurilmadan' in t for c, t in kimga))
sinov('birorta ham 400 yo\'q', all(s[2] == 200 for s in tg.sorov), [(s[0], s[2]) for s in tg.sorov])
sinov('hamma so\'rov — sendMessage (kanalga post yo\'q)', all(s[0] == 'sendMessage' for s in tg.sorov),
      [s[0] for s in tg.sorov])

tg = yangi_tg()
h = bot._kk_shaxsiy(UID, 'g\'olib', {'inline_keyboard': [[{'text': 'Admin', 'url': 'tg://user?id=1'}],
                                                       [{'text': 'Kanal', 'url': 'https://t.me/x'}]]})
sinov('konkurs shaxsiy xabari tg://user tugmasi bilan ham yetadi', h == 'yuborildi', tg.sorov)
sinov('… «Kanal» tugmasi qoldi', _markup({'json': tg.sorov[-1][1]}) == {'inline_keyboard': [[{'text': 'Kanal',
                                                                                               'url': 'https://t.me/x'}]]})

print(f'\n{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
