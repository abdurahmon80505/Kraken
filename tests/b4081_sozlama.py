# -*- coding: utf-8 -*-
"""tests/b4081_sozlama.py — 4081: shart env yo'q bo'lsa adminga ogohlantirish + Owner yo'llari yopilmaganini tekshirish.

Ishga tushirish:  python tests/b4081_sozlama.py   (repo ildizidan). Tarmoqqa hech narsa ketmaydi.
Owner yo'llari: bot buyruqlari (/webhook, /webhook-eski — Telegram kalit bilan yuboradi) va admin sayt (Mini App initData).
"""
import asyncio, hashlib, hmac, json, os, sys, time, urllib.parse

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
for k in ('BOT_TOKEN', 'ESKI_BOT_TOKEN', 'WEBHOOK_SECRET', 'IK_PRIVATE_KEY', 'RENDER_URL', 'MAIN_CHANNEL_ID'):
    os.environ.pop(k, None)
import requests


def _tarmoq_yoq(*a, **kw):
    raise AssertionError('tarmoq so\'rovi')


requests.post = requests.get = _tarmoq_yoq
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot  # noqa: E402

bot.req.post = bot.req.get = _tarmoq_yoq
N = [0, 0]


def sinov(nom, shart, sabab=''):
    N[0 if shart else 1] += 1
    print(f'  {"✓" if shart else "✗"} {nom}' + ('' if shart else f' — {sabab}'))


SIR = 'sinov-' + 'k' * 24
IK = 'sinov-ik-kalit'

# 1. Ogohlantirish
print('1. Ishga tushganda ogohlantirish')
yub = []
bot.send_msg = lambda chat, matn, *a, **kw: yub.append((chat, matn)) or True
for ws, ik, kut in (('', '', 2), (SIR, '', 1), ('', IK, 1), (SIR, IK, 0)):
    bot.WEBHOOK_SECRET, bot.IK_PRIVATE_KEY = ws, ik
    yub.clear()
    r = asyncio.run(bot.sozlama_ogohlantir())
    sinov(f'webhook={"bor" if ws else "yo`q"} ik={"bor" if ik else "yo`q"} → {kut} ta band',
          len(bot.sozlama_yetishmaydi()) == kut and r == bool(kut) and len(yub) == (1 if kut else 0), (r, yub))
    if yub:
        sinov('  xabar — faqat adminga, qiymat yo\'q', yub[0][0] == bot.ADMIN_ID and SIR not in yub[0][1] and IK not in yub[0][1])

# 2. Owner bot buyruqlari: Telegram (kalit bilan) → o'tadi va ishlanadi; begona soxta admin xabari → 403
print('2. Bot buyruqlari (/webhook, /webhook-eski)')
ishlandi = []


async def _hu(d):
    ishlandi.append(d)


bot.handle_update = _hu
if hasattr(bot, '_eski_bot_javob'):
    _asl_eski = bot._eski_bot_javob


class Sorov:
    def __init__(self, kalit, data):
        self.headers = {} if kalit is None else {'X-Telegram-Bot-Api-Secret-Token': kalit}
        self.data = data

    async def json(self):
        return self.data


uid = [1000]


def upd():
    uid[0] += 1
    return {'update_id': uid[0], 'message': {'message_id': 1, 'from': {'id': bot.ADMIN_ID}, 'chat': {'id': bot.ADMIN_ID},
                                            'text': '/start'}}


async def yurgiz(f, rq):
    r = await f(rq)
    await asyncio.sleep(0.05)
    return r.status


bot.WEBHOOK_SECRET = SIR
ishlandi.clear()
sinov('/webhook: Owner xabari (Telegram kaliti bilan) → 200 va ishlanadi',
      asyncio.run(yurgiz(bot.webhook, Sorov(SIR, upd()))) == 200 and len(ishlandi) == 1, ishlandi)
ishlandi.clear()
sinov('/webhook: soxta admin xabari kalitsiz → 403, ishlanmaydi',
      asyncio.run(yurgiz(bot.webhook, Sorov(None, upd()))) == 403 and not ishlandi)
sinov('/webhook: soxta admin xabari noto\'g\'ri kalit → 403, ishlanmaydi',
      asyncio.run(yurgiz(bot.webhook, Sorov('boshqa', upd()))) == 403 and not ishlandi)
sinov('/webhook-eski: kalit bilan → 200', asyncio.run(yurgiz(bot.eski_webhook, Sorov(SIR, []))) == 200)
sinov('/webhook-eski: kalitsiz → 403', asyncio.run(yurgiz(bot.eski_webhook, Sorov(None, []))) == 403)
sinov('setWebhook: secret_token yuboriladi (Telegram kalitni biladi)',
      bot.webhook_sozlama('u', ['message']).get('secret_token') == SIR)

# 3. Admin sayt (Mini App initData) — webhook kalitiga bog'liq emas
print('3. Admin sayt (initData)')
TOK = '123456:sinov-token'
bot.BOT_TOKEN, bot.ESKI_BOT_TOKEN = TOK, ''


def init_data(tok, user_id):
    d = {'auth_date': str(int(time.time())), 'user': json.dumps({'id': user_id}), 'query_id': 'q'}
    check = '\n'.join(f'{k}={v}' for k, v in sorted(d.items()))
    sec = hmac.new(b'WebAppData', tok.encode(), hashlib.sha256).digest()
    d['hash'] = hmac.new(sec, check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(d)


for ws in (SIR, ''):
    bot.WEBHOOK_SECRET = ws
    sinov(f'Owner initData → ADMIN_ID (webhook kaliti {"bor" if ws else "yo`q"})',
          bot.check_init_data(init_data(TOK, bot.ADMIN_ID)) == bot.ADMIN_ID)
sinov('Begona token bilan imzolangan initData → rad', bot.check_init_data(init_data('9:begona', bot.ADMIN_ID)) is None)

print(f'\n{N[0]} ✓, {N[1]} ✗')
sys.exit(1 if N[1] else 0)
