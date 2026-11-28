"""4810 / 4815: tashco_namuna — TashComp'ga ketadiganning o'zi faqat NUSXA (klon) guruhga: kanal posti bor — forward, yo'q —
kanal posti yasovchisi (kanal_rich) bilan sendRichMessage; TashComp'ga emas; klon sozlanmagan — hech narsa ketmaydi.
Jasur ishi: kanal posti yo'q e'lon — bot NUSXA mavzusiga kanal_rich post chiqaradi, Jasur o'shani forward qiladi.
python tests/b4810_tc_namuna.py → «OK»"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bot  # noqa: E402

ketdi = []
bot._tg_j = lambda usul, j: (ketdi.append((usul, j)), {'ok': True, 'result': {'message_id': 77}})[1]
bot.tashco_yukla = lambda: True
bot.elon_cache_get = lambda n: ({'num': n}, []) if n in ('223', '224') else (None, None)
bot.tashco_bolim = lambda e: 'telefon'
bot._tc_post_tanla = lambda e, k: ('@nuqta_tech_mobile', 1079) if e['num'] == '223' else None
bot.kanal_rich = lambda e, m, yonalish=None: ('<b>KANAL ' + e['num'] + '</b>', [{'type': 'photo', 'media': 'r'}], None)
boy = []


class R:
    def json(self):
        return {'ok': True, 'result': {'message_id': 88}}


bot.req._asl.post = lambda url, **kw: boy.append((url.rsplit('/', 1)[-1], kw.get('json'))) or R()

bot._TC_JOY['h'] = {'klon': {'id': -100123, 'm': {'telefon': 5}}}
mid, kalit, xato = bot.tashco_namuna('223')
assert (mid, kalit, xato) == (77, 'telefon', ''), (mid, kalit, xato)
assert ketdi == [('forwardMessage', {'chat_id': -100123, 'message_thread_id': 5, 'from_chat_id': '@nuqta_tech_mobile',
                                     'message_id': 1079})], ketdi

ketdi.clear()
assert bot.tashco_namuna('224') == (88, 'telefon', '') and not ketdi   # kanal posti yo'q — kanal_rich bilan
assert boy == [('sendRichMessage', {'chat_id': -100123, 'message_thread_id': 5, 'rich_message': {
    'html': '<b>KANAL 224</b>', 'media': [{'type': 'photo', 'media': 'r'}]}})], boy
boy.clear()
bot._TC_JOY['h'] = {'klon': {}}
assert bot.tashco_namuna('223')[0] is None and not ketdi and not boy   # NUSXA sozlanmagan — hech narsa ketmaydi
bot._TC_JOY['h'] = {'klon': {'id': -100123, 'm': {'telefon': 5}}}
assert bot.tashco_namuna('999')[0] is None and not ketdi       # e'lon yo'q
print('OK')
assert bot.tashco_ish_shakl('224', {'num': '224'}, 'telefon') is None   # 4815: Jasurga matn ishi berilmaydi
h = {'klon': {'id': -100123, 'm': {'telefon': 5}}}
bot._TC_JOY['h'] = h
assert bot._tc_jasurga_post({'num': '224'}, [], 'telefon', h) == (-100123, 88) and boy[-1][0] == 'sendRichMessage'
sh = bot.tashco_ish_shakl('224', {'num': '224'}, 'telefon', (-100123, 88))
assert sh['usul'] == 'f' and (sh['kanal'], sh['kanal_mid']) == (-100123, 88) and sh['nishon'] == bot.TASHCO_NISHON, sh
assert 'matn' not in sh and 'rasmlar' not in sh
n = len(boy)
assert bot._tc_jasurga_post({'num': '224'}, [], 'telefon', {'klon': {}})[0] is None and len(boy) == n
print('OK ish_shakl')
