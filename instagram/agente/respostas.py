"""Responde comentários e mensagens diretas novas, e registra quem tem interesse."""
import json
from datetime import datetime, timedelta, timezone

from . import claude, config, estado, instagram

SISTEMA = f"""Você atende o Instagram da ELLO Energia. Responde comentários e mensagens
com simpatia, em português do Brasil, em no máximo 2 frases curtas. Siga o guia da marca.

{config.MARCA}

Como decidir:
- Pergunta ou interesse (preço, como funciona, "quero", valor da conta etc.): responda a dúvida
  em uma frase e convide para o WhatsApp {config.LINK_WHATSAPP} para receber a proposta grátis.
  Marque "interesse": true.
- Elogio ou emoji: agradeça de forma curta e variada.
- Crítica: responda com respeito, sem discutir, e ofereça ajuda no WhatsApp.
- Spam, ofensa, golpe, política ou algo sem relação: "acao": "ignorar".
- Nunca prometa valores exatos nem mais de 20% de economia. Nunca peça dados pessoais por ali.

Responda SOMENTE com JSON."""

PEDIDO = """Itens novos para avaliar (comentários e mensagens diretas):
{itens}

Devolva: {{"respostas": [{{"id": "...", "acao": "responder" ou "ignorar", "resposta": "...", "interesse": true/false}}]}}"""


def _recente(ts: str, dias: int = 7) -> bool:
    try:
        data = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
    except (TypeError, ValueError):
        return True
    return data > datetime.now(timezone.utc) - timedelta(days=dias)


DM_PALAVRA_CHAVE = (
    "Oi! Que bom que você quer economizar 😊\n\n"
    "A análise da sua conta de luz é grátis: é só mandar uma foto da sua última conta no nosso WhatsApp "
    "que em até 24h te enviamos quanto dá para economizar (até 20%%), sem obra e sem fidelidade.\n\n"
    "👉 %s" % config.LINK_WHATSAPP
)
RESPOSTAS_PUBLICAS = ["Te chamei no direct! 📩", "Mandei no seu direct! 😉", "Olha o direct! ⚡", "Já te enviei no direct! 📲"]


def _palavras_chave(est: dict) -> set[str]:
    palavras = {"ECONOMIZAR"}
    palavras |= {p["palavra_chave"].upper() for p in est["publicacoes"][-20:] if p.get("palavra_chave")}
    return palavras


def executar() -> None:
    config.exigir("IG_TOKEN", "ANTHROPIC_API_KEY")
    est = estado.carregar()
    feitos_c = set(est["comentarios_respondidos"])
    feitos_m = set(est["mensagens_respondidas"])
    eu = instagram.meu_id()
    minhas_contas = {eu}
    palavras = _palavras_chave(est)

    pendentes = []
    for media in instagram.minhas_publicacoes(limite=10):
        if not _recente(media.get("timestamp", ""), dias=30) or not media.get("comments_count", 1):
            continue
        for c in instagram.comentarios(media["id"]):
            ja_tem_resposta = bool((c.get("replies") or {}).get("data"))
            if c["id"] in feitos_c or ja_tem_resposta or not _recente(c.get("timestamp", "")):
                continue
            if set((c.get("text") or "").upper().replace("!", " ").replace(".", " ").split()) & palavras:
                # Comentou a palavra-chave: manda DM com o link e responde em público
                try:
                    instagram.resposta_privada(c["id"], DM_PALAVRA_CHAVE)
                    instagram.responder_comentario(c["id"], RESPOSTAS_PUBLICAS[len(feitos_c) % len(RESPOSTAS_PUBLICAS)])
                except Exception as e:
                    print(f"Falha na DM da palavra-chave {c['id']}: {e}")
                    continue
                feitos_c.add(c["id"])
                est["comentarios_respondidos"].append(c["id"])
                est["leads"].append({"data": estado.agora(), "origem": "instagram_palavra_chave",
                                     "usuario": c.get("username"), "mensagem": (c.get("text") or "")[:300]})
                print(f"palavra-chave de @{c.get('username')}: DM enviada")
                continue
            pendentes.append({"id": c["id"], "tipo": "comentario", "usuario": c.get("username"),
                              "texto": c.get("text", ""), "post": (media.get("caption") or "")[:120]})

    for conversa in instagram.conversas():
        msgs = (conversa.get("messages") or {}).get("data", [])
        if not msgs:
            continue
        ultima = msgs[0]   # a API devolve da mais recente para a mais antiga
        remetente = ultima.get("from", {})
        if ultima["id"] in feitos_m or remetente.get("id") in minhas_contas:
            continue
        if not _recente(ultima.get("created_time", ""), dias=1):
            continue   # a Meta só permite responder DMs dentro de 24 horas
        pendentes.append({"id": ultima["id"], "tipo": "dm", "usuario": remetente.get("username"),
                          "usuario_id": remetente.get("id"), "texto": ultima.get("message", "")})

    if not pendentes:
        print("Nada novo para responder.")
        estado.salvar(est)
        return

    itens = json.dumps([{k: v for k, v in p.items() if k != "usuario_id"} for p in pendentes],
                       ensure_ascii=False, indent=1)
    decisoes = claude.perguntar_json(
        SISTEMA, PEDIDO.format(itens=itens), modelo=config.MODELO_RAPIDO,
        simulado={"respostas": [
            {"id": p["id"], "acao": "responder", "interesse": "?" in p["texto"] or "conta" in p["texto"],
             "resposta": "Oi! Dá sim 😊 Chama a gente no WhatsApp que mandamos sua proposta grátis: " + config.LINK_WHATSAPP}
            for p in pendentes]},
    ).get("respostas", [])

    por_id = {p["id"]: p for p in pendentes}
    for d in decisoes:
        p = por_id.get(d.get("id"))
        if not p:
            continue
        try:
            if d.get("acao") == "responder" and d.get("resposta"):
                if p["tipo"] == "comentario":
                    instagram.responder_comentario(p["id"], d["resposta"])
                else:
                    instagram.enviar_mensagem(p["usuario_id"], d["resposta"])
        except Exception as e:   # um erro não pode travar as outras respostas
            print(f"Falha ao responder {p['id']}: {e}")
            continue
        (est["comentarios_respondidos"] if p["tipo"] == "comentario" else est["mensagens_respondidas"]).append(p["id"])
        if d.get("interesse"):
            est["leads"].append({"data": estado.agora(), "origem": f"instagram_{p['tipo']}",
                                 "usuario": p.get("usuario"), "mensagem": p["texto"][:300]})
        print(f"{p['tipo']} de @{p.get('usuario')}: {d.get('acao')}")

    estado.salvar(est)
