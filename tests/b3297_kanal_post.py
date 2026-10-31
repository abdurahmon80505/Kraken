# -*- coding: utf-8 -*-
"""tests/b3297_kanal_post.py — 3297 (Owner, №1016): kanal postida ortiqcha qatorlar yo'q.

(a) 🔗 Mos — hamma mos model e'lon nomida bo'lsa qator yo'q; nomda yo'q model bo'lsa — bor.
(b) 📦 «Oxirgi 1 ta» — 1 talik tovarda yo'q; ko'p donadan 1 qolganda (`sotilgan` > 0) — bor. «N dona bor» o'zgarmaydi.
(c) №1016 ga o'xshash e'lon posti — uchala qator ham yo'q (izoh katagi bo'shatilgan).

Ishga tushirish:  python tests/b3297_kanal_post.py   (repo ildizidan)
Tarmoqqa HECH NARSA ketmaydi.
"""
import os
import sys

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


bot._ELON_CACHE['series'] = [
    {'key': 'p7s', 'type': 'smartfon', 'nameUz': 'Pixel 7 Seriyasi'},
    {'key': 'p10s', 'type': 'smartfon', 'nameUz': 'Pixel 10 Seriyasi'},
    {'key': 'ip13s', 'type': 'smartfon', 'nameUz': 'iPhone 13 Seriyasi'},
    {'key': 'case', 'type': 'gilof', 'nameUz': "G'ilof"},
]
MODELS = {
    'p7': {'id': 'p7', 'nameUz': 'Google Pixel 7', 'series': 'p7s'},
    'p7p': {'id': 'p7p', 'nameUz': 'Google Pixel 7 Pro', 'series': 'p7s'},
    'p7a': {'id': 'p7a', 'nameUz': 'Google Pixel 7a', 'series': 'p7s'},
    'p10': {'id': 'p10', 'nameUz': 'Google Pixel 10', 'series': 'p10s'},
    'p10p': {'id': 'p10p', 'nameUz': 'Google Pixel 10 Pro', 'series': 'p10s'},
    'p10px': {'id': 'p10px', 'nameUz': 'Google Pixel 10 Pro XL', 'series': 'p10s'},
    'ip13': {'id': 'ip13', 'nameUz': 'iPhone 13', 'series': 'ip13s'},
    'ip13p': {'id': 'ip13p', 'nameUz': 'iPhone 13 Pro', 'series': 'ip13s'},
    'chp7': {'id': 'chp7', 'nameUz': 'Google Pixel 7 uchun', 'series': 'case', 'mos': 'p7'},
    'chp10': {'id': 'chp10', 'nameUz': 'Google Pixel 10 / 10 Pro uchun', 'series': 'case', 'mos': 'p10, p10p'},
}


def mos(nom, kodlar):
    return bot.mos_line({'mos': kodlar}, MODELS, 'uz', nom)


print('(a) Mos qatori')
sinov('№1016: nom «Google Pixel 7 uchun», mos p7 → yo\'q', mos("Original g'ilof — Google Pixel 7 uchun", 'p7') == '')
sinov('nom «Pixel 7 g\'ilofi» (brendsiz), mos p7 → yo\'q', mos("Pixel 7 g'ilofi", 'p7') == '')
sinov('nom «Pixel 7 Pro g\'ilofi», mos p7 → BOR (Pro ≠ 7)', mos("Pixel 7 Pro g'ilofi", 'p7') == 'Mos: Pixel 7',
      repr(mos("Pixel 7 Pro g'ilofi", 'p7')))
sinov('nom «Pixel 7a g\'ilofi», mos p7 → BOR', mos("Pixel 7a g'ilofi", 'p7') != '')
sinov('nom «Pixel 7 g\'ilofi», mos p7p → BOR', mos("Pixel 7 g'ilofi", 'p7p') != '')
sinov('2 so\'zli model: «iPhone 13 Pro uchun», mos ip13 → BOR', mos('iPhone 13 Pro uchun', 'ip13') != '')
sinov('nom «Pixel 7 g\'ilofi», mos p7, p7p → BOR (nomda yo\'q model)', mos("Pixel 7 g'ilofi", 'p7, p7p') != '')
sinov('№1015: nom «… Pixel 10 Pro uchun», mos p10, p10p → BOR', mos("Original g'ilof — Google Pixel 10 Pro uchun", 'p10, p10p') != '')
sinov('№1005: nom «Pixel 10 / 10 Pro uchun», mos p10, p10p → yo\'q', mos('Google Pixel 10 / 10 Pro uchun', 'p10, p10p') == '')
sinov('nom «Pixel 7, 7 Pro», mos p7, p7p → yo\'q', mos("Pixel 7, 7 Pro g'ilofi", 'p7, p7p') == '')
sinov('nom «Pixel 10 Pro / 10 Pro XL», mos p10 → BOR', mos('Pixel 10 Pro / 10 Pro XL', 'p10') != '')
sinov('seriya kodi nomda deb hisoblanmaydi → BOR', mos("Pixel 7 g'ilofi", 'p7s') != '')
sinov('tur kodi nomda deb hisoblanmaydi → BOR', mos("Telefon g'ilofi", 'phone') != '')
sinov('nom berilmasa — eski xulq (qator bor)', mos('', 'p7') == 'Mos: Pixel 7')
sinov('modelda mos yo\'q → bo\'sh', mos('Pixel 7', '') == '')
sinov('nom katta-kichik harfga sezgir emas', mos("PIXEL 7 G'ILOFI", 'p7') == '')

print('(b) Oxirgi 1 ta')
sinov('soni 1, sotilgan yo\'q (1 talik) → yo\'q', bot.soni_qatori({'soni': '1', 'sotilgan': ''}) == '')
sinov('soni 1, sotilgan 0 → yo\'q', bot.soni_qatori({'soni': 1, 'sotilgan': 0}) == '')
sinov('soni 1, sotilgan ustuni umuman yo\'q → yo\'q', bot.soni_qatori({'soni': '1'}) == '')
sinov('soni 1, sotilgan 4 (ko\'p donadan) → bor', bot.soni_qatori({'soni': '1', 'sotilgan': '4'}) == '📦 Oxirgi 1 ta / Последний')
sinov('soni 1, sotilgan buzuq matn → yo\'q', bot.soni_qatori({'soni': '1', 'sotilgan': 'abc'}) == '')
sinov('soni 5 → «5 dona bor» o\'zgarmadi', bot.soni_qatori({'soni': '5'}) == '📦 5 dona bor / 5 шт.')
sinov('soni 2, sotilgan 3 → «2 dona bor»', bot.soni_qatori({'soni': '2', 'sotilgan': '3'}) == '📦 2 dona bor / 2 шт.')
sinov('soni bo\'sh (telefon) → yo\'q', bot.soni_qatori({'soni': ''}) == '')
sinov('soni 0 → yo\'q', bot.soni_qatori({'soni': '0'}) == '')

print('(c) №1016 ga o\'xshash post')
ELON = {'num': 1016, 'status': 'active', 'specId': 'chp7', 'nameUz': "Original g'ilof — Google Pixel 7 uchun",
        'price': '20', 'condition': 'new', 'color': 'Qora', 'soni': '1', 'sotilgan': '', 'izoh': '', 'images': ''}
for nom, matn in (('build_elon', bot.build_elon(ELON, MODELS)[1]), ('build_rich_html', bot.build_rich_html(ELON, MODELS, premium=False))):
    sinov(f'{nom}: e\'lon nomi bor', 'Pixel 7' in matn, matn)
    sinov(f'{nom}: 🔗 Mos yo\'q', '🔗' not in matn and 'Mos:' not in matn, matn)
    sinov(f'{nom}: 📝 izoh yo\'q', '📝' not in matn, matn)
    sinov(f'{nom}: 📦 Oxirgi yo\'q', 'Oxirgi' not in matn and 'Последний' not in matn, matn)
KOP = dict(ELON, specId='chp7', soni='1', sotilgan='3', nameUz="Pixel 7 Pro g'ilofi", izoh="Chetida tirnalgan")
matn = bot.build_rich_html(KOP, MODELS, premium=False)
sinov('teskari: nomda yo\'q mos, ko\'p donadan 1, izoh bor → uchalasi chiqadi',
      'Mos: Pixel 7' in matn and 'Oxirgi 1 ta' in matn and 'Chetida tirnalgan' in matn, matn)

print(f'\n{NATIJA[0]} o\'tdi, {NATIJA[1]} xato')
sys.exit(1 if NATIJA[1] else 0)
