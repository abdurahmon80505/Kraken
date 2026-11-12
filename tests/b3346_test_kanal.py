# -*- coding: utf-8 -*-
"""tests/b3346_test_kanal.py — 3346 (Owner 2026-11-03): saytdagi «🧪 Test kanal» richagi.

(a) test: true — «Kanalga» (PC, Mobile, Camera), belgilab «Yuborish», guruh «Kanalga» → TEST kanal; jadvalga id yozilmaydi.
(b) test yo'q / false — har bo'lim o'z kanaliga (PC → nuqta_tech_PC, Camera → camera, Mobile → mobile), id yoziladi.
(c) Endpointlar: test: true → javobda test: true va kanal = TEST; test'siz — eski yo'l.

Asosiy kanal ulangan holat (MAIN_CHANNEL_ID = har yo'nalish o'z kanali) taqlid qilinadi. Tarmoqqa HECH NARSA ketmaydi.
Ishga tushirish:  python tests/b3346_test_kanal.py   (repo ildizidan)
"""
import asyncio
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

for k in ('BOT_TOKEN', 'MAIN_CHANNEL_ID', 'WEBHOOK_SECRET', 'POST_CHANNEL_ID', 'POST_KANALLAR', 'TEST_CHANNEL_ID',
          'CHANNEL_ID', 'GURUH_KANAL_ID', 'ESKI_BOT_TOKEN', 'RENDER_URL', 'ADMIN_GURUH', 'SHEET_URL'):
    os.environ.pop(k, None)
os.environ['MAIN_CHANNEL_ID'] = 'mobile=@nuqta_tech_mobile pc=@nuqta_tech_PC camera=@nuqta_tech_camera'

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


TEST = '@Kraken_mobile_test'
MODELS = {'m1': {'id': 'm1', 'nameUz': 'Model'}}
ELONLAR = {
    '101': {'num': 101, 'status': 'active', 'yonalish': 'pc', 'specId': 'm1'},
    '102': {'num': 102, 'status': 'active', 'yonalish': 'camera', 'specId': 'm1'},
    '103': {'num': 103, 'status': 'active', 'yonalish': 'mobile', 'specId': 'm1', 'channel_message_id': 'mobile:a55'},
    '104': {'num': 104, 'status': 'active', 'yonalish': 'mobile', 'specId': 'm1'},
    '105': {'num': 105, 'status': 'active', 'yonalish': 'mobile', 'specId': 'm1', 'guruh': 'g1'},
    '106': {'num': 106, 'status': 'deleted', 'yonalish': 'mobile', 'specId': 'm1'},
    '107': {'num': 107, 'status': 'active', 'yonalish': 'mobile', 'specId': 'm1'},
    '108': {'num': 108, 'status': 'active', 'yonalish': 'olx', 'specId': 'm1'},
}
YUBORILDI, ID_YOZILDI, GURUH_YOZILDI, ADMIN = [], [], [], []

bot.elon_cache_get = lambda n: (ELONLAR.get(str(n)), MODELS)
bot.elon_status = lambda e: (e or {}).get('status', 'active')


def _rich(num, elon, models, chat, message_id=None, kollaj=False, yonalish=None, tugma=None, ovozsiz=False):
    YUBORILDI.append((int(num), chat))
    return 700 + len(YUBORILDI), ''


bot.kanal_rich_yubor = _rich
bot.send_rich = lambda chat, html, *a, **kw: (YUBORILDI.append(('toplam', chat)) or (800 + len(YUBORILDI), ''))
bot.edit_rich = lambda chat, mid, html, *a, **kw: (YUBORILDI.append(('tahrir', chat)) or (True, ''))
bot.kanal_id_yoz = lambda num, mid: ID_YOZILDI.append((num, mid))
bot.guruh_kanal_yoz = lambda *a, **kw: GURUH_YOZILDI.append(a)
bot.send_msg = lambda chat, text, *a, **kw: ADMIN.append(text)
bot.olx_albom = lambda num: None
bot.kollaj_tugma = lambda *a, **kw: None
bot.kollaj_nusxa_fonda = lambda *a, **kw: None
bot._uxla = lambda s: None
bot._fonda = lambda fn, *a: fn(*a)   # fon ishi darhol — natijani tekshirish uchun
bot.check_init_data = lambda s: bot.ADMIN_ID
bot.guruh_ol = lambda gid, yangila=False: (({'id': 'g1', 'nomi': 'Anker', 'rasmlar': ['https://i.ibb.co/x/g1.jpg']}, [ELONLAR['105']], MODELS) if gid == 'g1'
                                           else (None, [], {}))
bot.guruh_post_qur = lambda g, azolar, models, havolalar=None, shablon=None: f'guruh {len(havolalar or {})}'
bot._guruh_nomi = lambda g, azolar, models, lang='uz': 'Anker'
# 3435: rasmsiz guruh posti chiqmaydi — shuning uchun g1 da guruh rasmi bor


def tozala():
    del YUBORILDI[:], ID_YOZILDI[:], GURUH_YOZILDI[:], ADMIN[:]


print('(a) test yoqiq — hammasi TEST kanalga, id yozilmaydi')
for num, nom in ((101, 'PC'), (102, 'Camera'), (104, 'Mobile')):
    tozala()
    mid, xato = bot.kanal_sinov_post(num)
    sinov(f'{nom} №{num} → TEST', mid and YUBORILDI == [(num, TEST)], f'{YUBORILDI} {xato}')
    sinov(f'{nom} №{num} — id yozilmadi', not ID_YOZILDI, str(ID_YOZILDI))
tozala()
sinov("o'chirilgan e'lon test kanalga ham chiqmaydi", bot.kanal_sinov_post(106)[0] is None and not YUBORILDI)

tozala()
mid, xato, yub, otk = bot.kanal_sinov_toplam(['101', '103', '105', '106'])
sinov("to'plam → TEST (kanalda posti bori ham olinadi; 3403: har yo'nalish alohida post)",
      mid and sorted(YUBORILDI) == [(101, TEST), (103, TEST)] and sorted(yub) == [101, 103], f'{YUBORILDI} {yub}')
sinov("to'plam — guruhdagi va o'chirilgan o'tkazildi", sorted(o['num'] for o in otk) == [105, 106], str(otk))
sinov("to'plam — id yozilmadi", not ID_YOZILDI, str(ID_YOZILDI))
tozala()
mid, xato, yub, otk = bot.kanal_sinov_toplam(['101'])
sinov("to'plamda 1 ta telefon/PC — oddiy post, TEST", mid and YUBORILDI == [(101, TEST)], str(YUBORILDI))
tozala()
mid, xato, yub, otk = bot.kanal_sinov_toplam(['104', '107'])
sinov("to'plam: bir yo'nalishdan 2 ta — bitta post, TEST", mid and YUBORILDI == [('toplam', TEST)] and sorted(yub) == [104, 107],
      f'{YUBORILDI} {yub}')
tozala()
mid, xato, yub, otk = bot.kanal_sinov_toplam(['101', '102', '104', '107'])
sinov("to'plam: uch yo'nalish — asl kanalga hech narsa ketmadi", mid and len(YUBORILDI) == 3 and all(c == TEST for _, c in YUBORILDI)
      and sorted(yub) == [101, 102, 104, 107] and not ID_YOZILDI, f'{YUBORILDI} {yub}')
tozala()
mid, xato, yub, otk = bot.kanal_sinov_toplam(['108', '104', '107'])
sinov("to'plam: OLX e'loni o'tkazildi", [o['num'] for o in otk] == [108] and sorted(yub) == [104, 107], f'{otk} {yub}')

tozala()
mid, xato, havola = bot.guruh_sinov_yubor('g1')
sinov('guruh → TEST, Guruhlar ga yozilmadi', mid and YUBORILDI == [('toplam', TEST)] and not GURUH_YOZILDI,
      f'{YUBORILDI} {GURUH_YOZILDI}')
sinov('guruh havolasi — test kanalniki', havola.startswith('https://t.me/Kraken_mobile_test/'), havola)
tozala()
mid, xato, havola = bot.guruh_sinov_yubor('g1', alohida=True)
sinov('guruh + har rang alohida → hammasi TEST', mid and {c for _, c in YUBORILDI} == {TEST}
      and (105, TEST) in YUBORILDI and ('tahrir', TEST) in YUBORILDI, str(YUBORILDI))
sinov("guruh alohida — id / Guruhlar ga yozilmadi", not ID_YOZILDI and not GURUH_YOZILDI)

print("(b) test o'chiq — har bo'lim o'z kanaliga, id yoziladi")
for num, nom, kanal in ((101, 'PC', '@nuqta_tech_PC'), (102, 'Camera', '@nuqta_tech_camera'),
                        (104, 'Mobile', '@nuqta_tech_mobile')):
    tozala()
    mid, xato = bot.kanal_post(num, olx=False)
    sinov(f'{nom} №{num} → {kanal}', mid and YUBORILDI == [(num, kanal)], f'{YUBORILDI} {xato}')
    sinov(f'{nom} №{num} — id yozildi («a»li)', ID_YOZILDI and 'a' in str(ID_YOZILDI[0][1]), str(ID_YOZILDI))
sinov("KANAL_YOLI['sinov'] → TEST, 'elon' pc → PC kanal",
      bot.kanal_tanla('sinov') == TEST and bot.kanal_tanla('elon', 'pc') == '@nuqta_tech_PC')


class So:
    def __init__(self, d):
        self.d = d

    async def json(self):
        return self.d


def chaqir(fn, d):
    return json.loads(asyncio.run(fn(So(dict({'initData': 'x'}, **d)))).text)


print('(c) endpointlar')
tozala()
r = chaqir(bot.kanal_post_endpoint, {'num': '101', 'amal': 'yana', 'yonalish': 'pc', 'test': True})
sinov('/kanal_post test:true (hatto «yana») → TEST, id yo\'q', r.get('ok') and r.get('test') is True and r.get('kanal') == TEST
      and YUBORILDI == [(101, TEST)] and not ID_YOZILDI, f'{r} {YUBORILDI}')
tozala()
r = chaqir(bot.kanal_post_endpoint, {'num': '101', 'yonalish': 'pc', 'test': False})
sinov("/kanal_post test:false → PC kanal, id yozildi", r.get('ok') and not r.get('test')
      and YUBORILDI[0] == (101, '@nuqta_tech_PC') and ID_YOZILDI, f'{r} {YUBORILDI}')
tozala()
r = chaqir(bot.kanal_post_endpoint, {'num': '102', 'test': 'true'})
sinov('/kanal_post test:"true" (satr) — test emas (faqat true)', r.get('ok') and YUBORILDI[0] == (102, '@nuqta_tech_camera'),
      f'{r} {YUBORILDI}')
tozala()
r = chaqir(bot.kanal_toplam_endpoint, {'nums': ['101', '104'], 'test': True})
sinov('/kanal_toplam test:true → TEST', r.get('test') is True and r.get('kanal') == TEST
      and sorted(YUBORILDI) == [(101, TEST), (104, TEST)] and not ID_YOZILDI, f'{r} {YUBORILDI}')
tozala()
r = chaqir(bot.kanal_guruh_endpoint, {'id': 'g1', 'amal': 'yubor', 'test': True})
sinov('/kanal_guruh yubor test:true → TEST, sinov belgisi', r.get('sinov') is True and r.get('test') is True
      and YUBORILDI == [('toplam', TEST)] and not GURUH_YOZILDI, f'{r} {YUBORILDI}')
tozala()
r = chaqir(bot.kanal_guruh_endpoint, {'id': 'g1', 'amal': 'alohida', 'test': True})
sinov('/kanal_guruh alohida test:true — rad (hech narsa ketmaydi)', r.get('ok') is False and not YUBORILDI, str(r))

print(f'\n{NATIJA[0]} o\'tdi, {NATIJA[1]} xato')
sys.exit(1 if NATIJA[1] else 0)
