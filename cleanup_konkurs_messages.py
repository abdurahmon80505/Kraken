#!/usr/bin/env python3
"""Xato yuborilgan konkurs xabarlarini o'chirish (bir martalik tozalash skripti).

MUAMMO: bot restart bo'lganda tugagan konkurs qayta yakunlanib, barcha
qatnashuvchilarga TAKRORIY "konkurs yakunlandi / siz g'olib bo'ldingiz"
xabari ketgan. Yuborilgan xabarlarning message_id'lari hech qayerda
saqlanmagan, shuning uchun ularni to'g'ridan-to'g'ri o'chirib bo'lmaydi.

YECHIM: Telegram'da shaxsiy chatdagi message_id'lar ketma-ket o'sadi.
Skript har bir qatnashuvchiga bitta "zond" (probe) xabar yuboradi va uning
id'sini (N) oladi. Bot oxirgi yuborgan xato xabar — N-1 (undan oldingisi
N-2 ...). Shu id'lar deleteMessage bilan o'chiriladi, so'ng zond xabar ham
o'chiriladi (yoki --uzr rejimida uzr xabari sifatida chatda qoldiriladi).

DIQQAT: skript xabar MAZMUNINI tekshira olmaydi — faqat o'rniga qarab
o'chiradi. Agar foydalanuvchi xato xabardan keyin botga o'zi yozgan bo'lsa,
N-1 uning xabari bo'lishi mumkin. Shuning uchun --depth ni oshirmang
(standart 1) va avval --dry-run bilan sinang.

ISHLATISH:
    export BOT_TOKEN=...          # Render'dagi bilan bir xil
    export SHEET_URL=...          # Apps Script web app URL
    python3 cleanup_konkurs_messages.py --konkurs-id 12 --dry-run
    python3 cleanup_konkurs_messages.py --konkurs-id 12
    python3 cleanup_konkurs_messages.py --konkurs-id 12 --uzr

Kanaldagi xato postni o'chirish (bot kanalda admin bo'lishi shart):
    python3 cleanup_konkurs_messages.py --kanal-depth 2 --dry-run
"""
import argparse
import json
import os
import sys
import time
import urllib.parse

import requests as req

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
SHEET_URL = os.environ.get('SHEET_URL', '')
CHANNEL = os.environ.get('CHANNEL_ID', '@Kraken_mobile')
TG_API = f'https://api.telegram.org/bot{BOT_TOKEN}'

PROBE_TEXT = '🧹'
UZR_TEXT = (
    "❗️ Kechirasiz, texnik nosozlik tufayli konkurs natijalari xabari "
    "xato qayta yuborildi. Uni e'tiborsiz qoldiring — haqiqiy natijalar "
    "kanalimizda.\n\n"
    "❗️ Извините, из-за технической ошибки сообщение с итогами конкурса "
    "было отправлено повторно. Пожалуйста, проигнорируйте его — "
    "настоящие результаты в нашем канале."
)


def tg(method, payload, timeout=15):
    try:
        r = req.post(f'{TG_API}/{method}', json=payload, timeout=timeout)
        return r.json()
    except Exception as e:
        return {'ok': False, 'description': str(e)}


def get_konkurs_id():
    """Sheets'dagi oxirgi konkurs id'sini oladi."""
    r = req.get(f"{SHEET_URL}?action=getAllKonkurs&callback=d", timeout=15)
    t = r.text.strip()
    data = json.loads(t[2:-1]) if t.startswith('d(') else r.json()
    arr = data if isinstance(data, list) else data.get('konkurslar', [])
    if not arr:
        return None
    return str(arr[-1].get('id', ''))


def get_participants(konkurs_id):
    r = req.get(
        f"{SHEET_URL}?action=getParticipants&callback=d"
        f"&id={urllib.parse.quote(str(konkurs_id))}", timeout=20)
    t = r.text.strip()
    data = json.loads(t[2:-1]) if t.startswith('d(') else r.json()
    return data.get('participants', [])


def clean_chat(chat_id, depth, dry_run, uzr):
    """Bitta chatdagi oxirgi `depth` ta xabarni o'chiradi.
    Qaytaradi: (holat_matni, o'chirilgan_id_lar)"""
    probe = tg('sendMessage', {
        'chat_id': chat_id,
        'text': UZR_TEXT if uzr else PROBE_TEXT,
        'disable_notification': True,
    })
    if not probe.get('ok'):
        return f"probe xato: {probe.get('description', '')}", []
    mid = probe['result']['message_id']

    targets = [mid - i for i in range(1, depth + 1)]
    if dry_run:
        tg('deleteMessage', {'chat_id': chat_id, 'message_id': mid})
        return f"dry-run (o'chiriladigan id: {targets})", []

    deleted = []
    for t in targets:
        res = tg('deleteMessage', {'chat_id': chat_id, 'message_id': t})
        if res.get('ok'):
            deleted.append(t)
    if not uzr:
        tg('deleteMessage', {'chat_id': chat_id, 'message_id': mid})
    return f"o'chirildi: {len(deleted)}/{depth}", deleted


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--konkurs-id', default='',
                   help="Konkurs id (bo'sh bo'lsa — oxirgisi)")
    p.add_argument('--depth', type=int, default=1,
                   help="Har bir chatda nechta oxirgi xabar o'chirilsin (default 1)")
    p.add_argument('--kanal-depth', type=int, default=0,
                   help="Kanaldagi oxirgi nechta post o'chirilsin (default 0 = tegilmaydi)")
    p.add_argument('--dry-run', action='store_true',
                   help="Hech nima o'chirilmaydi, faqat ko'rsatiladi")
    p.add_argument('--uzr', action='store_true',
                   help="Zond o'rniga uzr xabari yuborilib, chatda qoldiriladi")
    p.add_argument('--faqat', default='',
                   help="Vergul bilan ajratilgan user_id'lar (avval o'zingizda sinash uchun)")
    a = p.parse_args()

    if not BOT_TOKEN:
        sys.exit("BOT_TOKEN yo'q — export BOT_TOKEN=... qiling")

    # ── Kanaldagi xato post ──
    if a.kanal_depth > 0:
        st, _ids = clean_chat(CHANNEL, a.kanal_depth, a.dry_run, uzr=False)
        print(f'KANAL {CHANNEL}: {st}')

    if a.faqat:
        users = [{'user_id': u.strip()} for u in a.faqat.split(',') if u.strip()]
    else:
        if not SHEET_URL:
            sys.exit("SHEET_URL yo'q — export SHEET_URL=... qiling")
        kid = a.konkurs_id or get_konkurs_id()
        if not kid:
            sys.exit('Konkurs topilmadi')
        print(f'Konkurs: {kid}')
        users = get_participants(kid)

    print(f"Qatnashuvchilar: {len(users)} | depth={a.depth} | "
          f"{'DRY-RUN' if a.dry_run else 'REAL'}")
    if not users:
        return

    log, ok_count = [], 0
    for i, u in enumerate(users, 1):
        uid = str(u.get('user_id', '')).strip()
        if not uid:
            continue
        st, ids = clean_chat(uid, a.depth, a.dry_run, a.uzr)
        if ids or a.dry_run:
            ok_count += 1
        log.append({'user_id': uid, 'status': st, 'deleted': ids})
        print(f'  [{i}/{len(users)}] {uid}: {st}')
        time.sleep(0.05)          # Telegram limiti (~30 xabar/sek)

    with open('cleanup_log.json', 'w') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f'\nTayyor: {ok_count}/{len(users)} chat. Log: cleanup_log.json')


if __name__ == '__main__':
    main()
