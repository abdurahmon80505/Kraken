# -*- coding: utf-8 -*-
"""tests/b4805_toliq_nom.py — 4805: to'liq nom bir marta (Elonlar `toliqNom` = 1).

Belgili e'londa kanal posti, inline / rich post va OLX sarlavhasi — saqlangan nomning o'zi (xotira / rang qayta qo'shilmaydi,
saytdagi bilan bir xil); belgisiz eski e'lon — avvalgidek yig'iladi.

Ishga tushirish:  python tests/b4805_toliq_nom.py   (repo ildizidan)
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


bot._ELON_CACHE['series'] = [{'key': 'p9s', 'type': 'smartfon', 'nameUz': 'Pixel 9 Seriyasi'}]
MODELS = {'p9p': {'id': 'p9p', 'nameUz': 'Google Pixel 9 Pro', 'series': 'p9s'}}
TOLIQ = {'num': 901, 'specId': 'p9p', 'nameUz': 'Google Pixel 9 Pro (128GB) Obsidian Black (Qora) Toza', 'toliqNom': '1',
         'storage': '128GB', 'color': 'Obsidian Black (Qora)', 'price': '520', 'condition': 'used', 'cycle': '90', 'status': 'active'}
ESKI = dict(TOLIQ, num=902, nameUz='Google Pixel 9 Pro', toliqNom='')
NOM = 'Google Pixel 9 Pro (128GB) Obsidian Black (Qora) Toza'

sinov('toliq_nommi: belgi 1 va nom bor — ha; belgisiz yoki nomsiz — yo\'q',
      bot.toliq_nommi(TOLIQ) and not bot.toliq_nommi(ESKI) and not bot.toliq_nommi(dict(TOLIQ, nameUz='', name='')))

_, matn, _ = bot.build_elon(TOLIQ, MODELS)
birinchi = matn.split('\n')[0]
sinov('kanal posti (build_elon): sarlavha — saqlangan nom, rang / xotira ikki marta emas',
      NOM in birinchi and birinchi.count('128GB') == 1 and birinchi.count('Obsidian Black') == 1, birinchi)
_, matn, _ = bot.build_elon(ESKI, MODELS)
birinchi = matn.split('\n')[0]
sinov('kanal posti: belgisiz eski e\'lon — avvalgidek yig\'iladi', 'Google Pixel 9 Pro (128GB) Obsidian Black' in birinchi, birinchi)

h = str(bot.build_rich_html(TOLIQ, MODELS, premium=False))
sinov('rich post (build_rich_html): sarlavha — saqlangan nom, ortiqcha rang yo\'q', NOM in h and h.count('Obsidian Black') == 1, h[:300])

olx_nom, _ = bot.build_olx_text(TOLIQ, MODELS)
sinov('OLX sarlavhasi: saqlangan nom, qavs qayta qo\'shilmaydi', olx_nom == NOM, olx_nom)

print(f'\n{NATIJA[0]} tekshiruv, {NATIJA[1]} xato')
sys.exit(1 if NATIJA[1] else 0)
