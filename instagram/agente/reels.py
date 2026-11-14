"""Cria e publica o Reels de 10 segundos com vídeo gerado por IA."""
from . import aprendizado, claude, config, estado, instagram, video

SISTEMA = f"""Você é o estrategista de conteúdo e diretor de vídeo do Instagram da ELLO Energia.
Seu trabalho é criar Reels de 10 segundos que prendam a atenção no primeiro segundo e
façam as pessoas compartilharem e salvarem. Siga à risca o guia da marca abaixo.

{config.MARCA}

Formatos que costumam viralizar em Reels curtos (use como inspiração, varie):
- Contraste visual forte: antes x depois, noite x dia, caro x barato.
- Movimento de câmera hipnótico: drone revelando uma usina solar ao amanhecer, travelling lento.
- Situação do dia a dia com tensão: a conta de luz chegando, o ar-condicionado ligado no calor.
- Satisfatório: luz do sol varrendo painéis, sombra de nuvem passando sobre a usina.
- Curiosidade: uma imagem que faz a pessoa perguntar "como assim?".

Responda SOMENTE com um JSON válido."""

PEDIDO = """Crie o próximo Reels da ELLO.

O que já sabemos do desempenho da conta:
{historico}

Estratégia: cerca de 70% das vezes faça uma variação nova do que melhor funcionou;
30% das vezes teste um tema ou formato diferente. Decida e diga qual fez.

Devolva este JSON:
{{
  "estrategia": "variacao" ou "teste",
  "tema": "tema curto em português",
  "gancho": "a ideia do primeiro segundo, em português",
  "prompt_video": "prompt em INGLÊS para o modelo de vídeo: uma cena vertical 9:16 de {segundos} segundos, ultra-realista, cinematográfica, descrevendo assunto, ambiente, luz, movimento de câmera e o que acontece segundo a segundo. Sem texto na tela, sem logotipos, sem pessoas reais famosas. Se houver pessoas, devem ser genéricas e naturais.",
  "legenda": "legenda em português: 1ª linha é um gancho forte (até 8 palavras), depois 2 a 4 linhas curtas, chamada para ação, a linha obrigatória sobre vídeo com IA, e 3 a 5 hashtags no fim"
}}"""


def executar() -> dict:
    config.exigir("IG_TOKEN", "ANTHROPIC_API_KEY", "FAL_KEY")
    est = estado.carregar()

    aprendizado.atualizar_metricas(est)
    historico = aprendizado.resumo_para_claude(est, "reel")

    ideia = claude.perguntar_json(
        SISTEMA, PEDIDO.format(historico=historico, segundos=config.VIDEO_SEGUNDOS),
        simulado={
            "estrategia": "teste", "tema": "Usina solar ao amanhecer",
            "gancho": "O sol nascendo e virando desconto na conta",
            "prompt_video": "Vertical 9:16 cinematic drone shot at sunrise over a vast solar farm near Campinas...",
            "legenda": "Seu telhado não precisa de placa.\nO sol trabalha na usina, o desconto vem na sua conta.\nSimule sua economia no link da bio.\n🎬 Vídeo criado com inteligência artificial.\n#energiasolar #campinas #contadeluz",
        })

    legenda = ideia["legenda"]
    if "inteligência artificial" not in legenda.lower():
        legenda += "\n\n🎬 Vídeo criado com inteligência artificial."

    url = video.gerar(ideia["prompt_video"])
    est["custos"].append({"data": estado.agora(), "servico": "fal.ai vídeo", "usd": video.custo_estimado()})
    estado.salvar(est)   # salva o custo mesmo se a publicação falhar

    media_id = instagram.publicar_reel(url, legenda)

    est["publicacoes"].append({
        "data": estado.agora(), "tipo": "reel", "estrategia": ideia.get("estrategia"),
        "tema": ideia.get("tema"), "gancho": ideia.get("gancho"),
        "prompt": ideia["prompt_video"], "legenda": legenda, "video_url": url, "media_id": media_id,
    })
    estado.salvar(est)
    print(f"Reels publicado: {media_id} — tema: {ideia.get('tema')}")
    return ideia
