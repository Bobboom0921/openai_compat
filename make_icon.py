#!/usr/bin/env python3
"""生成 openai_compat 的品牌图标(brand/icon.png),纯标准库,无第三方依赖。"""
import math
import os
import struct
import zlib

SIZE = 512


def lerp(a, b, t):
    return a + (b - a) * t


# ---- 辅助:像素级形状判断(简化版,不做抗锯齿) ----
def in_rounded_square(x, y, cx, cy, half, radius):
    """中心在 (cx,cy)、半宽 half、圆角 radius 的圆角矩形。"""
    dx = abs(x - cx) - (half - radius)
    dy = abs(y - cy) - (half - radius)
    if dx <= 0 and dy <= 0:
        return True
    if dx < 0:
        dx = 0
    if dy < 0:
        dy = 0
    return dx * dx + dy * dy <= radius * radius


def in_circle(x, y, cx, cy, r):
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def in_triangle(x, y, a, b, c):
    """点在三角形内(叉积法)。"""
    def sgn(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1, d2, d3 = sgn((x, y), a, b), sgn((x, y), b, c), sgn((x, y), c, a)
    neg, pos = (d1 < 0) or (d2 < 0) or (d3 < 0), (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (neg and pos)


def build():
    # 渐变:左上 cyan(34,211,238) -> 右下 violet(124,58,237)
    top_c, bot_c = (34, 211, 238), (124, 58, 237)
    for y in range(SIZE):
        t = y / SIZE
        bg = (lerp(top_c[0], bot_c[0], t), lerp(top_c[1], bot_c[1], t), lerp(top_c[2], bot_c[2], t))
        for x in range(SIZE):
            u = x / SIZE
            # 沿对角线的渐变更自然
            diag = (u + 1 - (t)) / 2
            diag = max(0.0, min(1.0, diag))
            r = lerp(top_c[0], bot_c[0], diag)
            g = lerp(top_c[1], bot_c[1], diag)
            b = lerp(top_c[2], bot_c[2], diag)

            if not in_rounded_square(x, y, SIZE / 2, SIZE / 2, 236, 96):
                yield (0, 0, 0, 0)  # 透明
                continue

            # 白色对话气泡:主圆 + 左下小尾巴
            bubble_cx, bubble_cy, bubble_r = 256, 240, 132
            tail = [(212, 356), (268, 348), (224, 402)]
            if in_circle(x, y, bubble_cx, bubble_cy, bubble_r) or in_triangle(x, y, *tail):
                # 气泡内部三个圆点(代表"思考/LLM"),用背景色
                for dot_x, dot_y, dot_r in ((180, 240, 20), (256, 240, 20), (332, 240, 20)):
                    if in_circle(x, y, int(dot_x), int(dot_y), int(dot_r)):
                        yield (int(r), int(g), int(b), 255)
                        break
                else:
                    yield (255, 255, 255, 255)
                continue

            yield (int(r), int(g), int(b), 255)


def write_png(path, pixels):
    """pixels 是逐行逐像素的 (r,g,b,a) 生成器。"""
    raw = bytearray()
    count = 0
    line = bytearray(b"\x00")  # 每行前导 filter type 0
    for (r, g, b, a) in pixels:
        line += bytes((r, g, b, a))
        count += 1
        if count % SIZE == 0:
            raw += line
            line = bytearray(b"\x00")

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    print("written:", path, len(raw), "bytes-raw")


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "custom_components", "openai_compat", "brand", "icon.png")
    write_png(out, list(build()))