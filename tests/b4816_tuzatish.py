"""4816: bot tuzatishlari — /publish spam to'sig'i, /konkurs_started tanaffusi, buyruqlar aniq, xato logi.
python tests/b4816_tuzatish.py → «OK»"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bot  # noqa: E402


# ── /publish to'sig'i: bir raqam 60 s da 1, jami 10 daqiqada 10 ──
bot._PUBLISH_IZ.update(num={}, hammasi=[])
t = 1_000_000.0
assert bot._publish_cheklov('5', t) == ''
assert bot._publish_cheklov('5', t + 30) != ''          # shu raqam — 60 s ichida yo'q
assert bot._publish_cheklov('5', t + 61) == ''          # 60 s dan keyin — bor
for i in range(8):
    assert bot._publish_cheklov(str(100 + i), t + 62) == '', i
assert bot._publish_cheklov('999', t + 63) != ''        # 10 ta to'ldi
assert bot._publish_cheklov('999', t + 700) == ''       # 10 daqiqadan keyin — yana


class So:
    def __init__(self, d):
        self.d = d
        self.headers = {}

    async def json(self):
        return self.d


yuborildi = []
bot.preview_elon_to_admin = lambda num, joy: yuborildi.append(num)
bot.admin_joy = lambda k: None


async def chaqir(f, d):
    r = await f(So(d))
    await asyncio.sleep(0.05)
    return r.status, json.loads(r.text)


async def publish_sinov():
    bot._PUBLISH_IZ.update(num={}, hammasi=[])
    s, j = await chaqir(bot.publish_endpoint, {'num': '248'})
    assert s == 200 and j == {'ok': True}, (s, j)
    s, j = await chaqir(bot.publish_endpoint, {'num': '248'})
    assert s == 429 and 'error' in j, (s, j)
    s, j = await chaqir(bot.publish_endpoint, {'num': '1&action=x'})
    assert s == 400, (s, j)
    # admin initData — cheklovsiz
    asl = bot.check_init_data
    bot.check_init_data = lambda x, *a, **k: bot.ADMIN_ID if x == 'ADMIN' else None
    try:
        s, j = await chaqir(bot.publish_endpoint, {'num': '248', 'initData': 'ADMIN'})
        assert s == 200, (s, j)
    finally:
        bot.check_init_data = asl
    assert yuborildi.count('248') == 2, yuborildi


async def konkurs_sinov():
    chaqiruv = []
    bot.get_konkurs = lambda: chaqiruv.append(1) or None
    bot.konkurs_taymer_qoy = lambda k: False
    bot._KS_OXIRGI[0] = 0.0
    s, j = await chaqir(bot.konkurs_started_endpoint, {})
    assert s == 200 and j.get('ok') and not j.get('kech'), (s, j)
    s, j = await chaqir(bot.konkurs_started_endpoint, {})
    assert s == 200 and j.get('kech'), (s, j)           # 15 s ichida — jadval qayta o'qilmaydi
    assert len(chaqiruv) == 1, chaqiruv


asyncio.run(publish_sinov())
asyncio.run(konkurs_sinov())

# ── buyruqlar: birinchi so'z aniq ──
kod = open(bot.__file__, encoding='utf-8').read()
for b in ("text.startswith('/stat')", "text.startswith('/tozala')", "text.startswith('/yubor')",
          "text.startswith('/elon')", "text.startswith('/demo')"):
    assert b not in kod, b
assert "buyruq0 == '/stat' and adm" in kod and "buyruq0 in ('/tozala', '/tozala_test') and adm" in kod


# ── send_msg: Telegram rad etsa — sababi logda ──
class Javob:
    status_code = 400

    def json(self):
        return {'ok': False, 'description': 'Bad Request: chat not found'}


yozuv = []


class H(logging.Handler):
    def emit(self, rec):
        yozuv.append(rec.getMessage())


bot.logger.addHandler(H())
asl_post = bot.req.post
bot.req.post = lambda *a, **k: Javob()
try:
    assert bot.send_msg(1, 'x') is False
finally:
    bot.req.post = asl_post
assert any('chat not found' in y for y in yozuv), yozuv
print('OK')
