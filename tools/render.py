#!/usr/bin/env python3
"""Рендер планировки поверх обмерной подложки.

Система координат (мм), общая для обоих этажей:
  начало (0,0) — внутренний верхний левый угол кухни-гостиной (пом. 3) 1 этажа,
  X — вправо, Y — вниз (как на листе обмера).
Масштаб подложки откалиброван по размеру 6333 мм (внутренняя ширина пом. 3): 9.02 мм/px.
Привязка 2 этажа к 1 — по левой наружной стене [ПРОВЕРИТЬ].

Использование:
  python3 tools/render.py designs/A.json out_dir/ [--no-underlay]
JSON: {"floor1": [item, ...], "floor2": [item, ...]}
item:
  {"t":"rect","x":..,"y":..,"w":..,"h":..,"label":"Диван","cls":"furn|zone|wet|stair|new_wall|demo|tech","rot":0}
  {"t":"poly","pts":[[x,y],...],"label":..,"cls":..}
  {"t":"line","pts":[[x,y],[x,y]],"cls":"new_wall|demo|dim"}
  {"t":"door","x":..,"y":..,"w":..,"dir":"up|down|left|right","hinge":"l|r","cls":"new"}
  {"t":"text","x":..,"y":..,"text":"...","size":180}
  {"t":"stairs","x":..,"y":..,"w":..,"h":..,"n":..,"dir":"up|down|left|right","label":".."}
  {"t":"sym","x":..,"y":..,"k":"socket|switch|light|spot|track|led|ac|tv|wifi|cam|floorheat|water|sewer|gas|vent|pendant","label":".."}
"""
import base64, json, math, sys, os, html

K = 9.02  # мм на пиксель подложки
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNDER = {
    "floor1": dict(img="source/obmer_floor1_crop.png", px0=500, py0=380, ox=594, oy=513),
    "floor2": dict(img="source/obmer_floor2_crop.png", px0=420, py0=470, ox=594 - 73, oy=513 + 31),
}
# Видимая область (мм)
VIEW = {"floor1": (-900, -1300, 11800, 6700), "floor2": (-900, -1300, 11800, 6700)}

CSS = {
    "furn": "fill:#efe6d8;stroke:#5b4a3a;stroke-width:18",
    "zone": "fill:#c9a77c;fill-opacity:.18;stroke:#a07c52;stroke-width:14;stroke-dasharray:60 40",
    "wet": "fill:#b9d3e0;fill-opacity:.7;stroke:#2f5d75;stroke-width:18",
    "stair": "fill:#e8dcc9;stroke:#3d2f22;stroke-width:18",
    "new_wall": "fill:#6b5a49;stroke:#3d2f22;stroke-width:10",
    "demo": "fill:none;stroke:#c0392b;stroke-width:30;stroke-dasharray:80 50",
    "tech": "fill:#d8d8d8;stroke:#555;stroke-width:16",
    "dim": "stroke:#1f5fa8;stroke-width:10",
    "light": "fill:#f6d77a;fill-opacity:.35;stroke:#b58b1c;stroke-width:14",
    "storage": "fill:#d9c6a8;stroke:#5b4a3a;stroke-width:18",
    "heat": "fill:#e9967a;fill-opacity:.18;stroke:#c0392b;stroke-width:10;stroke-dasharray:30 30",
}

SYM_COL = {"socket": "#1f5fa8", "switch": "#7a3fa0", "light": "#b58b1c", "spot": "#b58b1c", "pendant": "#b58b1c",
           "track": "#b58b1c", "led": "#e0a400", "ac": "#2e86c1", "tv": "#333", "wifi": "#16a085", "cam": "#c0392b",
           "floorheat": "#c0392b", "water": "#2471a3", "sewer": "#7b5230", "gas": "#d4ac0d", "vent": "#17a589",
           "shield": "#555"}


def esc(s):
    return html.escape(str(s))


def underlay(floor):
    u = UNDER[floor]
    p = os.path.join(ROOT, u["img"])
    from PIL import Image
    w, h = Image.open(p).size
    b64 = base64.b64encode(open(p, "rb").read()).decode()
    x = (u["px0"] - u["ox"]) * K
    y = (u["py0"] - u["oy"]) * K
    return f'<image href="data:image/png;base64,{b64}" x="{x:.0f}" y="{y:.0f}" width="{w*K:.0f}" height="{h*K:.0f}" opacity=".55" preserveAspectRatio="none"/>'


def label(x, y, text, size=150, anchor="middle", color="#2b2118", rot=0):
    lines = str(text).split("\n")
    out = []
    for i, ln in enumerate(lines):
        dy = (i - (len(lines) - 1) / 2) * size * 1.15
        tr = f' transform="rotate({rot} {x:.0f} {y:.0f})"' if rot else ""
        out.append(f'<text x="{x:.0f}" y="{y+dy+size*0.35:.0f}" font-size="{size}" text-anchor="{anchor}" fill="{color}" font-family="Jost, Arial, sans-serif"{tr}>{esc(ln)}</text>')
    return "".join(out)


def item_svg(it):
    t = it.get("t", "rect")
    cls = it.get("cls", "furn")
    st = CSS.get(cls, CSS["furn"])
    o = []
    if t == "group":
        inner = "".join(item_svg(x) for x in it.get("items", []))
        return f'<g opacity="{it.get("opacity", 1)}">{inner}</g>'
    if t == "rect":
        x, y, w, h = it["x"], it["y"], it["w"], it["h"]
        rot = it.get("rot", 0)
        tr = f' transform="rotate({rot} {x+w/2} {y+h/2})"' if rot else ""
        rx = it.get("rx", 0)
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" style="{st}"{tr}/>')
        if it.get("label"):
            size = it.get("size", min(150, max(70, min(w, h) / 3.2)))
            vert = h > w * 1.8 and w < 900
            o.append(label(x + w / 2, y + h / 2, it["label"], size, rot=(-90 if vert else 0)))
    elif t == "circle":
        o.append(f'<circle cx="{it["x"]}" cy="{it["y"]}" r="{it["r"]}" style="{st}"/>')
        if it.get("label"):
            o.append(label(it["x"], it["y"], it["label"], it.get("size", 100)))
    elif t == "poly":
        pts = " ".join(f"{a},{b}" for a, b in it["pts"])
        o.append(f'<polygon points="{pts}" style="{st}"/>')
        if it.get("label"):
            cx = sum(p[0] for p in it["pts"]) / len(it["pts"])
            cy = sum(p[1] for p in it["pts"]) / len(it["pts"])
            o.append(label(it.get("lx", cx), it.get("ly", cy), it["label"], it.get("size", 140)))
    elif t == "line":
        pts = " ".join(f"{a},{b}" for a, b in it["pts"])
        o.append(f'<polyline points="{pts}" style="{st};fill:none"/>')
        if it.get("label"):
            (x1, y1), (x2, y2) = it["pts"][0], it["pts"][-1]
            o.append(label((x1 + x2) / 2, (y1 + y2) / 2 - 120, it["label"], it.get("size", 110), color="#1f5fa8"))
    elif t == "door":
        x, y, w = it["x"], it["y"], it["w"]
        d = it.get("dir", "down"); hinge = it.get("hinge", "l")
        col = "#3d2f22"
        # проём вдоль оси: horizontal для up/down, vertical для left/right
        if d in ("up", "down"):
            sgn = 1 if d == "down" else -1
            hx = x if hinge == "l" else x + w
            ex = x + w if hinge == "l" else x
            o.append(f'<line x1="{hx}" y1="{y}" x2="{hx}" y2="{y+sgn*w}" stroke="{col}" stroke-width="16"/>')
            sweep = 1 if (sgn > 0) == (hinge == "l") else 0
            o.append(f'<path d="M {hx} {y+sgn*w} A {w} {w} 0 0 {sweep} {ex} {y}" fill="none" stroke="{col}" stroke-width="8" stroke-dasharray="30 20"/>')
        else:
            sgn = 1 if d == "right" else -1
            hy = y if hinge == "l" else y + w
            ey = y + w if hinge == "l" else y
            o.append(f'<line x1="{x}" y1="{hy}" x2="{x+sgn*w}" y2="{hy}" stroke="{col}" stroke-width="16"/>')
            sweep = 0 if (sgn > 0) == (hinge == "l") else 1
            o.append(f'<path d="M {x+sgn*w} {hy} A {w} {w} 0 0 {sweep} {x} {ey}" fill="none" stroke="{col}" stroke-width="8" stroke-dasharray="30 20"/>')
    elif t == "text":
        o.append(label(it["x"], it["y"], it["text"], it.get("size", 160), it.get("anchor", "middle"), it.get("color", "#2b2118")))
    elif t == "stairs":
        x, y, w, h, n = it["x"], it["y"], it["w"], it["h"], it.get("n", 7)
        d = it.get("dir", "up")
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" style="{CSS["stair"]}"/>')
        for i in range(1, n):
            if d in ("up", "down"):
                yy = y + h * i / n
                o.append(f'<line x1="{x}" y1="{yy:.0f}" x2="{x+w}" y2="{yy:.0f}" stroke="#3d2f22" stroke-width="10"/>')
            else:
                xx = x + w * i / n
                o.append(f'<line x1="{xx:.0f}" y1="{y}" x2="{xx:.0f}" y2="{y+h}" stroke="#3d2f22" stroke-width="10"/>')
        # стрелка подъёма
        if d in ("up", "down"):
            y1, y2 = (y + h - 100, y + 100) if d == "up" else (y + 100, y + h - 100)
            cx = x + w / 2
            o.append(f'<line x1="{cx}" y1="{y1}" x2="{cx}" y2="{y2}" stroke="#a0522d" stroke-width="18" marker-end="url(#arr)"/>')
        else:
            x1, x2 = (x + w - 100, x + 100) if d == "left" else (x + 100, x + w - 100)
            cy = y + h / 2
            o.append(f'<line x1="{x1}" y1="{cy}" x2="{x2}" y2="{cy}" stroke="#a0522d" stroke-width="18" marker-end="url(#arr)"/>')
        if it.get("label"):
            o.append(label(x + w / 2, y + h / 2 + 200, it["label"], 90, color="#a0522d"))
    elif t == "sym":
        x, y, k = it["x"], it["y"], it["k"]
        c = SYM_COL.get(k, "#333")
        r = 75
        if k == "socket":
            o.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" stroke="{c}" stroke-width="16"/><line x1="{x-r}" y1="{y}" x2="{x+r}" y2="{y}" stroke="{c}" stroke-width="16"/>')
        elif k == "switch":
            o.append(f'<circle cx="{x}" cy="{y}" r="{r*0.7}" fill="{c}"/><line x1="{x}" y1="{y}" x2="{x+r*1.6}" y2="{y-r*1.6}" stroke="{c}" stroke-width="16"/>')
        elif k in ("light", "pendant"):
            o.append(f'<circle cx="{x}" cy="{y}" r="{r*1.4}" fill="#fff6d6" stroke="{c}" stroke-width="16"/><line x1="{x-r}" y1="{y-r}" x2="{x+r}" y2="{y+r}" stroke="{c}" stroke-width="12"/><line x1="{x-r}" y1="{y+r}" x2="{x+r}" y2="{y-r}" stroke="{c}" stroke-width="12"/>')
        elif k == "spot":
            o.append(f'<circle cx="{x}" cy="{y}" r="{r*0.8}" fill="#fff6d6" stroke="{c}" stroke-width="14"/><circle cx="{x}" cy="{y}" r="{r*0.3}" fill="{c}"/>')
        elif k in ("led", "track"):
            x2, y2 = it.get("x2", x + 1000), it.get("y2", y)
            dash = "60 30" if k == "led" else "none"
            o.append(f'<line x1="{x}" y1="{y}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="{30 if k=="track" else 22}" stroke-dasharray="{dash}"/>')
        else:
            txt = {"ac": "AC", "tv": "TV", "wifi": "Wi", "cam": "CAM", "floorheat": "ТП", "water": "В", "sewer": "К",
                   "gas": "Г", "vent": "ВК", "shield": "ЩР"}.get(k, k)
            o.append(f'<rect x="{x-110}" y="{y-75}" width="220" height="150" rx="20" fill="#fff" stroke="{c}" stroke-width="14"/>')
            o.append(f'<text x="{x}" y="{y+40}" font-size="105" text-anchor="middle" fill="{c}" font-family="Arial" font-weight="700">{txt}</text>')
        if it.get("label"):
            o.append(label(x, y + 190, it["label"], 75, color=c))
    return "".join(o)


def render(items, floor, title="", show_under=True, grid=True):
    vx, vy, vw, vh = VIEW[floor]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vx} {vy} {vw} {vh}" class="plan">',
         '<defs><marker id="arr" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#a0522d"/></marker></defs>',
         f'<rect x="{vx}" y="{vy}" width="{vw}" height="{vh}" fill="#fffdf9"/>']
    if show_under:
        s.append(underlay(floor))
    if grid:
        for gx in range(-500, vx + vw, 500):
            w = 6 if gx % 1000 else 10
            s.append(f'<line x1="{gx}" y1="{vy}" x2="{gx}" y2="{vy+vh}" stroke="#7aa" stroke-opacity=".25" stroke-width="{w}"/>')
            if gx % 1000 == 0:
                s.append(f'<text x="{gx+20}" y="{vy+120}" font-size="100" fill="#699">{gx}</text>')
        for gy in range(-1000, vy + vh, 500):
            w = 6 if gy % 1000 else 10
            s.append(f'<line x1="{vx}" y1="{gy}" x2="{vx+vw}" y2="{gy}" stroke="#7aa" stroke-opacity=".25" stroke-width="{w}"/>')
            if gy % 1000 == 0:
                s.append(f'<text x="{vx+20}" y="{gy-20}" font-size="100" fill="#699">{gy}</text>')
    for it in items:
        s.append(item_svg(it))
    if title:
        s.append(f'<text x="{vx+200}" y="{vy+vh-150}" font-size="220" fill="#2b2118" font-family="Jost, Arial">{esc(title)}</text>')
    s.append("</svg>")
    return "\n".join(s)


def main():
    src, out = sys.argv[1], sys.argv[2]
    show = "--no-underlay" not in sys.argv
    os.makedirs(out, exist_ok=True)
    d = json.load(open(src))
    name = os.path.splitext(os.path.basename(src))[0]
    for fl in ("floor1", "floor2"):
        svg = render(d.get(fl, []), fl, f"{name} · {'1 этаж' if fl=='floor1' else '2 этаж (мансарда)'}", show)
        p = os.path.join(out, f"{name}_{fl}.svg")
        open(p, "w").write(svg)
        print(p)


if __name__ == "__main__":
    main()
