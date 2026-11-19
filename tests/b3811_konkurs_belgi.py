# -*- coding: utf-8 -*-
"""tests/b3811_konkurs_belgi.py — 3811 (2026-11-19): konkurs yakun tugmalariga `konkurs-<YYYYMMDD>-<tugma>` belgisi.

Ishga tushirish:  python tests/b3811_konkurs_belgi.py <bot papkasi>   (sukut — BOT_PAPKA yoki ildiz)
Internetsiz. Tekshiriladi: sana end_time dan (Toshkent), yutqazganlar tugmasi `?p=`, kanal tugmasi `?startapp=`,
belgisiz chaqiriq — oldingidek; belgi Telegram startapp qoidasiga mos (A-Z a-z 0-9 _ -, ≤ 30).
"""
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ILDIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KB = os.path.join(ILDIZ, 'Kraken_bot')
sys.path.insert(0, os.path.abspath((sys.argv[1] if len(sys.argv) > 1 else '') or os.environ.get('BOT_PAPKA')
                                   or (_KB if os.path.isdir(_KB) else ILDIZ)))
import bot  # noqa: E402

xato = 0


def teng(nom, bor, kut):
    global xato
    if bor == kut:
        print('  ✓ ' + nom)
    else:
        xato += 1
        print('  ✗ %s — kutilgan %r, keldi %r' % (nom, kut, bor))


# 1) Sana — end_time dan, Toshkent kuni (UTC 19:30 → ertasi kun Toshkentda)
teng('naive end_time (Toshkent)', bot._kk_belgi({'end_time': '2026-12-15 19:50'}, 'maglub'), 'konkurs-20261215-maglub')
teng('ISO Z, Toshkentda ertasi kun', bot._kk_belgi({'end_time': '2026-12-15T19:30:00.000Z'}, 'kanal'), 'konkurs-20261216-kanal')
b = bot._kk_belgi({}, 'kanal')
teng('end_time yo\'q — bugungi sana, xato yo\'q', bool(re.fullmatch(r'konkurs-\d{8}-kanal', b)), True)
teng('startapp qoidasi, ≤ 30', bool(re.fullmatch(r'[A-Za-z0-9_-]{1,30}', bot._kk_belgi({'end_time': '2026-12-15 19:50'}, 'maglub'))), True)

# 2) Tugmalar
_, mk = bot._kk_maglub_xabari('Sovrin', 'g', 'konkurs-20261215-maglub')
teng('yutqazganlar tugmasi — web_app ?p=', mk['inline_keyboard'][0][0]['web_app']['url'], bot.SAYT_URL + '?p=konkurs-20261215-maglub')
_, mk = bot._kk_maglub_xabari('Sovrin', 'g')
teng('belgisiz — oldingidek', mk['inline_keyboard'][0][0]['web_app']['url'], bot.SAYT_URL)
_, mk = bot._kk_kanal_xabari('Sovrin', 'g', 'konkurs-20261215-kanal')
teng('kanal tugmasi — startapp', mk['inline_keyboard'][0][0]['url'],
     'https://t.me/%s?startapp=konkurs-20261215-kanal' % bot.BOT_USERNAME)
_, mk = bot._kk_kanal_xabari('Sovrin', 'g')
teng('kanal belgisiz — oldingidek', mk['inline_keyboard'][0][0]['url'], 'https://t.me/%s?startapp' % bot.BOT_USERNAME)

print('  — 3811 konkurs belgisi: %s' % ('%d XATO' % xato if xato else "hammasi to'g'ri"))
sys.exit(1 if xato else 0)
