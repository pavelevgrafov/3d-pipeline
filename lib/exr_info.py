"""Что на самом деле лежит в EXR: размер и список пассов, прямо из заголовка.

Нужно по двум причинам.

Во-первых, это проверка, а не обещание: «в файле есть глубина и cryptomatte»
должно быть видно списком. Blender умеет молча записать однослойный RGBA вместо
multilayer, и заметить подмену можно только так.

Во-вторых, `bpy.data.images.load()` не декодирует файл сразу, и `image.size`
до первого обращения к пикселям равен (0, 0) — размер приходится брать отсюда.

Чистый Python, без bpy и без сторонних модулей: запускается обычным python3.

    python3 lib/exr_info.py renders/hero.exr
"""
import struct
import sys

_MAGIC = b"\x76\x2f\x31\x01"
_HEADER_LIMIT = 4 << 20        # заголовки многочастного EXR лежат в начале файла


def _read_headers(path):
    with open(path, "rb") as fh:
        d = fh.read(_HEADER_LIMIT)
    if d[:4] != _MAGIC:
        raise ValueError(f"{path}: не EXR")
    multipart = bool(struct.unpack_from("<i", d, 4)[0] & 0x1000)
    p, headers = 8, []
    while True:
        attrs = {}
        while True:
            e = d.index(b"\x00", p)
            name = d[p:e].decode()
            p = e + 1
            if not name:
                break
            e = d.index(b"\x00", p)          # тип атрибута — пропускаем
            p = e + 1
            (sz,) = struct.unpack_from("<i", d, p)
            p += 4
            attrs[name] = d[p:p + sz]
            p += sz
        headers.append(attrs)
        # Часть заканчивается пустым именем; список частей — вторым пустым байтом.
        if not multipart or p >= len(d) or d[p] == 0:
            break
    return headers


def _channels(blob):
    out, q = [], 0
    while q < len(blob) - 1:
        e = blob.index(b"\x00", q)
        name = blob[q:e].decode()
        q = e + 1
        if not name:
            break
        q += 16                 # pixelType(4) + pLinear(1) + reserved(3) + sampling(8)
        out.append(name)
    return out


def size(path):
    """(ширина, высота) из dataWindow первой части."""
    x0, y0, x1, y1 = struct.unpack_from("<4i", _read_headers(path)[0]["dataWindow"], 0)
    return x1 - x0 + 1, y1 - y0 + 1


def passes(path):
    """[(имя пасса, [каналы])] по всем частям файла."""
    out = []
    for h in _read_headers(path):
        name = h.get("name", b"").rstrip(b"\x00").decode() or "(единственный слой)"
        out.append((name, _channels(h.get("channels", b""))))
    return out


def report(path):
    ps = passes(path)
    w, h = size(path)
    lines = [f"{path}", f"  {w}×{h}, пассов: {len(ps)}"]
    for name, chans in ps:
        lines.append(f"  {name:34s} {len(chans)}  "
                     f"{','.join(c.rsplit('.', 1)[-1] for c in chans)}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("укажите EXR-файл: python3 lib/exr_info.py renders/hero.exr")
    for f in sys.argv[1:]:
        print(report(f))
