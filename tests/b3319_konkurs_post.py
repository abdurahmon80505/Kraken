# -*- coding: utf-8 -*-
"""tests/b3319_konkurs_post.py — 3319 (Owner): konkurs anonsi avval admin lichkasiga, kanalga faqat «✅» dan keyin.

(a) /konkursyuborish — kanalga hech narsa, adminga post + «✅» · «↩️», 12 sovg'a
(b) «✅» — kanalga bir marta, tugma «✅ Chiqdi: …», post_havola yoziladi; ikkinchi «✅» / takror buyruq — post yo'q
(c) «↩️», eskirgan «✅», begona bosgan — post yo'q
(d) «✅» paytida jadval qayta tekshiriladi: yashirin / o'zgargan / tugagan / chiqqan — post yo'q; jadval jim — tugma qaytadi
(e) Rasm: matn sig'masa — rasm alohida, matn tugma bilan alohida; albom ketmasa — yarim post yo'q
(f) Sinov konkursi — TEST kanalga; guruhdan buyruq — post baribir lichkaga

Ishga tushirish:  python tests/b3319_konkurs_post.py   (repo ildizidan)
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

import requests

SOROV = []          # (usul, json)
XATO_USUL = set()   # shu usullar — Telegram xatosi


class Javob:
    def __init__(self, usul, ok=True):
        self.status_code = 200 if ok else 400
        self._j = {'ok': ok}
        if ok:
            self._j['result'] = [{'message_id': 700 + len(SOROV)}] if usul == 'sendMediaGroup' else {'message_id': 700 + len(SOROV)}

    def json(self):
        return self._j


def _post(url, json=None, **kw):
    usul = str(url).rsplit('/', 1)[-1]
    SOROV.append((usul, json or {}))
    return Javob(usul, usul not in XATO_USUL)


def _get(url, **kw):
    return Javob('get')


requests.post = _post
requests.get = _get

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
KANAL = bot.kanal_tanla('konkurs')
SOVGA = [f'Sovg\'a {i}' for i in range(1, 13)]
HOLAT = {}
HAVOLA_YOZUV = []
HAVOLA_JAVOB = [{'ok': True}]


def konkurs(**kw):
    return {'id': 'k1', 'prize': 'Nuqta tech konkursi', 'status': 'active', 'yashirin': False, 'post_havola': '',
            'end_time': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(time.time() + 86400)),
            'prizes': '[' + ', '.join(SOVGA) + ']', 'prizePics': 'https://r/1.jpg,https://r/2.jpg,https://r/3.jpg', **kw}


async def _sorov(action, urinish=3, oraliq=5, **params):
    HAVOLA_YOZUV.append((action, params))
    return HAVOLA_JAVOB[0]


bot.get_konkurs = lambda *a, **kw: HOLAT.get('k')
bot._kk_sorov = _sorov


def boshla(**kw):
    bot._konkurs_post.clear()
    bot._konkurs_post_olindi.clear()
    bot._konkurs_chiqdi.clear()
    XATO_USUL.clear()
    HAVOLA_YOZUV.clear()
    HAVOLA_JAVOB[0] = {'ok': True}
    HOLAT['k'] = konkurs(**kw)
    SOROV.clear()


def fon(update):
    async def ish():
        await bot.handle_update(update)
        for t in [x for x in asyncio.all_tasks() if x is not asyncio.current_task()]:
            await t
    asyncio.run(ish())


def buyruq(kim=None):
    kim = kim or ADMIN
    SOROV.clear()
    fon({'update_id': 1, 'message': {'message_id': 9, 'chat': {'id': kim, 'type': 'private'}, 'from': {'id': kim, 'first_name': 'A'},
                                     'text': '/konkursyuborish'}})


def bos(data, kim=None):
    kim = kim or ADMIN
    SOROV.clear()
    fon({'update_id': 2, 'callback_query': {'id': 'q', 'from': {'id': kim}, 'data': data,
                                            'message': {'message_id': 50, 'chat': {'id': kim}, 'text': 't'}}})


def kanalga(kanal=None):
    return [(u, d) for u, d in SOROV if str(d.get('chat_id')) == str(kanal or KANAL)]


def chatga(chat):
    return [(u, d) for u, d in SOROV if str(d.get('chat_id')) == str(chat)]


def tasdiq():
    """Oxirgi tasdiq xabaridagi tugmalar: {'ok': 'kpost_ok:…', 'no': 'kpost_no:…'}."""
    for u, d in reversed(SOROV):
        t = [b for q in (d.get('reply_markup') or {}).get('inline_keyboard', []) for b in q]
        cb = [b.get('callback_data', '') for b in t]
        if any(c.startswith('kpost_ok:') for c in cb):
            return {'ok': cb[0], 'no': cb[1]}
    return {}


def tahrirlar():
    return [d for u, d in SOROV if u == 'editMessageText']


def oxirgi_tahrir():
    return (tahrirlar() or [{}])[-1]


def admin_matn():
    return '\n'.join(str(d.get('text') or d.get('caption') or '') for u, d in chatga(ADMIN))


print('(a) /konkursyuborish — avval lichkaga')
boshla()
buyruq()
sinov('kanalga hech narsa ketmadi', kanalga() == [], kanalga())
alb = [d for u, d in chatga(ADMIN) if u == 'sendMediaGroup']
sinov('adminga 3 rasmli albom keldi', len(alb) == 1 and len(alb[0]['media']) == 3, SOROV)
izoh = alb[0]['media'][0].get('caption', '') if alb else ''
sinov('«🎁 Konkursda qatnashish» tugmasi adminga ham ko\'rindi',
      any('Konkursda qatnashish' in str(d.get('reply_markup')) for u, d in chatga(ADMIN)), SOROV)
t = tasdiq()
sinov('«✅» va «↩️» bor', t.get('ok', '').startswith('kpost_ok:') and t.get('no', '').startswith('kpost_no:'), SOROV)
sinov('«Hali hech narsa ketmadi» deyilgan', 'Hali hech narsa ketmadi' in admin_matn(), admin_matn())
for s in SOVGA:
    sinov(f'matnda: {s}', s in izoh, izoh)
for b in ('🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟', '11. ', '12. '):
    sinov(f'belgi {b.strip()}', b in izoh, izoh)
sinov('tartib: 🔟 Sovg\'a 10 · 11. Sovg\'a 11 · 12. Sovg\'a 12',
      "🔟 Sovg'a 10\n11. Sovg'a 11\n12. Sovg'a 12\n" in izoh, izoh)
sinov('matn rasm izohiga sig\'adi — alohida matn yo\'q', izoh.startswith('🎊'), izoh)

print('(b) «✅» — bir marta')
tok = t['ok']
bos(tok)
kp = kanalga()
sinov('kanalga bitta albom', [u for u, _ in kp].count('sendMediaGroup') == 1, kp)
sinov('kanalga bitta tugma xabari', [u for u, _ in kp].count('sendMessage') == 1, kp)
sinov('kanaldagi matn lichkadagi bilan bir xil', kp and kp[0][1]['media'][0].get('caption') == izoh)
ot = oxirgi_tahrir()
tugma = [b for q in (ot.get('reply_markup') or {}).get('inline_keyboard', []) for b in q]
sinov('tugma «✅ Chiqdi: t.me/…» ga almashdi', len(tugma) == 1 and tugma[0]['text'].startswith('✅ Chiqdi: t.me/'), ot)
sinov('tugma — havola, callback emas', 'url' in (tugma or [{}])[0] and 'callback_data' not in tugma[0], tugma)
sinov('post_havola bir marta yozildi', [a for a, _ in HAVOLA_YOZUV] == ['konkursPostHavola'], HAVOLA_YOZUV)
sinov('yozilgan havola — konkurs id si bilan', HAVOLA_YOZUV and HAVOLA_YOZUV[0][1].get('id') == 'k1', HAVOLA_YOZUV)
sinov('adminga 🔗 xabar', '🔗' in admin_matn(), admin_matn())
bos(tok)
sinov('ikkinchi «✅» — kanalga yo\'q', kanalga() == [], kanalga())
sinov('ikkinchi «✅» — tahrir «Chiqdi» ni buzmadi', tahrirlar() == [], tahrirlar())

print('(b2) Bot qayta yondi / takror buyruq')
boshla(post_havola='https://t.me/nuqta_tech_mobile/5')
buyruq()
sinov('post_havola bor — ko\'rsatilmadi', tasdiq() == {} and 'allaqachon chiqqan' in admin_matn(), SOROV)
sinov('kanalga yo\'q', kanalga() == [])
boshla()
buyruq()
ok = tasdiq()['ok']
HOLAT['k'] = konkurs(post_havola='https://t.me/nuqta_tech_mobile/5')
bos(ok)
sinov('«✅» paytida post_havola paydo bo\'ldi — kanalga yo\'q', kanalga() == [], kanalga())
sinov('xabar: allaqachon chiqqan', 'allaqachon chiqqan' in oxirgi_tahrir().get('text', ''), oxirgi_tahrir())
boshla()
HAVOLA_JAVOB[0] = None
buyruq()
bos(tasdiq()['ok'])
sinov('havola yozilmadi — chiqdi', len(kanalga()) == 2, kanalga())
sinov('⚠️ ogohlantirildi', '⚠️ Post havolasi' in admin_matn(), admin_matn())
buyruq()
sinov('jadvalga yozilmagan bo\'lsa ham — qayta ko\'rsatilmadi', tasdiq() == {} and 'allaqachon chiqqan' in admin_matn(), SOROV)
boshla()
buyruq()
ok = tasdiq()['ok']


async def _ikki():
    await asyncio.gather(bot.konkurs_post_tugma(ADMIN, 50, ok), bot.konkurs_post_tugma(ADMIN, 50, ok))
SOROV.clear()
asyncio.run(_ikki())
sinov('bir vaqtda ikki «✅» — kanalga bir marta', [u for u, _ in kanalga()].count('sendMediaGroup') == 1, kanalga())
sinov('«Chiqdi» oxirida qoldi', 'chiqdi' in oxirgi_tahrir().get('text', ''), oxirgi_tahrir())

print('(c) «↩️», eskirgan, begona')
boshla()
buyruq()
t = tasdiq()
bos(t['no'])
sinov('«↩️» — kanalga yo\'q', kanalga() == [], kanalga())
sinov('«↩️» — xabar almashdi', 'Bekor qilindi' in oxirgi_tahrir().get('text', ''), oxirgi_tahrir())
sinov('«↩️» — tugmalar olindi', oxirgi_tahrir().get('reply_markup') == {'inline_keyboard': []}, oxirgi_tahrir())
sinov('«↩️» — post_havola yozilmadi', HAVOLA_YOZUV == [], HAVOLA_YOZUV)
bos(t['ok'])
sinov('«↩️» dan keyin «✅» — kanalga yo\'q', kanalga() == [], kanalga())
boshla()
buyruq()
eski = tasdiq()['ok']
buyruq()
yangi = tasdiq()['ok']
sinov('yangi ko\'rsatish — yangi token', eski != yangi)
bos(eski)
sinov('eski «✅» — kanalga yo\'q', kanalga() == [], kanalga())
sinov('eski «✅» — «eskirgan», tugmasiz', 'eskirgan' in oxirgi_tahrir().get('text', '')
      and oxirgi_tahrir().get('reply_markup') == {'inline_keyboard': []}, oxirgi_tahrir())
bos(yangi)
sinov('yangi «✅» hali ishlaydi', len(kanalga()) == 2, kanalga())
boshla()
buyruq()
ok = tasdiq()['ok']
bos(ok, kim=777001)
sinov('begona «✅» — kanalga yo\'q', kanalga() == [], kanalga())
sinov('begona «✅» — kutayotgan post saqlandi', bot._konkurs_post.get('token') == ok.split(':')[1])
boshla()
buyruq(kim=777001)
sinov('begona /konkursyuborish — hech narsa', kanalga() == [] and tasdiq() == {}, SOROV)

print('(d) «✅» paytida jadval qayta tekshiriladi')
for nom, ozgar, soz in (('yashirin bo\'ldi', {'yashirin': True}, 'yashirin'),
                        ('tugadi', {'status': 'finished'}, 'aktiv emas'),
                        ('sovg\'a o\'zgardi', {'prizes': '[A, B]'}, 'o\'zgargan'),
                        ('rasm o\'zgardi', {'prizePics': 'https://r/9.jpg'}, 'o\'zgargan'),
                        ('boshqa konkurs', {'id': 'k2'}, 'aktiv emas')):
    boshla()
    buyruq()
    ok = tasdiq()['ok']
    HOLAT['k'] = konkurs(**ozgar)
    bos(ok)
    sinov(f'{nom} — kanalga yo\'q', kanalga() == [], kanalga())
    sinov(f'{nom} — sabab aytildi', soz in oxirgi_tahrir().get('text', ''), oxirgi_tahrir())
boshla()
buyruq()
ok = tasdiq()['ok']
HOLAT['k'] = None
bos(ok)
sinov('jadval jim — kanalga yo\'q', kanalga() == [], kanalga())
sinov('jadval jim — tugmalar qaytdi', tasdiq().get('ok') == ok, oxirgi_tahrir())
HOLAT['k'] = konkurs()
bos(ok)
sinov('jadval tuzaldi — o\'sha «✅» ishladi', len(kanalga()) == 2, kanalga())
boshla()
HOLAT['k'] = konkurs(yashirin=True)
buyruq()
sinov('yashirin konkurs — ko\'rsatilmadi', tasdiq() == {} and 'yashirin' in admin_matn(), SOROV)
boshla()
HOLAT['k'] = None
buyruq()
sinov('konkurs yo\'q — «aktiv konkurs yo\'q»', "aktiv konkurs yo'q" in admin_matn(), admin_matn())

print('(e) Rasm va uzun matn')
UZUN = [f'Juda uzun sovg\'a nomi {i} ' + 'x' * 100 for i in range(12)]
boshla(prizes='[' + ', '.join(UZUN) + ']')
buyruq()
alb = [d for u, d in chatga(ADMIN) if u == 'sendMediaGroup']
sinov('uzun matn: albom izohsiz', alb and not any(m.get('caption') for m in alb[0]['media']), alb)
sinov('uzun matn: matn tugma bilan alohida', any(u == 'sendMessage' and 'Konkursda qatnashish' in str(d.get('reply_markup'))
                                                  and 'Sovg' in d.get('text', '') for u, d in chatga(ADMIN)), SOROV)
boshla(prizes='[' + ', '.join(UZUN) + ']', prizePics='https://r/1.jpg')
buyruq()
foto = [d for u, d in chatga(ADMIN) if u == 'sendPhoto']
sinov('uzun matn, 1 rasm: rasm izohsiz', len(foto) == 1 and not foto[0].get('caption'), foto)
sinov('uzun matn, 1 rasm: matn tugma bilan alohida', any(u == 'sendMessage' and 'Konkursda qatnashish' in str(d.get('reply_markup'))
                                                          for u, d in chatga(ADMIN)), SOROV)
mid = bot.send_konkurs_channel_post('@k', 'm' * 1100, ['https://r/1.jpg'], {})
sinov('uzun matn, 1 rasm: havola matn xabariga', mid == 700 + len(SOROV), mid)
ha = '😀' * 600
sinov('emoji — Telegram birligida sanaladi (600 belgi, 1200 birlik) → rasm alohida', (
    SOROV.clear(), bot.send_konkurs_channel_post('@k', ha, ['https://r/1.jpg'], {}),
    not [d for u, d in SOROV if u == 'sendPhoto'][0].get('caption'))[-1], SOROV)
boshla(prizePics='https://r/1.jpg')
buyruq()
foto = [d for u, d in chatga(ADMIN) if u == 'sendPhoto']
sinov('qisqa matn, 1 rasm: izoh + tugma birga', len(foto) == 1 and foto[0].get('caption') and foto[0].get('reply_markup'), foto)
boshla(prizePics='')
buyruq()
sinov('rasmsiz: matn + tugma', any(u == 'sendMessage' and 'Konkursda qatnashish' in str(d.get('reply_markup')) for u, d in chatga(ADMIN)), SOROV)
boshla()
XATO_USUL.add('sendMediaGroup')
buyruq()
sinov('adminga albom ketmadi — «✅» chiqmadi', tasdiq() == {} and 'ko\'rsatib bo\'lmadi' in admin_matn(), SOROV)
boshla()
buyruq()
ok = tasdiq()['ok']
XATO_USUL.add('sendMediaGroup')
bos(ok)
sinov('kanalga albom ketmadi — tugma ham yo\'q', [u for u, _ in kanalga()] == ['sendMediaGroup'], kanalga())
sinov('«tasdiqlanmadi» deyildi', 'tasdiqlanmadi' in oxirgi_tahrir().get('text', ''), oxirgi_tahrir())
sinov('post_havola yozilmadi', HAVOLA_YOZUV == [], HAVOLA_YOZUV)
SOROV.clear()
XATO_USUL.clear()
bos(ok)
sinov('o\'sha «✅» qayta yubormaydi', kanalga() == [], kanalga())
boshla()
XATO_USUL.add('sendPhoto')
sinov('1 rasm uzun matn: rasm ketmadi — matn ham ketmadi', (
    bot.send_konkurs_channel_post('@k', 'm' * 1100, ['https://r/1.jpg'], {}) is None
    and [u for u, _ in SOROV] == ['sendPhoto']), SOROV)
boshla()
buyruq()
ok = tasdiq()['ok']
_asl = requests.post


def _uzildi(url, json=None, **kw):
    if str((json or {}).get('chat_id')) == str(KANAL):
        raise TimeoutError('t')
    return _asl(url, json=json, **kw)


requests.post = _uzildi
bos(ok)
requests.post = _asl
sinov('kutish tugadi — «tasdiqlanmadi», avto-qayta yo\'q', 'tasdiqlanmadi' in oxirgi_tahrir().get('text', ''), oxirgi_tahrir())
sinov('kutish tugadi — tugma qaytmadi', tasdiq() == {}, SOROV)

print('(f) Sinov konkursi va guruh')
boshla(prize='TEST konkurs')
buyruq()
sinov('sinov: admin lichkasida, kanalga yo\'q', kanalga(bot.TEST_CHANNEL) == [] and kanalga() == [] and tasdiq() != {}, SOROV)
sinov('sinov: tasdiqda TEST kanal ko\'rsatilgan', bot.TEST_CHANNEL in admin_matn(), admin_matn())
bos(tasdiq()['ok'])
sinov('sinov: «✅» — TEST kanalga', len(kanalga(bot.TEST_CHANNEL)) == 2, SOROV)
sinov('sinov: asosiy kanalga yo\'q', kanalga(bot.CHANNEL) == [] or bot.CHANNEL == bot.TEST_CHANNEL, kanalga(bot.CHANNEL))
boshla()
asyncio.run(bot.konkurs_post_korsat(-1001234))
sinov('guruhdan: post lichkaga', tasdiq() != {} and any(u == 'sendMediaGroup' for u, _ in chatga(ADMIN)), SOROV)
sinov('guruhga — faqat «lichkangizga» xabari', [u for u, _ in chatga(-1001234)] == ['sendMessage']
      and 'lichkangizga' in chatga(-1001234)[0][1].get('text', ''), chatga(-1001234))

print('(g) Eski holat ustidan yozilmagan')
sinov("_kk_chiqqan — BUGUN147 to'plami (kanaldan chiqqanlar), yangi funksiya emas", isinstance(bot._kk_chiqqan, set),
      repr(type(bot._kk_chiqqan)))

print(f'\n{NATIJA[0]} o\'tdi, {NATIJA[1]} xato')
sys.exit(1 if NATIJA[1] else 0)
