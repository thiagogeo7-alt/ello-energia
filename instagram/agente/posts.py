"""Cria um carrossel educativo com a identidade da ELLO e publica no feed."""
import html
from datetime import datetime
from pathlib import Path

from . import aprendizado, claude, config, dados_git, estado, instagram

MODELO_HTML = (Path(__file__).parent / "carrossel.html").read_text(encoding="utf-8")

SISTEMA = f"""Você é o redator do Instagram da ELLO Energia. Cria carrosséis educativos,
claros e úteis, que as pessoas salvam e mandam para amigos. Siga à risca o guia da marca.

{config.MARCA}

Responda SOMENTE com um JSON válido."""

PEDIDO = """Crie o próximo carrossel da ELLO (5 slides).

Desempenho dos carrosséis anteriores:
{historico}

Regras dos slides:
- Slide 1 (capa): título curto e provocativo, até 7 palavras. Texto de apoio até 12 palavras.
- Slides 2 a 4: um ponto por slide. Título até 6 palavras, texto até 28 palavras.
- Slide 5 (final): chamada para simular a economia ou chamar no WhatsApp.

Devolva:
{{
  "tema": "tema curto",
  "gancho": "a promessa da capa",
  "slides": [{{"titulo": "...", "texto": "..."}}, ... 5 itens],
  "legenda": "legenda em português: gancho na 1ª linha, 2 a 4 linhas, chamada para ação e 3 a 5 hashtags"
}}"""

ESTILOS = ["escuro", "claro", "claro", "claro", "ambar"]


def _renderizar(slides: list[dict], pasta: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    pasta.mkdir(parents=True, exist_ok=True)
    arquivos = []
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pagina = nav.new_page(viewport={"width": 1080, "height": 1350})
        total = len(slides)
        for i, s in enumerate(slides, 1):
            classe = ESTILOS[min(i - 1, len(ESTILOS) - 1)]
            tipo = "capa" if i == 1 else ("final" if i == total else "conteudo")
            cta = f'<div class="cta">WhatsApp (19) 99562-1927</div>' if tipo == "final" else ""
            doc = (MODELO_HTML
                   .replace("{{classe}}", f"{classe} {tipo}")
                   .replace("{{cor_logo}}", "#0A1A33" if classe == "ambar" else "#F5A524")
                   .replace("{{n}}", str(i)).replace("{{total}}", str(total))
                   .replace("{{titulo}}", html.escape(s["titulo"]))
                   .replace("{{texto}}", html.escape(s.get("texto", "")))
                   .replace("{{cta}}", cta)
                   .replace("{{seta}}", "Arraste →" if i < total else ""))
            pagina.set_content(doc, wait_until="networkidle")
            arq = pasta / f"{i}.jpg"
            pagina.screenshot(path=str(arq), type="jpeg", quality=92)
            arquivos.append(arq)
        nav.close()
    return arquivos


def executar() -> dict:
    config.exigir("IG_TOKEN", "ANTHROPIC_API_KEY")
    est = estado.carregar()
    aprendizado.atualizar_metricas(est)

    ideia = claude.perguntar_json(
        SISTEMA, PEDIDO.format(historico=aprendizado.resumo_para_claude(est, "carrossel")),
        simulado={
            "tema": "Mitos da energia solar", "gancho": "3 mitos que fazem você pagar mais",
            "slides": [
                {"titulo": "3 mitos que fazem você pagar mais", "texto": "E a verdade sobre energia solar sem placa"},
                {"titulo": "\"Preciso de placa no telhado\"", "texto": "Não. A energia é gerada em usinas solares e chega como crédito na sua conta."},
                {"titulo": "\"Vou trocar de distribuidora\"", "texto": "Não. Você continua com a mesma distribuidora, que segue cuidando da rede."},
                {"titulo": "\"É caro para começar\"", "texto": "Não. Não há custo de adesão nem equipamento para comprar."},
                {"titulo": "Quanto você economiza?", "texto": "Simule no link da bio ou chame no WhatsApp."},
            ],
            "legenda": "Você acredita em algum desses mitos?\nSalve para mostrar para alguém.\n#energiasolar #campinas #contadeluz",
        })

    carimbo = datetime.now().strftime("%Y%m%d-%H%M")
    import tempfile
    pasta = Path(tempfile.mkdtemp())
    arquivos = _renderizar(ideia["slides"], pasta)
    arquivos = [a.rename(pasta / f"carrossel-{carimbo}-{a.name}") for a in arquivos]
    # Versão 9:16 do 1º slide para os Stories (fundo desfocado do próprio slide)
    story = pasta / f"carrossel-{carimbo}-story.jpg"
    try:
        import subprocess
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(arquivos[0]), "-filter_complex",
                        "[0]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5,"
                        "eq=brightness=-0.15[f];[0]scale=1000:-1[s];[f][s]overlay=(W-w)/2:(H-h)/2",
                        "-q:v", "2", str(story)], check=True)
    except Exception as e:
        print(f"Aviso: sem imagem para Story ({e})")
        story = None
    urls = dados_git.publicar_midia(arquivos + ([story] if story else []))   # precisam estar públicas
    url_story = urls.pop() if story else None

    media_id = instagram.publicar_carrossel(urls, ideia["legenda"])
    if url_story and instagram.copiar_para_stories(url_story, video=False):
        estado.registrar(est, "story", f"Carrossel copiado para os Stories: {ideia.get('tema', '')}")
    est["publicacoes"].append({
        "data": estado.agora(), "tipo": "carrossel", "ref": estado.proximo_ref(est, "carrossel"), "tema": ideia.get("tema"),
        "gancho": ideia.get("gancho"), "legenda": ideia["legenda"], "imagens": urls, "media_id": media_id,
        "permalink": instagram.permalink(media_id),
    })
    est["custos"].append({"data": estado.agora(), "servico": "Claude (texto)", "usd": 0.03})
    estado.registrar(est, "carrossel", ideia.get("tema", ""))
    estado.salvar(est)
    print(f"Carrossel publicado: {media_id} — tema: {ideia.get('tema')}")
    return ideia
