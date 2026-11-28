# -*- coding: utf-8 -*-
"""tests/b4513_inline_kanal.py — 4513 (2026-11-28): «!#331» (Madina) — kanal posti ko‘rinishi, qisqa karta emas.

Ishga tushirish:  python tests/b4513_inline_kanal.py <bot papkasi>   (sukut — BOT_PAPKA yoki Kraken_bot)
  Internetsiz — soxta answerInlineQuery. Nega: Madina userbot'i (GramJS) rich_message natijani o'qiy olmaydi.
Tekshiriladi: «!#331» — kanal posti matni (to‘liq), xarakteristika iqtibosda, tugmalar; rich_message yo‘q.
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
MODEL = {'specUz': 'Ekran: 6.1"\nXotira: 128GB', 'specRu': 'Экран: 6.1"\nПамять: 128GB'}
ELON['specId'] = 'm1'
bot.req.post = soxta_post
bot.blok = soxta_blok
bot.elon_cache_hammasi = lambda: ({'331': ELON}, {'m1': MODEL})
bot.inline_topish = lambda q, by, m: [ELON] if q.strip() in ('#331', '331') else []
bot.rasm_navbatga = lambda urls: None
bot._fid_jadvaldan = lambda e: None


def natija(q):
    yuborildi.clear()
    asyncio.run(bot.inline_javob({'id': '1', 'query': q, 'offset': ''}))
    return (yuborildi[0] or {}).get('results', []) if yuborildi else []


n = natija('!#331')
tek(len(n) == 1, '«!#331» — 1 natija')
r = n[0] if n else {}
imc = r.get('input_message_content', {})
m = imc.get('message_text', '')
tek('rich_message' not in imc, 'rich_message yo\'q (GramJS o\'qiy oladi)')
tek("E'lon №" not in m, 'eski qisqa karta matni emas')
tek('Holati' in m and 'Состояние' in m and 'Narxi / Цена' in m, 'kanal posti matni: holati (2 tilda), narx')
tek('#331' in m and 'Texnik xarakteristika' in m, 'kanal posti matni: teg, xarakteristika sarlavhasi')
tek('<blockquote expandable>' in m and 'Ekran' in m and m.count('<blockquote') == m.count('</blockquote>'),
    'xarakteristika — yig\'ilgan iqtibos')
tek('\x01' not in m and '\x02' not in m and '<tg-' not in m and '<p>' not in m and '<details' not in m,
    'rich teglari qolmagan')
tek(imc.get('parse_mode') == 'HTML' and (imc.get('link_preview_options') or {}).get('show_above_text'),
    'rasm — matn tepasida (katta)')
kb = (r.get('reply_markup') or {}).get('inline_keyboard') or []
matnlar = [b['text'] for q in kb for b in q]
tek(any('Sotib olish' in t for t in matnlar) and any("Boshqa e'lonlar" in t for t in matnlar),
    'tugmalar — kanal postidagidek')
tek(all(b['url'].startswith('https://t.me/') for q in kb for b in q), 'tugma havolalari')
# kanal postidagi har matn qatori natijada bor (shablon bir xil — qaytib qolmasin)
kanal = bot._tc_tg_html(bot.build_rich_html(ELON, {'m1': MODEL}, premium=False), chegara=4096)
toza = lambda s: [q.strip() for q in bot._html.unescape(bot.re.sub(r'<[^>]+>', '', s)).split('\n')
                  if q.strip() and not q.startswith('🔗')]
yoq = [q for q in toza(kanal) if q not in toza(m)]
tek(not yoq, 'kanal posti matnining hamma qatori bor' + (f' (yo\'q: {yoq[:2]})' if yoq else ''))
tek(len(m) <= 4096, 'matn ≤ 4096')
print(f'\n  {ok} ✓, {xato} ✗')
sys.exit(1 if xato else 0)
