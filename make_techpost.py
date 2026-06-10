"""
make_techpost.py — convierte POST_TECNICO.md en tech_post.html (listo para pegar en Substack).
Maneja bloques de código (```), encabezados, negrita/cursiva, código en línea, listas y separadores.
USO: python make_techpost.py
"""
import re, html as H

SRC, OUT = "POST_TECNICO.md", "tech_post.html"

def inline(s):
    s = H.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`]+?)`", r"<code style='background:#eef1f6;padding:1px 5px;border-radius:4px;font-size:90%'>\1</code>", s)
    s = re.sub(r"(?<![\*\w])\*([^*]+?)\*(?![\*\w])", r"<i>\1</i>", s)
    return s

lines = open(SRC, encoding="utf-8").read().split("\n")
out, incode, buf, i = [], False, [], 0
while i < len(lines):
    ln = lines[i]
    if ln.strip().startswith("```"):
        if not incode:
            incode, buf = True, []
        else:
            incode = False
            out.append("<pre style='background:#0b1437;color:#d6e2ff;padding:14px 16px;border-radius:10px;"
                       "overflow-x:auto;font-size:12.5px;line-height:1.45;white-space:pre'>"
                       + H.escape("\n".join(buf)) + "</pre>")
        i += 1; continue
    if incode:
        buf.append(ln); i += 1; continue
    s = ln.rstrip()
    if not s.strip():
        i += 1; continue
    if s.startswith("#### "): out.append(f"<p style='color:#5566aa;font-size:15px;margin:2px 0 16px'><b>{inline(s[5:])}</b></p>")
    elif s.startswith("### "): out.append(f"<h3 style='color:#0e8a5f;margin:22px 0 4px'>{inline(s[4:])}</h3>")
    elif s.startswith("## "): out.append(f"<h2 style='color:#1f3b8b;margin:28px 0 8px'>{inline(s[3:])}</h2>")
    elif s.startswith("# "): out.append(f"<h1 style='margin:0 0 6px;line-height:1.25'>{inline(s[2:])}</h1>")
    elif s.strip() == "---": out.append("<hr style='border:none;border-top:1px solid #d9deec;margin:18px 0'>")
    elif s.startswith("- "): out.append(f"<p style='margin:5px 0 5px 18px;line-height:1.55'>• {inline(s[2:])}</p>")
    else: out.append(f"<p style='margin:9px 0;line-height:1.65'>{inline(s)}</p>")
    i += 1

doc = ("<div style='font-family:Georgia,\"Times New Roman\",serif;max-width:680px;margin:auto;"
       "color:#0b1437;padding:8px 14px'>" + "".join(out) + "</div>")
open(OUT, "w", encoding="utf-8").write(doc)
print(f"→ {OUT} guardado ({len(doc)} caracteres)")
