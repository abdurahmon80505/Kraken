# -*- coding: utf-8 -*-
"""tests/b3273_kanal_tugmasiz.py — 3273: «📣 №… kanalga chiqdi» admin xabarida «🗑 Postni o'chirish» tugmasi yo'q.

Ishga tushirish:  python tests/b3273_kanal_tugmasiz.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post almashtirilgan (so'rovlar SOROV ga yoziladi).
Eski xabardagi `pochir:` tugmasi — «Ha / Yo'q» tasdiq bilan ishlayveradi.
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
SOROV = []


def sinov(nom, shart, sabab=''):
    if shart:
        NATIJA[0] += 1
        print(f'  ✓ {nom}')
    else:
        NATIJA[1] += 1
        print(f'  ✗ {nom} — {sabab}')


class Javob:
    status_code = 200
    text = '{"ok": true, "result": {"message_id": 1}}'

    def json(self):
        return {'ok': True, 'result': {'message_id': 1}}


def _post(url, **kw):
    SOROV.append((url.rsplit('/', 1)[-1], kw.get('json') or kw.get('data')))
    return Javob()


bot.req.post = _post


def cb(kb):
    return [b.get('callback_data') for q in (kb or {}).get('inline_keyboard', []) for b in q]


print('3273: kanalga chiqdi — tugmasiz')

# kollaj o'chiq (jonli holat): yakka e'lon ham, to'plam ham — tugma umuman yo'q
bot.KOLLAJ_YOQIQ = False
sinov("kollaj_tugma (kollaj o'chiq) — None", bot.kollaj_tugma(55) is None, repr(bot.kollaj_tugma(55)))
SOROV.clear()
bot.send_msg(1058186533, "📣 №301 kanalga chiqdi (saytdan, id 55) — @kanal", bot.kollaj_tugma(55))
sinov("«kanalga chiqdi» xabari — reply_markup yo'q (bir qator matn)",
      SOROV and SOROV[-1][0] == 'sendMessage' and 'reply_markup' not in SOROV[-1][1], repr(SOROV))
sinov("matnda «Postni o'chirish» yo'q", SOROV and "o'chirish" not in str(SOROV[-1][1]))

# kollaj yoqilsa — faqat kollaj / slayd tugmasi, o'chirish yo'q
bot.KOLLAJ_YOQIQ = True
sinov("kollaj yoqiq — faqat «🖼 Kollajga o'tkazish»", cb(bot.kollaj_tugma(55)) == ['kollaj:55'], repr(bot.kollaj_tugma(55)))
sinov("kollaj yoqiq, kollajda — faqat «🎞 Slaydga qaytarish»", cb(bot.kollaj_tugma(55, True)) == ['slayd:55'])
bot.KOLLAJ_YOQIQ = False

# eski xabar: pochir: → Ha / Yo'q; Yo'q → tugmalar olinadi (bo'sh klaviatura, xato yo'q)
SOROV.clear()
bot.post_ochir_tugma(1058186533, 7, 'pochir:55')
sinov("eski «🗑 Postni o'chirish» → «Ha / Yo'q» tasdiq",
      SOROV and SOROV[-1][0] == 'editMessageReplyMarkup' and cb(SOROV[-1][1]['reply_markup']) == ['pochir_ha:55', 'pochir_yoq:55'],
      repr(SOROV))
bot.kollajmi = lambda mid: False
SOROV.clear()
bot.post_ochir_tugma(1058186533, 7, 'pochir_yoq:55')
sinov("«Yo'q» → bo'sh klaviatura (o'chirish tugmasi qaytmaydi)",
      SOROV and SOROV[-1][0] == 'editMessageReplyMarkup' and SOROV[-1][1]['reply_markup'] == {"inline_keyboard": []},
      repr(SOROV))

# boshqa joyda «🗑 Postni o'chirish» tugmasi yasalmaydi
manba = open(bot.__file__, encoding='utf-8').read()
sinov("bot.py da «🗑 Postni o'chirish» tugmasi yasalmaydi", '"text": "🗑 Postni o\'chirish"' not in manba)

print(f'{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
