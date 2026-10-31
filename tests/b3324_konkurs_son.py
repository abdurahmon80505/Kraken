# -*- coding: utf-8 -*-
"""tests/b3324_konkurs_son.py — 3324 (Owner): «🎁 Konkursda N kishi» — har 20 chegarasidan o'tganda adminga bir marta.

(a) Partiyada 19 → 21 (20 jadvalda bor, lekin javobi kelmadi) — aynan bitta xabar, «21 kishi»
(b) 40 ikki marta kelsa (takror javob) — bitta xabar; 41, 42 — xabar yo'q
(c) Telegram yubormasa — qadam belgilanmaydi, keyingi qo'shilishda qayta (bir marta)
(d) Bot yonganda: jadvaldagi son — boshlang'ich; o'tilgan chegara qaytarilmaydi, keyingisi aytiladi
(e) Bir martalik «hozir N kishi» — faqat KK_SON_QUVISH_GACHA dan oldin, bir marta; 20 dan kam / aktiv emas — yo'q
(f) Boshlang'ich yo'q (jadval javob bermagan) — birinchi son 41 bo'lsa xabar yo'q, 40 bo'lsa — bor
(g) Navbat orqali: _kk_navbat_xabar — 19, 21 natijasi → bitta xabar; already — sanalmaydi

Ishga tushirish:  python tests/b3324_konkurs_son.py   (repo ildizidan)
Tarmoqqa HECH NARSA ketmaydi.
"""
import asyncio
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


def _fonsiz(self, ex, f, *a):
    fut = self.create_future()
    try:
        fut.set_result(f(*a))
    except Exception as e:
        fut.set_exception(e)
    return fut


asyncio.SelectorEventLoop.run_in_executor = _fonsiz
if hasattr(asyncio, 'ProactorEventLoop'):
    asyncio.ProactorEventLoop.run_in_executor = _fonsiz

ADMIN = bot.ADMIN_ID
YUBORILDI = []      # (chat_id, matn)
YETMAYDI = [False]  # True — Telegram xato qaytaradi


def _send(chat_id, text, keyboard=None):
    if YETMAYDI[0]:
        return False
    YUBORILDI.append((chat_id, text))
    return True


bot.send_msg = _send


def son_xabarlari():
    return [m for c, m in YUBORILDI if c == ADMIN and m.startswith('🎁 Konkursda')]


def toza():
    bot._kk_son_qadam.clear()
    YUBORILDI.clear()
    YETMAYDI[0] = False


async def qator(kid, sonlar):
    for n in sonlar:
        await bot._kk_son_xabari(kid, n)


async def asosiy():
    # (a)
    toza()
    await qator('k1', range(1, 20))
    await qator('k1', [21, 22])
    sinov('(a) 19 → 21 (20 o\'tib ketdi) — aynan bitta xabar', son_xabarlari() == ['🎁 Konkursda 21 kishi'],
          son_xabarlari())

    # (b)
    toza()
    await qator('k1', range(1, 41))
    await qator('k1', [40, 40, 41, 42])
    sinov('(b) 40 ikki marta — bitta xabar, 41/42 — yo\'q',
          son_xabarlari() == ['🎁 Konkursda 20 kishi', '🎁 Konkursda 40 kishi'], son_xabarlari())

    # (c)
    toza()
    await qator('k1', range(1, 40))
    YETMAYDI[0] = True
    await qator('k1', [40])
    YETMAYDI[0] = False
    oldin = list(son_xabarlari())
    await qator('k1', [41, 42, 43])
    sinov('(c) 40 yetmadi — 41 da qayta, faqat bir marta',
          oldin == ['🎁 Konkursda 20 kishi'] and son_xabarlari() == ['🎁 Konkursda 20 kishi', '🎁 Konkursda 41 kishi'],
          son_xabarlari())

    # (d)
    toza()
    bot.KK_SON_QUVISH_GACHA = time.time() - 1
    await bot._kk_son_boshlash({'id': 'k1', 'status': 'active', 'count': 40})
    await qator('k1', [40, 41, 59])
    bosh = list(son_xabarlari())
    await qator('k1', [60, 60, 61])
    sinov('(d) yonganda 40 — qaytarilmaydi; 60 — bir marta',
          bosh == [] and son_xabarlari() == ['🎁 Konkursda 60 kishi'], son_xabarlari())

    # (e)
    toza()
    bot.KK_SON_QUVISH_GACHA = time.time() + 3600
    await bot._kk_son_boshlash({'id': 'k1', 'status': 'active', 'count': 59})
    await bot._kk_son_boshlash({'id': 'k1', 'status': 'active', 'count': 59})
    await qator('k1', [59])
    birinchi = list(son_xabarlari())
    toza()
    await bot._kk_son_boshlash({'id': 'k2', 'status': 'active', 'count': 19})
    await bot._kk_son_boshlash({'id': 'k3', 'status': 'ended', 'count': 80})
    await bot._kk_son_boshlash(None)
    kam = list(son_xabarlari())
    toza()
    bot.KK_SON_QUVISH_GACHA = time.time() - 1
    await bot._kk_son_boshlash({'id': 'k1', 'status': 'active', 'count': 59})
    sinov('(e) bir martalik «59 kishi» — muddat ichida bir marta; 19 / tugagan / muddatdan keyin — yo\'q',
          birinchi == ['🎁 Konkursda 59 kishi'] and kam == [] and son_xabarlari() == [],
          (birinchi, kam, son_xabarlari()))

    # (f)
    toza()
    await qator('k1', [41, 42])
    a = list(son_xabarlari())
    toza()
    await qator('k1', [40])
    sinov("(f) boshlang'ich yo'q: birinchi son 41 — yo'q, 40 — bor",
          a == [] and son_xabarlari() == ['🎁 Konkursda 40 kishi'], (a, son_xabarlari()))

    # (g)
    toza()
    bot._kk_son_qadam['k1'] = 0
    juftlar = [({'user_id': 100 + n, 'konkurs_id': 'k1', 'til': 'uz'}, {'ok': True, 'count': n}) for n in (18, 19, 21)]
    juftlar.append(({'user_id': 999, 'konkurs_id': 'k1', 'til': 'uz'}, {'ok': False, 'msg': 'already', 'count': 40}))
    await bot._kk_navbat_xabar(juftlar)
    sinov('(g) navbat partiyasi 18, 19, 21 (+ already 40) — bitta «21 kishi»',
          son_xabarlari() == ['🎁 Konkursda 21 kishi'], son_xabarlari())


asyncio.run(asosiy())
print(f'  — 3324 konkurs soni: {NATIJA[0]} to\'g\'ri, {NATIJA[1]} xato')
sys.exit(1 if NATIJA[1] else 0)
