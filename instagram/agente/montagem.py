"""Monta o Reels no formato do vídeo modelo da ELLO.

Formato novo (montar_roteiro, 20–30 s): 3–4 cenas com balões de diálogo, passos explicativos ou legendas,
seguidas da tela da marca.

Formato original (montar, ~13,7 s):
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
        origem = cena_url_ou_arquivo.split("?")[0].lower()
        eh_imagem = origem.endswith((".jpg", ".jpeg", ".png", ".webp"))
        bruto = tmp / ("cena-original" + (Path(origem).suffix if eh_imagem else ".mp4"))
        if cena_url_ou_arquivo.startswith("http"):
            bruto.write_bytes(requests.get(cena_url_ou_arquivo, timeout=120).content)
        else:
            shutil.copy(cena_url_ou_arquivo, bruto)
        cena = tmp / "cena.mp4"
        if eh_imagem:
            # Foto vira vídeo: aproximação lenta da câmera + leve tremida (efeito "susto")
            n = int(CENA_S * FPS)
            _ff("-loop", "1", "-i", str(bruto), "-t", str(CENA_S), "-vf",
                f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
                f"zoompan=z='1+0.18*on/{n}':x='iw/2-(iw/zoom/2)+if(between(on,{int(1.0 * FPS)},{int(1.4 * FPS)}),8*sin(on*2),0)'"
                f":y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS},format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(cena))
        else:
            shutil.copy(bruto, cena)

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
        elif tem_trilha:
            entradas += ["-i", str(TRILHA)]
            f.append(f"[{idx_trilha + 1}:a]atrim=0:{CENA_S},asetpts=PTS-STARTPTS,aresample=44100,"
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


# ---------------------------------------------------------------------------
# Formato novo: várias cenas (diálogo, explicativo com desenhos ou reação)
# ---------------------------------------------------------------------------
CENA_ROTEIRO_S = 4.6
FADE_CENAS_S = 0.4

ROTEIRO_CSS = """
body{background:transparent}
.topo{position:absolute;top:70px;left:0;right:0;text-align:center;font-weight:900;line-height:1.02;
  font-size:80px;-webkit-text-stroke:5px #0A1A33;paint-order:stroke fill;text-shadow:0 6px 18px rgba(0,0,0,.45)}
.topo .l1{color:#fff}.topo .l2{color:#F5CF4A}
.balao{position:absolute;top:1140px;max-width:820px;background:#fff;color:#0A1A33;font-weight:800;font-size:54px;
  line-height:1.18;padding:30px 40px 34px;border-radius:44px;box-shadow:0 14px 40px rgba(0,0,0,.35)}
.balao.a{left:60px;border-bottom-left-radius:10px}.balao.b{right:60px;border-bottom-right-radius:10px;background:#FFF6D6}
.balao .quem{display:inline-block;background:#F5B731;color:#0A1A33;font-size:34px;font-weight:900;
  padding:6px 22px;border-radius:22px;margin-bottom:12px;letter-spacing:.5px}
.balao.b .quem{background:#2D6DB0;color:#fff}
.passo{position:absolute;top:1180px;left:60px;right:60px;display:flex;gap:30px;align-items:center;background:rgba(14,34,64,.92);
  border:6px solid #F5CF4A;border-radius:36px;padding:30px 36px;color:#fff;font-weight:800;font-size:52px;line-height:1.15;
  box-shadow:0 14px 40px rgba(0,0,0,.35)}
.passo b{flex:none;width:96px;height:96px;border-radius:50%;background:#F5B731;color:#0A1A33;display:grid;place-items:center;font-size:58px;font-weight:900}
.leg{position:absolute;top:1200px;left:70px;right:70px;text-align:center;color:#fff;font-weight:900;font-size:64px;line-height:1.1;
  -webkit-text-stroke:4px #0A1A33;paint-order:stroke fill;text-shadow:0 6px 18px rgba(0,0,0,.5)}
.tag{position:absolute;top:860px;left:50%;transform:translateX(-50%) rotate(-6deg);background:#D92D2D;color:#fff;font-weight:900;
  font-size:88px;padding:16px 42px;border:7px solid #F5CF4A;border-radius:22px;box-shadow:0 14px 40px rgba(0,0,0,.45);white-space:nowrap}
.virada{position:absolute;top:1560px;left:50%;transform:translateX(-50%);background:#0E2240;color:#fff;font-weight:900;font-size:70px;
  padding:12px 48px;border:6px solid #F5CF4A;border-radius:60px;white-space:nowrap;box-shadow:0 12px 30px rgba(0,0,0,.4)}
"""


def _camadas_roteiro(r: dict) -> list[list[tuple[str, float]]]:
    """Para cada cena, as camadas transparentes (html, segundo de entrada dentro da cena)."""
    e = html.escape
    nomes = r.get("nomes") or ["", ""]
    cenas = r["cenas"]
    saida = []
    for i, c in enumerate(cenas):
        camadas = []
        if i == 0 and r.get("texto_topo_1"):
            topo = (f'<div class="topo"><div class="l1">{e(r["texto_topo_1"])}</div>'
                    f'<div class="l2">{e(r.get("texto_topo_2", ""))}</div></div>')
            camadas.append((_doc(ROTEIRO_CSS, topo, False), 0.0))
        texto = (c.get("texto") or "").strip()
        if texto:
            if r.get("formato") == "dialogo" and c.get("quem") in ("A", "B"):
                lado = c["quem"].lower()
                nome = nomes[0 if lado == "a" else 1] if len(nomes) > 1 else ""
                quem = f'<span class="quem">{e(nome)}</span><br>' if nome else ""
                corpo = f'<div class="balao {lado}">{quem}{e(texto)}</div>'
            elif r.get("formato") == "explicativo":
                corpo = f'<div class="passo"><b>{i + 1}</b><span>{e(texto)}</span></div>'
            else:
                corpo = f'<div class="leg">{e(texto)}</div>'
            camadas.append((_doc(ROTEIRO_CSS, corpo, False), 0.35))
        if c.get("destaque"):
            camadas.append((_doc(ROTEIRO_CSS, f'<div class="tag">{e(c["destaque"])}</div>', False), 1.0))
        if i == len(cenas) - 1 and r.get("virada"):
            camadas.append((_doc(ROTEIRO_CSS, f'<div class="virada">{e(r["virada"])}</div>', False), 2.4))
        saida.append(camadas)
    return saida


def _baixar(origem: str, destino: Path) -> Path:
    if origem.startswith("http"):
        destino.write_bytes(requests.get(origem, timeout=120).content)
    else:
        shutil.copy(origem, destino)
    return destino


def _clipe_imagem(img: Path, saida: Path, n_cena: int, dur: float) -> None:
    """Foto vira vídeo com movimento de câmera: alterna aproximar, afastar e deslizar."""
    n = int(dur * FPS)
    movimentos = [
        (f"1+0.14*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),                 # aproxima
        (f"1.14-0.14*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),              # afasta
        ("1.12", f"(iw-iw/zoom)*on/{n}", "ih/2-(ih/zoom/2)"),                       # desliza p/ direita
        ("1.12", f"(iw-iw/zoom)*(1-on/{n})", "ih/2-(ih/zoom/2)"),                   # desliza p/ esquerda
    ]
    z, x, y = movimentos[n_cena % len(movimentos)]
    _ff("-loop", "1", "-i", str(img), "-t", f"{dur}", "-vf",
        f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={FPS},format=yuv420p,setsar=1",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(saida))


def _duracao(arq: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def montar_roteiro(imagens: list[str], roteiro: dict, destino: Path, trilha: str | None = None,
                   falas: list[str | None] | None = None) -> Path:
    """imagens: uma por cena (URL ou arquivo). falas: áudio da fala de cada cena (opcional).
    Cada cena dura pelo menos CENA_ROTEIRO_S e o suficiente para a fala caber inteira."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        camadas = _camadas_roteiro(roteiro)
        n = len(imagens)
        falas = (falas or []) + [None] * (n - len(falas or []))

        # Áudios das falas e duração de cada cena
        arquivos_fala, dur_cenas = [], []
        for i in range(n):
            arq = None
            if falas[i]:
                try:
                    arq = _baixar(falas[i], tmp / f"fala{i}{Path(falas[i].split('?')[0]).suffix or '.mp3'}")
                except Exception as e:
                    print(f"Aviso: fala {i + 1} indisponível ({e})")
            arquivos_fala.append(arq)
            d = _duracao(arq) if arq else 0.0
            dur_cenas.append(round(max(CENA_ROTEIRO_S, d + 0.9), 2))

        clipes = []
        for i, (img, cams) in enumerate(zip(imagens, camadas)):
            dur = dur_cenas[i]
            bruto = _baixar(img, tmp / f"img{i}.jpg")
            base = tmp / f"base{i}.mp4"
            _clipe_imagem(bruto, base, i, dur)
            if cams:
                pasta = tmp / f"c{i}"
                pasta.mkdir()
                pngs = _render([d for d, _ in cams], pasta, True)
                entradas = ["-i", str(base)]
                for png in pngs:
                    entradas += ["-loop", "1", "-t", f"{dur}", "-i", str(png)]
                f, ultimo = [], "0:v"
                for k, (_, inicio) in enumerate(cams, start=1):
                    f.append(f"[{ultimo}][{k}:v]overlay=0:0:enable='gte(t,{inicio})'[o{k}]")
                    ultimo = f"o{k}"
                clipe = tmp / f"clipe{i}.mp4"
                _ff(*entradas, "-filter_complex", ";".join(f), "-map", f"[{ultimo}]", "-t", f"{dur}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(clipe))
            else:
                clipe = base
            clipes.append(clipe)

        # Tela da marca
        cartela = _quadros_cartela(roteiro)
        pngs_cart = _render([d for d, _ in cartela], tmp, False)
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

        # Junta cenas e tela da marca com transições suaves
        partes = clipes + [cart_mp4]
        duracoes = dur_cenas + [dur_cart]
        entradas = []
        for arq in partes:
            entradas += ["-i", str(arq)]
        f, ultimo, acumulado = [], "0:v", duracoes[0]
        inicios = [0.0]
        for k in range(1, len(partes)):
            fade = FADE_S if k == len(partes) - 1 else FADE_CENAS_S
            f.append(f"[{ultimo}][{k}:v]xfade=transition=fade:duration={fade}:offset={acumulado - fade:.3f}[x{k}]")
            ultimo = f"x{k}"
            inicios.append(acumulado - fade)
            acumulado += duracoes[k] - fade
        total = acumulado
        f.append(f"[{ultimo}]format=yuv420p[v]")

        # Áudio: trilha (nova a cada Reels; se falhar, a padrão) + falas por cima
        idx = len(partes)
        musica = TRILHA
        if trilha:
            try:
                musica = _baixar(trilha, tmp / ("trilha" + (Path(trilha.split("?")[0]).suffix or ".wav")))
            except Exception as e:
                print(f"Aviso: trilha nova indisponível ({e}); usando a padrão")
        tem_fala = any(arquivos_fala)
        rotulos = []
        if musica.exists():
            entradas += ["-stream_loop", "-1", "-i", str(musica)]
            vol = 0.22 if tem_fala else 1.0
            f.append(f"[{idx}:a]atrim=0:{total:.2f},asetpts=PTS-STARTPTS,aresample=44100,volume={vol},"
                     f"afade=t=in:d=0.5,afade=t=out:st={total - 1.0:.2f}:d=1.0[mus]")
            rotulos.append("[mus]")
            idx += 1
        for i, arq in enumerate(arquivos_fala):
            if not arq:
                continue
            entradas += ["-i", str(arq)]
            atraso = int((inicios[i] + 0.35) * 1000)
            f.append(f"[{idx}:a]aresample=44100,volume=1.6,adelay={atraso}|{atraso}[f{i}]")
            rotulos.append(f"[f{i}]")
            idx += 1
        if rotulos:
            f.append(f"{''.join(rotulos)}amix=inputs={len(rotulos)}:normalize=0:duration=first,"
                     f"apad,atrim=0:{total:.2f}[a]" if len(rotulos) > 1 else f"{rotulos[0]}apad,atrim=0:{total:.2f}[a]")
        else:
            f.append(f"anullsrc=r=44100:cl=stereo,atrim=0:{total:.2f}[a]")

        destino.parent.mkdir(parents=True, exist_ok=True)
        _ff(*entradas, "-filter_complex", ";".join(f), "-map", "[v]", "-map", "[a]",
            "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", str(destino))

        capa = destino.with_suffix(".jpg")
        _ff("-ss", "1.2", "-i", str(destino), "-frames:v", "1", "-q:v", "3", str(capa))
    return destino
