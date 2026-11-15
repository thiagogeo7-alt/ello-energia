"""Cria e publica o Reels no formato do vídeo modelo da ELLO.

Cena realista de 5 s gerada por IA (Kling 3.0) + textos por cima + tela animada da marca.
"""
import tempfile
from datetime import datetime
from pathlib import Path

from . import aprendizado, claude, config, dados_git, estado, instagram, montagem, video

SISTEMA = f"""Você é o estrategista de conteúdo e diretor de vídeo do Instagram da ELLO Energia.
Cada Reels segue o FORMATO MODELO da marca:

1. CENA DE 5 SEGUNDOS, ultra-realista, gerada por IA: uma situação do dia a dia com emoção forte e
   um toque de humor (ex.: pessoa abrindo a conta de luz na cozinha, arregalando os olhos, desesperando
   e desmaiando no chão de forma cômica). Vertical 9:16, câmera próxima, luz natural de casa brasileira.
2. Por cima da cena: uma pergunta-gancho em 2 linhas no topo (ex.: "SUA CONTA DE LUZ" / "VEIO ASSIM?"),
   um destaque em etiqueta vermelha (ex.: um valor de conta "R$ 1.487,90") e uma virada no fim
   (ex.: "TEM JEITO!").
3. Tela da marca (montada automaticamente): logo, "Energia que conecta", 4 benefícios e
   "Comente PALAVRA e ganhe a análise da sua conta de luz GRÁTIS".

Siga à risca o guia da marca abaixo.

{config.MARCA}

Responda SOMENTE com um JSON válido."""

PEDIDO = """Crie o próximo Reels da ELLO.

O que já sabemos do desempenho da conta:
{historico}

Estratégia: cerca de 70% das vezes faça uma variação nova do que melhor funcionou (mude a situação,
o personagem, o ambiente ou o gancho); 30% das vezes teste uma situação diferente. Diga qual fez.
Varie personagens (idade, gênero, aparência) e ambientes (cozinha, sala, escritório, comércio, condomínio).

Devolva este JSON:
{{
  "estrategia": "variacao" ou "teste",
  "tema": "tema curto em português",
  "gancho": "a ideia da cena em uma frase, em português",
  "prompt_cena": "prompt em INGLÊS para o modelo de vídeo, 5 segundos, vertical 9:16, ultra-realistic, cinematic, natural lighting, descrevendo personagem genérico (não famoso), ambiente brasileiro, ação segundo a segundo, expressão facial e movimento de câmera. Sem texto, legendas ou logotipos na imagem.",
  "prompt_imagem": "prompt em INGLÊS para UMA FOTO ultra-realista vertical do momento mais forte da cena (o pico da emoção), estilo fotografia profissional, lente 35mm, luz natural, pele e texturas realistas, personagem genérico, ambiente brasileiro, sem texto nem logotipos",
  "texto_topo_1": "1ª linha do gancho, MAIÚSCULAS, até 18 caracteres",
  "texto_topo_2": "2ª linha do gancho, MAIÚSCULAS, até 16 caracteres",
  "destaque": "texto curto da etiqueta vermelha (ex.: valor de conta fictício), até 12 caracteres",
  "virada": "frase de virada, MAIÚSCULAS, até 14 caracteres",
  "palavra_chave": "UMA palavra para as pessoas comentarem, MAIÚSCULAS (padrão: ECONOMIZAR)",
  "beneficios": ["4 itens escolhidos da lista de benefícios aprovados do guia da marca"],
  "legenda": "legenda em português: 1ª linha gancho forte, 2 a 3 linhas curtas, convite para comentar a palavra-chave, a linha obrigatória sobre vídeo com IA, e 3 a 5 hashtags"
}}"""

SIMULADO = {
    "estrategia": "variacao", "tema": "Susto com a conta de luz",
    "gancho": "Homem abre a conta de luz e desmaia",
    "prompt_cena": "Vertical 9:16 ultra-realistic cinematic shot, natural daylight in a Brazilian home kitchen...",
    "prompt_imagem": "Ultra-realistic vertical photo of a shocked young Brazilian man holding an electricity bill in his kitchen...",
    "prompt_imagem": "prompt em INGLÊS para UMA FOTO ultra-realista vertical do momento mais forte da cena (o pico da emoção), estilo fotografia profissional, lente 35mm, luz natural, pele e texturas realistas, personagem genérico, ambiente brasileiro, sem texto nem logotipos",
  "texto_topo_1": "SUA CONTA DE LUZ", "texto_topo_2": "VEIO ASSIM?", "destaque": "R$ 1.487,90",
    "virada": "TEM JEITO!", "palavra_chave": "ECONOMIZAR",
    "beneficios": ["Análise da conta GRÁTIS", "Economia de até 50% na conta",
                   "Zero investimento pra você", "Economia limpa pro planeta"],
    "legenda": "Sua conta de luz veio assim? 😱\nTem jeito, e sem placa no telhado.\nComente ECONOMIZAR que a gente te chama no direct.\n🎬 Vídeo criado com inteligência artificial.\n#contadeluz #energiasolar #campinas",
}


def executar(cena_local: str | None = None) -> dict:
    config.exigir("IG_TOKEN", "ANTHROPIC_API_KEY", "FAL_KEY")
    est = estado.carregar()

    aprendizado.atualizar_metricas(est)
    historico = aprendizado.resumo_para_claude(est, "reel")
    pedido = PEDIDO.format(historico=historico)
    tema = __import__("os").getenv("TEMA", "").strip()
    if tema:
        pedido += f"\n\nTEMA OBRIGATÓRIO deste Reels (use exatamente esta ideia): {tema}"
    r = claude.perguntar_json(SISTEMA, pedido, simulado=SIMULADO)

    r["palavra_chave"] = (r.get("palavra_chave") or "ECONOMIZAR").split()[0].upper()
    legenda = r["legenda"]
    if "inteligência artificial" not in legenda.lower():
        legenda += "\n\n🎬 Vídeo criado com inteligência artificial."

    # 1) Cena com IA (em simulação dá para passar um vídeo local para testar a montagem)
    if cena_local:
        cena = cena_local
    else:
        cena = video.gerar_cena(r.get("prompt_cena", ""), r.get("prompt_imagem") or r.get("prompt_cena", ""))
        est["custos"].append({"data": estado.agora(), "servico": f"fal.ai cena ({config.MODO_CENA})",
                              "usd": video.custo_estimado()})
        estado.salvar(est)   # registra o custo mesmo se algo falhar depois

    if config.SIMULAR and not cena_local:
        print("[simulação] sem cena real para montar; pulando a montagem.")
        urls = [f"{config.URL_MIDIA_BASE}/reel-simulado.mp4", f"{config.URL_MIDIA_BASE}/reel-simulado.jpg"]
    else:
        # 2) Montagem no formato da marca
        nome = f"reel-{datetime.now().strftime('%Y%m%d-%H%M')}"
        destino = Path(tempfile.mkdtemp()) / f"{nome}.mp4"
        montagem.montar(cena, r, destino)
        print(f"Vídeo montado: {destino}")
        # 3) Deixa o vídeo e a capa públicos para o Instagram buscar
        urls = dados_git.publicar_midia([destino, destino.with_suffix(".jpg")])

    media_id = instagram.publicar_reel(urls[0], legenda, capa_url=urls[1])

    est["publicacoes"].append({
        "data": estado.agora(), "tipo": "reel", "estrategia": r.get("estrategia"),
        "tema": r.get("tema"), "gancho": r.get("gancho"), "palavra_chave": r["palavra_chave"],
        "prompt": r.get("prompt_cena"), "textos": [r.get("texto_topo_1"), r.get("texto_topo_2"),
                                                   r.get("destaque"), r.get("virada")],
        "legenda": legenda, "media_id": media_id, "permalink": instagram.permalink(media_id),
        "modo": config.MODO_CENA,
    })
    est["custos"].append({"data": estado.agora(), "servico": "Claude (texto)", "usd": 0.03})
    estado.registrar(est, "reel", r.get("tema", ""))
    estado.salvar(est)
    print(f"Reels publicado: {media_id} — tema: {r.get('tema')}")
    return r
