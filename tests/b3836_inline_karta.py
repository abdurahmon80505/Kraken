# -*- coding: utf-8 -*-
"""tests/b3836_inline_karta.py — 3836 (2026-11-19): inline «!#331» — faqat karta (rich yo'q).

Ishga tushirish:  python tests/b3836_inline_karta.py <bot papkasi>   (sukut — BOT_PAPKA yoki Kraken_bot)
  Internetsiz — soxta answerInlineQuery. Nega: Madina userbot'i (GramJS) rich_message natijani o'qiy olmaydi.
Tekshiriladi: «!#331» — natijada rich_message yo'q, message_text bor; «#331» — o'zgarmagan (rich, rasm keshda bo'lsa).
"""
import os
import sys
import asyncio

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ILDIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KB = os.path.join(ILDIZ, 'Kraken_bot')
sys.path.insert(0, os.path.abspath((sys.argv[1] if len(sys.argv) > 1 else '') or os.environ.get('BOT_PAPKA')
                                   or (_KB if os.path.isdir(_KB) else ILDIZ)))
for _k, _v in {'BOT_TOKEN': '123456:SINOV', 'BOT_USERNAME': 'sinov_bot', 'SHEET_URL': '', 'API_KEY': '',
               'CHANNEL_ID': '@sinov_kanal', 'ADMIN_ID': '777'}.items():
    os.environ[_k] = _v
for _k in ('ADMIN_GURUH', 'RENDER_INSTANCE_ID', 'ESKI_BOT_TOKEN'):
    os.environ.pop(_k, None)

import bot  # noqa: E402

ok = xato = 0


def tek(shart, nom):
    global ok, xato
    if shart:
        ok += 1
        print('  ✓', nom)
    else:
        xato += 1
        print('  ✗', nom)


ELON = {'num': 331, 'specId': '', 'status': 'active', 'price': '500', 'condition': 'used', 'storage': '128GB',
        'color': 'Black', 'images': 'https://ik.imagekit.io/x/a.jpg'}
yuborildi = []


class _J:
    def json(self):
        return {'ok': True}


def soxta_post(url, json=None, **kw):
    yuborildi.append(json)
    return _J()


async def soxta_blok(f, *a, **kw):
    return f(*a, **kw)

bot.req.post = soxta_post
bot.blok = soxta_blok
bot.elon_cache_hammasi = lambda: ({'331': ELON}, {})
bot.inline_topish = lambda q, by, m: [ELON] if q.strip() in ('#331', '331') else []
bot.rasm_navbatga = lambda urls: None
bot._fid_jadvaldan = lambda e: None
for k in bot.inline_kalitlari(ELON):
    bot._RASM_FID[k] = 'FID'


def natija(q):
    yuborildi.clear()
    asyncio.run(bot.inline_javob({'id': '1', 'query': q, 'offset': ''}))
    return (yuborildi[0] or {}).get('results', []) if yuborildi else []


n1 = natija('!#331')
tek(len(n1) == 1, '«!#331» — 1 natija')
tek(n1 and 'rich_message' not in n1[0]['input_message_content'], '«!#331» — rich_message yo\'q')
tek(n1 and 'message_text' in n1[0]['input_message_content'], '«!#331» — karta matni bor')
n2 = natija('#331')
tek(len(n2) == 1, '«#331» — 1 natija')
tek(n2 and 'rich_message' in n2[0]['input_message_content'], '«#331» — rich (o\'zgarmagan)')
tek(natija('! #331') and True, '«! #331» — bo\'shliq bilan ham topiladi')
print(f'\n  {ok} ✓, {xato} ✗')
sys.exit(1 if xato else 0)
