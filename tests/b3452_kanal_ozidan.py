"""3452: kanal / guruhga hech narsa o'zidan ketmaydi; Owner o'chirgan post qayta chiqmaydi.
Telegram'ga hech narsa yuborilmaydi — hamma yuborish funksiyalari soxta.
python tests/b3452_kanal_ozidan.py → «OK»"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bot  # noqa: E402

yuborildi, xabarlar, yozildi = [], [], []
bot.send_msg = lambda chat, matn, *a, **k: xabarlar.append(matn)
bot.send_rich = lambda *a, **k: (yuborildi.append(('send_rich', a)), (999, ''))[1]
bot.kanal_post = lambda num, *a, **k: (yuborildi.append(('kanal_post', num)), (777, ''))[1]
bot.kanal_yana_keldi = lambda num, *a, **k: (yuborildi.append(('yana', num)), (778, ''))[1]
bot.guruh_yangila_keyin = lambda g: None
bot.olx_albom = lambda *a, **k: (True, '')
bot.kollaj_nusxa_fonda = lambda *a, **k: None
bot._sheets_update = lambda payload: (yozildi.append(payload), True)[1]
bot.req.post = lambda *a, **k: type('R', (), {'json': lambda s: {'ok': True}})()
bot.toplam_postmi = lambda *a, **k: False
bot.elon_kanali = lambda num: 'test kanal'

models = {'1': {'series': 'px'}}
bot._ELON_CACHE['series'] = [{'key': 'px', 'turkum': 'phone'}]
bot._ELON_CACHE['turkumlar'] = [{'key': 'phone', 'labelUz': 'Smartfonlar', 'type': 'phone'}]
bot._ELON_CACHE['models'] = models
bot._ELON_CACHE['time'] = 1


def elon(num, cid='', st='active'):
    e = {'num': num, 'specId': '1', 'nameUz': 'Pixel', 'price': '100', 'status': st, 'images': '', 'channel_message_id': cid}
    bot._ELON_CACHE['by_num'][str(num)] = e
    return e


def tozala():
    yuborildi.clear(); xabarlar.clear(); yozildi.clear()


# 1) №6009 holati: post kanalda yo'q (Owner o'chirgan) → yangi post YO'Q, belgi, xabar
tozala()
bot.kanal_tahrir = lambda num: (False, 'Bad Request: message to edit not found')
e = elon(6009, '91')
r = bot.kanal_sinxron(dict(e), e)
assert r == 'ochirildi', r
assert not yuborildi, f'yangi post ketmasin: {yuborildi}'
assert xabarlar == ["🚫 №6009 kanalda yo'q — qayta yuborilmadi."], xabarlar
assert yozildi and yozildi[-1]['channel_message_id'] == 'ochirildi', yozildi
assert bot.kanaldan_ochirilganmi(bot._ELON_CACHE['by_num']['6009'])
assert bot.kanal_msg_id(bot._ELON_CACHE['by_num']['6009']) is None

# 2) Keyingi o'zgarishda ham qayta chiqmaydi (post yo'q, avto-taklif ham yo'q — hatto waited→active bo'lsa ham)
tozala()
e2 = dict(bot._ELON_CACHE['by_num']['6009'])
r = bot.kanal_sinxron(dict(e2, status='waited'), e2)
assert r == '' and not yuborildi and not xabarlar, (r, yuborildi, xabarlar)

# 3) Navbat (ommaviy / tomchi) belgilini olmaydi
bot.guruh_idsi = lambda e: ''
nav = [x['num'] for x in bot.kanal_navbat('tomchi')]
assert 6009 not in nav, nav

# 4) Boshqa bot posti (begona) — yangi post YO'Q, faqat xabar
tozala()
bot.kanal_tahrir = lambda num: (False, "Bad Request: message can't be edited")
e = elon(6010, '92')
r = bot.kanal_sinxron(dict(e), e)
assert r == 'tahrir' and not yuborildi and 'Yangi post yuborilmadi' in xabarlar[0], (r, yuborildi, xabarlar)
assert not yozildi

# 5) Yangi telefon — avto-post YO'Q, faqat tugmali taklif
tozala()
e = elon(6011, '')
r = bot.kanal_sinxron(None, e)
assert r == 'taklif' and not yuborildi and 'yuborasizmi' in xabarlar[0], (r, yuborildi, xabarlar)

# 6) Owner tugmani bosdi → shunda yuboriladi; «Kerak emas» → yo'q
tozala()
bot.avto_post_tugma(1, 5, 'apost_no:6011')
assert not yuborildi
bot.avto_post_tugma(1, 5, 'apost:6011')
assert yuborildi == [('kanal_post', 6011)], yuborildi

# 7) Tomchi va TashkentComp avto — o'chiq
assert bot.TOMCHI_YOQIQ is False and bot.KANAL_TOMCHI_BOSHI == ''
assert bot.tomchi_qadam(10 ** 10) is False
assert bot.TASHCO_AVTO is False

# 8) Guruh posti kanalda yo'q → yangi post YO'Q, guruh belgisi
tozala()
gk = []
bot.guruh_ol = lambda gid, yangila=False: ({'id': 'g1', 'kanal_message_id': '{"k":"-1","m":50}'}, [elon(7001, '')], models)
bot.guruh_post_qur = lambda *a, **k: '<p>x</p>'
bot._guruh_havolalar = lambda *a, **k: {}
bot._guruh_nomi = lambda *a, **k: 'Case'
bot._429_bilan = lambda fn, *a, **k: (False, 'Bad Request: message to edit not found') if fn is bot.edit_rich else fn(*a, **k)
bot.guruh_kanal_yoz = lambda gid, kd, alohida=None: gk.append(kd)
ok, _ = bot.guruh_tahrir('g1')
assert ok and not yuborildi and gk == [{'o': 1}], (yuborildi, gk)
assert xabarlar == ["🚫 Guruh «Case» kanalda yo'q — qayta yuborilmadi."], xabarlar
assert bot.guruh_kanaldan_ochirilganmi({'kanal_message_id': '{"o":1}'})
assert not bot.guruh_kanaldan_ochirilganmi({'kanal_message_id': '{"k":"-1","m":5}'})
print('OK')
