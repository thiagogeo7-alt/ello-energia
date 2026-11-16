"""Cria e publica o Reels da ELLO (20–30 s).

Rodízio de formatos (diálogo entre duas pessoas, explicativo com desenhos, reação) e de argumentos
(planeta e bolso, como funciona, sem obra, comércio...). Cada cena é uma imagem gerada por IA com
movimento de câmera e textos por cima, seguida da tela da marca.
"""
import tempfile
from datetime import datetime
from pathlib import Path

from . import aprendizado, claude, config, dados_git, estado, instagram, montagem, video

FORMATOS = ["dialogo", "explicativo", "reacao"]
ARGUMENTOS = [
    "Planeta e bolso: energia limpa do sol, menos CO₂, e economia de até 50% na conta",
    "Bolso: a conta de luz alta pesando no orçamento da casa",
    "Como funciona: usina solar gera energia, ela entra na rede e vira crédito na sua conta",
    "Sem obra e sem placa: serve para apartamento, casa alugada ou quem não tem telhado",
    "Comércio: energia é custo fixo e economizar nela sobra dinheiro todo mês",
    "Mesma distribuidora: nada muda na rotina, a economia aparece direto na fatura",
    "Condomínio: áreas comuns, elevador e portaria com conta menor para todos",
    "Mitos x verdades: precisa de placa? é caro? muda a distribuidora?",
]

ESTILO_FOTO = ("ultra-realistic vertical photo, professional photography, 35mm lens, natural light, realistic skin "
               "and textures, generic non-famous people, Brazilian setting, no text, no captions, no logos")
ESTILO_DESENHO = ("clean flat vector illustration, simple friendly explainer style, navy blue (#0E2240) and golden "
                  "yellow (#F5B731) palette with white, soft shadows, vertical composition, centered subject, "
                  "lots of empty space in the lower third, absolutely no text, no letters, no numbers, no logos")

SISTEMA = f"""Você é o roteirista e diretor de vídeo do Instagram da ELLO Energia.
Cada Reels tem de 20 a 30 segundos: 3 cenas de ~4 s (imagens geradas por IA com movimento de câmera
e textos por cima) e depois a tela da marca, montada automaticamente.

Formatos:
- "dialogo": duas pessoas conversando (vizinhas, casal, sócios, síndico e morador, amigos no café...).
  Uma conta o problema, a outra conta a solução (ELLO). Cada cena mostra AS DUAS PESSOAS juntas no mesmo
  ambiente, e o texto da cena é a fala de quem está falando (A ou B). Descreva as duas pessoas sempre do
  mesmo jeito em todas as cenas (idade, cabelo, roupa, ambiente) para parecerem as mesmas.
- "explicativo": desenhos simples explicando o negócio passo a passo (ex.: sol → usina solar → rede da
  distribuidora → crédito na conta → economia e planeta mais limpo). Cada cena é uma ilustração e o texto
  é a legenda curta do passo. Nas ilustrações, NUNCA peça texto escrito (o texto é colocado depois).
- "reacao": uma pessoa com emoção forte e humor leve (ex.: susto com a conta) e, nas cenas seguintes,
  a virada (alívio, conta menor, sorriso). O texto da cena é uma legenda curta.

Siga à risca o guia da marca abaixo.

{config.MARCA}

Responda SOMENTE com um JSON válido."""

PEDIDO = """Crie o próximo Reels da ELLO.

FORMATO OBRIGATÓRIO: {formato}
ARGUMENTO PRINCIPAL OBRIGATÓRIO: {argumento}

O que já sabemos do desempenho da conta:
{historico}

Seja criativo e diferente dos temas recentes: varie personagens (idade, gênero, aparência) e ambientes
(cozinha, sala, varanda, escritório, padaria, salão, academia, portaria de condomínio, café).

Devolva este JSON:
{{
  "estrategia": "variacao" ou "teste",
  "formato": "{formato}",
  "argumento": "o argumento usado, em poucas palavras",
  "tema": "tema curto em português",
  "gancho": "a ideia do vídeo em uma frase",
  "nomes": ["nome da pessoa A", "nome da pessoa B"] (só no formato dialogo; nomes brasileiros comuns),
  "texto_topo_1": "1ª linha da pergunta-gancho, MAIÚSCULAS, até 18 caracteres",
  "texto_topo_2": "2ª linha, MAIÚSCULAS, até 16 caracteres",
  "cenas": [
    {{
      "prompt_imagem": "prompt em INGLÊS do PRIMEIRO QUADRO da cena (foto realista nos formatos dialogo/reacao; ilustração no explicativo)",
      "movimento": "prompt em INGLÊS do que ACONTECE na cena em vídeo de 3 a 5 s: uma ação contínua e clara (gestos, expressões, quem está falando, objetos se mexendo) e o movimento da câmera. No dialogo, diga quem fala (ex.: 'the woman on the left talks to her neighbor, gesturing with the bill'). No explicativo, anime o desenho (sol brilhando, energia fluindo pelos fios, números caindo). Sem texto na tela.",
      "quem": "A" ou "B" (só no dialogo),
      "texto": "fala, passo ou legenda em português, até 55 caracteres (cabe em ~3,5 s falando). ESTE TEXTO SERÁ FALADO EM VOZ ALTA: escreva como as pessoas falam de verdade, natural, com emoção (sem siglas difíceis; escreva números por extenso quando ajudar a leitura, ex.: 'seiscentos reais')",
      "destaque": "opcional: etiqueta vermelha curta (ex.: valor de conta fictício), até 12 caracteres"
    }}
  ] (exatamente 3 cenas),
  "virada": "frase final curta, MAIÚSCULAS, até 14 caracteres",
  "vozes": {{"A": "voz da pessoa A", "B": "voz da pessoa B", "narrador": "voz do narrador"}} — escolha da lista: {vozes}. Combine com idade e gênero dos personagens (no dialogo A e B; nos outros formatos o narrador lê os textos das cenas),
  "trilha": "prompt em INGLÊS para uma música instrumental de fundo de 30 s que combine com o clima do vídeo (gênero, instrumentos, andamento, energia); varie bastante entre os vídeos (ex.: brazilian bossa nova acoustic guitar, upbeat funk carioca beat, lo-fi chill, sunny tropical house, warm acoustic pop, light comedic pizzicato). Sem voz/vocals.",
  "palavra_chave": "UMA palavra para comentar, MAIÚSCULAS (padrão: ECONOMIZAR)",
  "beneficios": ["4 itens da lista de benefícios aprovados do guia da marca"],
  "legenda": "legenda em português: 1ª linha gancho forte, 2 a 3 linhas curtas, convite para comentar a palavra-chave, a linha obrigatória sobre vídeo com IA, e 3 a 5 hashtags"
}}"""

SIMULADO = {
    "estrategia": "teste", "formato": "dialogo", "argumento": "Planeta e bolso",
    "tema": "Vizinhas no portão falando da conta", "gancho": "Uma vizinha conta como economizou e ainda ajuda o planeta",
    "nomes": ["Rita", "Bia"], "texto_topo_1": "ECONOMIA PRO", "texto_topo_2": "PLANETA E BOLSO",
    "cenas": [
        {"prompt_imagem": "two Brazilian women neighbors chatting at a house gate, one worried holding a bill", "quem": "A",
         "texto": "Bia, minha conta veio R$ 640 de novo!", "destaque": "R$ 640"},
        {"prompt_imagem": "same two women, the second one smiling and showing her phone", "quem": "B",
         "texto": "A minha caiu! Energia solar sem placa, pela ELLO."},
        {"prompt_imagem": "same two women laughing, sunny street", "quem": "B",
         "texto": "Energia limpa do sol e até 50% de economia."},
    ],
    "virada": "TEM JEITO!", "palavra_chave": "ECONOMIZAR",
    "beneficios": ["Análise da conta GRÁTIS", "Economia de até 50% na conta",
                   "Economia limpa pro planeta", "Sem obra e sem placa no telhado"],
    "legenda": "Economia pro planeta e pro bolso ☀️\nEnergia solar sem placa no telhado.\nComente ECONOMIZAR.\n🎬 Vídeo criado com inteligência artificial.\n#energiasolar #energialimpa #campinas",
}


def _escolher(est: dict) -> tuple[str, str]:
    """Rodízio: não repete o formato do último Reels nem os 3 últimos argumentos."""
    reels = [p for p in est["publicacoes"] if p.get("tipo") == "reel"]
    ult_formato = next((p.get("formato") for p in reversed(reels) if p.get("formato")), "reacao")
    formato = FORMATOS[(FORMATOS.index(ult_formato) + 1) % len(FORMATOS)] if ult_formato in FORMATOS else FORMATOS[0]
    usados = [p.get("argumento_base") for p in reels[-3:]]
    livres = [a for a in ARGUMENTOS if a not in usados]
    argumento = livres[len(reels) % len(livres)] if livres else ARGUMENTOS[0]
    return formato, argumento


def executar(cena_local: str | None = None) -> dict:
    config.exigir("IG_TOKEN", "ANTHROPIC_API_KEY", "FAL_KEY")
    est = estado.carregar()

    aprendizado.atualizar_metricas(est)
    historico = aprendizado.resumo_para_claude(est, "reel")
    formato, argumento = _escolher(est)
    formato = __import__("os").getenv("FORMATO", "").strip() or formato
    lista_vozes = "; ".join(f"{k} ({v})" for k, v in video.VOZES.items())
    pedido = PEDIDO.format(historico=historico, formato=formato, argumento=argumento, vozes=lista_vozes)
    tema = __import__("os").getenv("TEMA", "").strip()
    if tema:
        pedido += f"\n\nTEMA OBRIGATÓRIO deste Reels (use exatamente esta ideia): {tema}"
    r = claude.perguntar_json(SISTEMA, pedido, simulado=SIMULADO)
    r["formato"] = formato
    r["cenas"] = (r.get("cenas") or [])[:3]
    if len(r["cenas"]) < 2:
        raise RuntimeError(f"Roteiro com poucas cenas: {r.get('cenas')}")

    r["palavra_chave"] = (r.get("palavra_chave") or "ECONOMIZAR").split()[0].upper()
    legenda = r["legenda"]
    if "inteligência artificial" not in legenda.lower():
        legenda += "\n\n🎬 Vídeo criado com inteligência artificial."

    # 1) Primeiro quadro de cada cena (foto realista ou desenho)
    estilo = ESTILO_DESENHO if formato == "explicativo" else ESTILO_FOTO
    falas = [None] * len(r["cenas"])
    if cena_local:
        imagens = [cena_local] * len(r["cenas"])
    else:
        imagens = [video.gerar_imagem(f"{c.get('prompt_imagem', '')}. {estilo}") for c in r["cenas"]]
        est["custos"].append({"data": estado.agora(), "servico": f"fal.ai imagens ({len(imagens)} cenas)",
                              "usd": round(video.CUSTO_IMAGEM_USD * len(imagens), 2)})
        estado.salvar(est)   # registra o custo mesmo se algo falhar depois

    if not cena_local and not config.SIMULAR:
        # 2) Vozes realistas (diálogo: A e B; outros formatos: narrador)
        vozes = r.get("vozes") or {}
        caracteres = 0
        for i, c in enumerate(r["cenas"]):
            texto = (c.get("texto") or "").strip()
            if not texto:
                continue
            voz = vozes.get(c.get("quem")) if formato == "dialogo" else vozes.get("narrador")
            try:
                falas[i] = video.gerar_fala(texto, voz or "Friendly_Person")
                caracteres += len(texto)
            except Exception as e:
                print(f"Aviso: fala não gerada ({e})")
        if caracteres:
            est["custos"].append({"data": estado.agora(), "servico": "fal.ai vozes",
                                  "usd": round(caracteres / 1000 * video.CUSTO_FALA_USD_POR_1000, 3)})

        # 3) Cada cena vira vídeo de verdade (no diálogo, a boca acompanha a fala)
        segundos_total = 0.0
        for i, c in enumerate(r["cenas"]):
            dur_fala = video.duracao_audio(falas[i]) if falas[i] else 0.0
            segundos = max(3.0, min(4.5, dur_fala + 0.4))
            audio_sync = falas[i] if formato == "dialogo" and falas[i] and dur_fala >= 2 else None
            try:
                imagens[i] = video.animar_imagem(imagens[i], c.get("movimento") or c.get("prompt_imagem", ""),
                                                 segundos, audio_sync)
                segundos_total += segundos + 0.4
            except Exception as e:
                print(f"Aviso: cena {i + 1} ficou como foto animada ({e})")
        if segundos_total:
            est["custos"].append({"data": estado.agora(), "servico": "fal.ai vídeo das cenas (H3 Turbo)",
                                  "usd": round(segundos_total * video.PRECO_VIDEO_CENA_USD_S, 2)})
        estado.salvar(est)

    trilha = None
    if not cena_local and not config.SIMULAR:
        try:
            trilha = video.gerar_trilha(f"{r.get('trilha') or 'upbeat warm acoustic pop'}, instrumental, no vocals", 30)
            est["custos"].append({"data": estado.agora(), "servico": "fal.ai trilha", "usd": video.CUSTO_TRILHA_USD})
        except Exception as e:
            print(f"Aviso: não consegui gerar a trilha ({e}); usando a padrão")
        estado.salvar(est)   # registra o custo mesmo se algo falhar depois

    if config.SIMULAR and not cena_local:
        print("[simulação] sem imagens reais para montar; pulando a montagem.")
        urls = [f"{config.URL_MIDIA_BASE}/reel-simulado.mp4", f"{config.URL_MIDIA_BASE}/reel-simulado.jpg"]
    else:
        # 2) Montagem: cenas com textos + tela da marca
        nome = f"reel-{datetime.now().strftime('%Y%m%d-%H%M')}"
        destino = Path(tempfile.mkdtemp()) / f"{nome}.mp4"
        montagem.montar_roteiro(imagens, r, destino, trilha=trilha, falas=falas)
        print(f"Vídeo montado: {destino}")
        if config.SIMULAR or __import__("os").getenv("PREVIA") == "1":
            pasta = Path(__file__).resolve().parent.parent / "previa"
            pasta.mkdir(exist_ok=True)
            for arq in (destino, destino.with_suffix(".jpg")):
                __import__("shutil").copy(arq, pasta / arq.name)
            (pasta / "roteiro.json").write_text(__import__("json").dumps(r, ensure_ascii=False, indent=2))
            print(f"Prévia pronta (não publicada): {pasta}")
            return r
        # 3) Deixa o vídeo e a capa públicos para o Instagram buscar
        urls = dados_git.publicar_midia([destino, destino.with_suffix(".jpg")])

    media_id = instagram.publicar_reel(urls[0], legenda, capa_url=urls[1])

    est["publicacoes"].append({
        "data": estado.agora(), "tipo": "reel", "estrategia": r.get("estrategia"),
        "formato": formato, "argumento": r.get("argumento"), "argumento_base": argumento,
        "tema": r.get("tema"), "gancho": r.get("gancho"), "palavra_chave": r["palavra_chave"],
        "textos": [r.get("texto_topo_1"), r.get("texto_topo_2")] + [c.get("texto") for c in r["cenas"]] + [r.get("virada")],
        "legenda": legenda, "media_id": media_id, "permalink": instagram.permalink(media_id),
        "modo": "cenas",
    })
    est["custos"].append({"data": estado.agora(), "servico": "Claude (texto)", "usd": 0.03})
    estado.registrar(est, "reel", f"{r.get('tema', '')} ({formato})")
    estado.salvar(est)
    print(f"Reels publicado: {media_id} — {formato} — tema: {r.get('tema')}")
    return r
