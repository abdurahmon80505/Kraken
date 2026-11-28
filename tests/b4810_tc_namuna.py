"""4810: tashco_namuna — Jasur matni HTML bilan faqat NUSXA (klon) guruhga; TashComp'ga emas; klon yo'q bo'lsa hech narsa ketmaydi.
python tests/b4810_tc_namuna.py → «OK»"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bot  # noqa: E402

ketdi = []
bot._tg_j = lambda usul, j: (ketdi.append((usul, j)), {'ok': True, 'result': {'message_id': 77}})[1]
bot.tashco_yukla = lambda: True
bot.elon_cache_get = lambda n: ({'num': n}, []) if n == '223' else (None, None)
bot.tashco_bolim = lambda e: 'telefon'
bot.tashco_ish_shakl = lambda num, e, m, k, h: {'matn': '<b>Ekran</b>: 6.8', 'nishon': bot.TASHCO_NISHON}

bot._TC_JOY['h'] = {'klon': {'id': -100123, 'm': {'telefon': 5}}}
mid, kalit, xato = bot.tashco_namuna('223')
assert (mid, kalit, xato) == (77, 'telefon', ''), (mid, kalit, xato)
usul, j = ketdi[0]
assert usul == 'sendMessage' and j['chat_id'] == -100123 and j['message_thread_id'] == 5, ketdi
assert j['parse_mode'] == 'HTML' and j['text'] == '<b>Ekran</b>: 6.8', j
assert all(x[1]['chat_id'] != bot.TASHCO_NISHON for x in ketdi), ketdi

ketdi.clear()
bot._TC_JOY['h'] = {'klon': {}}
assert bot.tashco_namuna('223')[0] is None and not ketdi       # NUSXA sozlanmagan — hech narsa ketmaydi
bot._TC_JOY['h'] = {'klon': {'id': -100123, 'm': {'telefon': 5}}}
assert bot.tashco_namuna('999')[0] is None and not ketdi       # e'lon yo'q
print('OK')
