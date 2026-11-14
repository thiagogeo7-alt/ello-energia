"""Monta o Reels no formato do vídeo modelo da ELLO.

Estrutura (~13,7 s):
  0–5 s   cena realista gerada por IA + textos grandes por cima (pergunta, valor, virada)
  5–14 s  tela da marca: logo → "Energia que conecta" → benefícios um a um → "Comente PALAVRA"
"""
import html
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests

from . import config

W, H, FPS = 1080, 1920, 30
CENA_S = 5.0
FADE_S = 0.3
PASTA_MARCA = config.RAIZ / "marca"
LOGO = (PASTA_MARCA / "logo-ello.svg").read_text(encoding="utf-8")
TRILHA = PASTA_MARCA / "trilha-cartela.m4a"     # trilha da tela final (troque pelo áudio que quiser)

FONTES = '<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;700;800;900&display=swap" rel="stylesheet">'

BASE_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden;font-family:"Montserrat",sans-serif}
.fundo{position:absolute;inset:0;background:
  radial-gradient(ellipse 70% 45% at 38% 38%,#1B3A5E 0%,rgba(27,58,94,0) 70%),
  radial-gradient(ellipse 50% 35% at 80% 92%,rgba(120,90,20,.35) 0%,rgba(0,0,0,0) 70%),
  #0B1626}
"""

CENA_CSS = """
body{background:transparent}
.topo{position:absolute;top:70px;left:0;right:0;text-align:center;font-weight:900;line-height:1.02;
  font-size:84px;letter-spacing:.5px;-webkit-text-stroke:5px #0A1A33;paint-order:stroke fill;
  text-shadow:0 6px 18px rgba(0,0,0,.45)}
.topo .l1{color:#fff}.topo .l2{color:#F5CF4A}
.tag{position:absolute;top:880px;left:50%;transform:translateX(-50%) rotate(-6deg);background:#D92D2D;
  color:#fff;font-weight:900;font-size:92px;padding:18px 44px;border:7px solid #F5CF4A;border-radius:22px;
  box-shadow:0 14px 40px rgba(0,0,0,.45);white-space:nowrap}
.virada{position:absolute;top:1100px;left:50%;transform:translateX(-50%);background:#0E2240;color:#fff;
  font-weight:900;font-size:76px;padding:14px 50px;border:6px solid #F5CF4A;border-radius:60px;white-space:nowrap;
  box-shadow:0 12px 30px rgba(0,0,0,.4)}
"""

CARTELA_CSS = """
.logo{position:absolute;left:50%;transform:translateX(-50%);top:150px;width:520px}
.logo.grande{top:330px;width:820px}
.slogan{position:absolute;top:1010px;left:0;right:0;text-align:center;color:#F5CF4A;font-weight:500;font-size:62px;letter-spacing:3px}
h1{position:absolute;top:520px;left:0;right:0;text-align:center;font-weight:900;font-size:98px;line-height:1.02;color:#fff}
h1 span{color:#F5B731;display:block}
.sub{position:absolute;top:745px;left:0;right:0;text-align:center;color:#fff;font-weight:800;font-size:34px;letter-spacing:1px}
ul{position:absolute;top:840px;left:90px;right:90px;list-style:none}
li{display:flex;align-items:center;gap:30px;border:5px solid #2D6DB0;border-radius:28px;padding:30px 36px;margin-bottom:34px;
   background:rgba(10,26,51,.55);color:#fff;font-weight:700;font-size:44px}
li i{flex:none;width:62px;height:62px;border-radius:50%;background:#F5B731;display:grid;place-items:center}
li i svg{width:36px;height:36px}
.mais{position:absolute;top:1640px;left:0;right:0;text-align:center;color:#F5B731;font-weight:900;font-size:58px}
.comente{position:absolute;top:1190px;left:0;right:0;text-align:center;color:#fff;font-weight:700;font-size:54px}
.botao{position:absolute;top:1290px;left:50%;transform:translateX(-50%);background:#F5B731;border-radius:30px;
  padding:36px 70px;display:flex;align-items:center;gap:36px;color:#0A1A33;font-weight:900;font-size:76px;white-space:nowrap}
.botao svg{width:84px;height:84px}
.ganhe{position:absolute;top:1520px;left:0;right:0;text-align:center;color:#fff;font-weight:500;font-size:40px;line-height:1.35}
.ganhe b{color:#4D9BEA;font-weight:900}
.seta{position:absolute;top:1660px;left:50%;transform:translateX(-50%);width:0;height:0;
  border-left:30px solid transparent;border-right:30px solid transparent;border-top:44px solid #F5B731}
"""

CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="#0A1A33" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>'
BALAO = '<svg viewBox="0 0 24 24"><path fill="#0A1A33" d="M4 3h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-5 4v-4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/></svg>'


def _doc(css: str, corpo: str, fundo: bool = True) -> str:
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8">{FONTES}<style>{BASE_CSS}{css}</style></head>'
            f'<body>{"<div class=fundo></div>" if fundo else ""}{corpo}</body></html>')


def _quadros_cena(r: dict) -> list[tuple[str, float]]:
    """Três camadas transparentes que entram em momentos diferentes (html, segundo de entrada)."""
    e = html.escape
    topo = f'<div class="topo"><div class="l1">{e(r["texto_topo_1"])}</div><div class="l2">{e(r["texto_topo_2"])}</div></div>'
    tag = f'<div class="tag">{e(r["destaque"])}</div>' if r.get("destaque") else ""
    vir = f'<div class="virada">{e(r["virada"])}</div>' if r.get("virada") else ""
    return [(_doc(CENA_CSS, topo, False), 0.0), (_doc(CENA_CSS, tag, False), 1.0), (_doc(CENA_CSS, vir, False), 3.6)]


def _quadros_cartela(r: dict) -> list[tuple[str, float]]:
    """Sequência da tela da marca: (html, duração em segundos)."""
    e = html.escape
    logo = f'<div class="logo">{LOGO}</div>'
    titulo = '<h1>ENERGIA QUE<span>CONECTA</span></h1><div class="sub">A SOLUÇÃO PRA CONTA DE LUZ</div>'
    itens = r["beneficios"][:4]
    quadros = [(_doc(CARTELA_CSS, logo), 0.7), (_doc(CARTELA_CSS, logo + titulo), 0.7)]
    for n in range(1, len(itens) + 1):
        lista = "<ul>" + "".join(f"<li><i>{CHECK}</i>{e(t)}</li>" for t in itens[:n]) + "</ul>"
        quadros.append((_doc(CARTELA_CSS, logo + titulo + lista), 0.55))
    lista = "<ul>" + "".join(f"<li><i>{CHECK}</i>{e(t)}</li>" for t in itens) + "</ul>"
    quadros.append((_doc(CARTELA_CSS, logo + titulo + lista + '<div class="mais">e muito mais!</div>'), 1.0))
    final = f'<div class="logo grande">{LOGO}</div><div class="slogan">Tudo se conecta.</div>'
    quadros.append((_doc(CARTELA_CSS, final), 0.8))
    cta = (f'<div class="comente">Comente</div><div class="botao">{BALAO}{e(r["palavra_chave"].upper())}</div>'
           '<div class="ganhe">e ganhe a análise da sua conta<br><b>de luz GRÁTIS</b></div><div class="seta"></div>')
    quadros.append((_doc(CARTELA_CSS, final + cta), round(9.0 - sum(d for _, d in quadros), 3)))
    return quadros


def _render(paginas: list[str], pasta: Path, transparente: bool) -> list[Path]:
    from playwright.sync_api import sync_playwright
    saida = []
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pg = nav.new_page(viewport={"width": W, "height": H})
        for i, doc in enumerate(paginas):
            pg.set_content(doc, wait_until="networkidle")
            arq = pasta / f"{'cam' if transparente else 'car'}{i}.png"
            pg.screenshot(path=str(arq), omit_background=transparente)
            saida.append(arq)
        nav.close()
    return saida


def _tem_audio(arq: Path) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                        "-of", "csv=p=0", str(arq)], capture_output=True, text=True)
    return bool(r.stdout.strip())


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def montar(cena_url_ou_arquivo: str, roteiro: dict, destino: Path) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cena = tmp / "cena.mp4"
        if cena_url_ou_arquivo.startswith("http"):
            cena.write_bytes(requests.get(cena_url_ou_arquivo, timeout=120).content)
        else:
            shutil.copy(cena_url_ou_arquivo, cena)

        camadas = _quadros_cena(roteiro)
        pngs_cena = _render([d for d, _ in camadas], tmp, True)
        cartela = _quadros_cartela(roteiro)
        pngs_cart = _render([d for d, _ in cartela], tmp, False)

        # 1) Vídeo da tela da marca a partir das imagens
        lista = tmp / "cartela.txt"
        linhas = []
        for png, (_, dur) in zip(pngs_cart, cartela):
            linhas += [f"file '{png}'", f"duration {dur:.3f}"]
        linhas.append(f"file '{pngs_cart[-1]}'")
        lista.write_text("\n".join(linhas))
        cart_mp4 = tmp / "cartela.mp4"
        _ff("-f", "concat", "-safe", "0", "-i", str(lista), "-vf", f"fps={FPS},format=yuv420p,setsar=1",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(cart_mp4))
        dur_cart = sum(d for _, d in cartela)

        # 2) Cena + camadas de texto + transição + áudio
        entradas = ["-i", str(cena)]
        for png in pngs_cena:
            entradas += ["-loop", "1", "-t", str(CENA_S), "-i", str(png)]
        entradas += ["-i", str(cart_mp4)]
        idx_cart = 1 + len(pngs_cena)
        tem_trilha = TRILHA.exists()
        if tem_trilha:
            entradas += ["-i", str(TRILHA)]
        idx_trilha = idx_cart + 1

        f = [f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,"
             f"trim=0:{CENA_S},setpts=PTS-STARTPTS[v0]"]
        ultimo = "v0"
        for i, (_, inicio) in enumerate(camadas, start=1):
            f.append(f"[{ultimo}][{i}:v]overlay=0:0:enable='gte(t,{inicio})'[v{i}]")
            ultimo = f"v{i}"
        f.append(f"[{idx_cart}:v]fps={FPS},setsar=1[vc]")
        f.append(f"[{ultimo}][vc]xfade=transition=fade:duration={FADE_S}:offset={CENA_S - FADE_S},format=yuv420p[v]")

        total = CENA_S + dur_cart - FADE_S
        if _tem_audio(cena):
            f.append(f"[0:a]atrim=0:{CENA_S},asetpts=PTS-STARTPTS,aresample=44100,"
                     f"afade=t=out:st={CENA_S - 0.5}:d=0.5[a0]")
        else:
            f.append(f"anullsrc=r=44100:cl=stereo,atrim=0:{CENA_S}[a0]")
        if tem_trilha:
            f.append(f"[{idx_trilha}:a]atrim=0:{dur_cart},asetpts=PTS-STARTPTS,aresample=44100,"
                     f"afade=t=in:d=0.3,afade=t=out:st={dur_cart - 0.6}:d=0.6[a1]")
        else:
            f.append(f"anullsrc=r=44100:cl=stereo,atrim=0:{dur_cart}[a1]")
        f.append(f"[a0][a1]acrossfade=d={FADE_S}[a]")

        destino.parent.mkdir(parents=True, exist_ok=True)
        _ff(*entradas, "-filter_complex", ";".join(f), "-map", "[v]", "-map", "[a]",
            "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", str(destino))

        capa = destino.with_suffix(".jpg")
        _ff("-ss", "1.5", "-i", str(destino), "-frames:v", "1", "-q:v", "3", str(capa))
    return destino
