"""Responde comentários e mensagens diretas novas, e registra quem tem interesse."""
import json
from datetime import datetime, timedelta, timezone

from . import aprendizado, aviso, claude, config, estado, instagram

SISTEMA = f"""Você atende o Instagram da ELLO Energia. Responde comentários e mensagens
com simpatia, em português do Brasil, em no máximo 2 frases curtas. Siga o guia da marca.

{config.MARCA}

Como decidir (todo comentário que não for spam vira contato no WhatsApp):
- Para COMENTÁRIOS que não forem spam, escreva duas coisas:
  "resposta": resposta pública curta (até 1 frase) avisando que mandou no direct, variando o texto
    (ex.: "Te mandei no direct! 📩", "Olha seu direct 😉"). Para elogios, agradeça e avise do direct.
  "dm": mensagem privada de 1 a 3 frases: responda a dúvida (se houver) e convide para o WhatsApp,
    onde a análise da conta é grátis. NÃO coloque o link: ele é adicionado automaticamente.
- Para MENSAGENS DIRETAS (tipo "dm"): "resposta" responde a dúvida em até 2 frases e convida para o WhatsApp.
  NÃO coloque o link: a mensagem já vai com o botão "{config.BOTAO_WHATSAPP}" que abre o WhatsApp.
- "interesse": true quando houver pergunta ou interesse (preço, como funciona, "quero", valor da conta etc.).
- Crítica: responda com respeito, sem discutir, e ofereça ajuda no WhatsApp.
- Spam, ofensa, golpe, política ou algo sem relação: "acao": "ignorar".
- Nunca prometa valores exatos nem mais de 50% de economia. Nunca peça dados pessoais por ali.

Responda SOMENTE com JSON."""

PEDIDO = """Itens novos para avaliar (comentários e mensagens diretas):
{itens}

Devolva: {{"respostas": [{{"id": "...", "acao": "responder" ou "ignorar", "resposta": "...", "dm": "... (só para comentários)", "interesse": true/false}}]}}"""


def _recente(ts: str, dias: int = 7) -> bool:
    try:
        data = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
    except (TypeError, ValueError):
        return True
    return data > datetime.now(timezone.utc) - timedelta(days=dias)


def _dm_palavra_chave(ref: str) -> str:
    """Direct da palavra-chave com o código do post no link do WhatsApp."""
    return DM_PALAVRA_CHAVE.replace(config.LINK_WHATSAPP_IG, config.link_whatsapp_ref(ref))


def _contar_lead(est: dict, media_id: str) -> None:
    for pub in est["publicacoes"]:
        if pub.get("media_id") == media_id:
            pub["leads"] = pub.get("leads", 0) + 1


DM_PALAVRA_CHAVE = (
    "Oi! Que bom que você quer economizar 😊\n\n"
    "A análise da sua conta de luz é grátis: é só mandar uma foto da sua última conta no nosso WhatsApp "
    "que em até 24h te enviamos quanto dá para economizar (até 50%%), sem obra e sem placas no telhado.\n\n"
    "👉 %s" % config.LINK_WHATSAPP_IG
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
    refs = estado.refs_por_media(est)
    novos_leads = []

    pendentes = []
    for media in instagram.minhas_publicacoes(limite=10):
        if not _recente(media.get("timestamp", ""), dias=30) or not media.get("comments_count", 1):
            continue
        ref = refs.get(media["id"], "")
        for c in instagram.comentarios(media["id"]):
            ja_tem_resposta = bool((c.get("replies") or {}).get("data"))
            if c["id"] in feitos_c or ja_tem_resposta or not _recente(c.get("timestamp", "")):
                continue
            if set((c.get("text") or "").upper().replace("!", " ").replace(".", " ").split()) & palavras:
                # Comentou a palavra-chave: manda DM com o link e responde em público
                try:
                    try:
                        instagram.resposta_privada(c["id"], _dm_palavra_chave(ref), link=config.link_whatsapp_ref(ref))
                        publica = RESPOSTAS_PUBLICAS[len(feitos_c) % len(RESPOSTAS_PUBLICAS)]
                    except Exception as e:
                        print(f"Direct indisponível para {c['id']} ({e}); WhatsApp vai na resposta pública")
                        publica = ("Que bom! 😊 A análise da sua conta é grátis: manda uma foto dela no nosso "
                                   f"WhatsApp {config.WHATSAPP_LEGIVEL} 📲")
                    instagram.responder_comentario(c["id"], publica)
                except Exception as e:
                    print(f"Falha ao responder a palavra-chave {c['id']}: {e}")
                    continue
                feitos_c.add(c["id"])
                est["comentarios_respondidos"].append(c["id"])
                est["leads"].append({"data": estado.agora(), "origem": "instagram_palavra_chave", "post": ref,
                                     "usuario": c.get("username"), "mensagem": (c.get("text") or "")[:300]})
                _contar_lead(est, media["id"])
                novos_leads.append(f"@{c.get('username')} comentou a palavra-chave no post {ref or '?'}: "
                                   f"\"{(c.get('text') or '')[:120]}\"")
                estado.registrar(est, "dm_palavra_chave", f"DM automática com o WhatsApp (post {ref})" if ref
                                 else "DM automática com o WhatsApp")
                print(f"palavra-chave de @{c.get('username')}: DM enviada")
                continue
            pendentes.append({"id": c["id"], "tipo": "comentario", "usuario": c.get("username"), "ref": ref,
                              "media_id": media["id"], "texto": c.get("text", ""),
                              "post": (media.get("caption") or "")[:120]})

    try:
        lista_conversas = instagram.conversas()
    except Exception as e:   # DMs podem exigir a revisão do app pela Meta; comentários seguem funcionando
        print(f"Aviso: não consegui ler as DMs ({e})")
        lista_conversas = []
    for conversa in lista_conversas:
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
        _avisar(novos_leads)
        aprendizado.atualizar_metricas_do_dia(est)
        estado.salvar(est)
        return

    itens = json.dumps([{k: v for k, v in p.items() if k not in ("usuario_id", "media_id", "ref")} for p in pendentes],
                       ensure_ascii=False, indent=1)
    decisoes = claude.perguntar_json(
        SISTEMA, PEDIDO.format(itens=itens), modelo=config.MODELO_RAPIDO,
        simulado={"respostas": [
            {"id": p["id"], "acao": "responder", "interesse": "?" in p["texto"] or "conta" in p["texto"],
             "resposta": "Te mandei no direct! 📩", "dm": "Oi! Dá sim 😊 Chama a gente no WhatsApp que mandamos sua análise grátis."}
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
                    # Manda o WhatsApp no direct e avisa em público; se o direct falhar, o número vai na resposta pública
                    dm = (d.get("dm") or "A análise da sua conta de luz é grátis pelo nosso WhatsApp 😊").strip()
                    try:
                        instagram.resposta_privada(p["id"], dm, link=config.link_whatsapp_ref(p.get("ref", "")))
                        publica = d["resposta"]
                        estado.registrar(est, "dm_whatsapp", "Botão do WhatsApp enviado no direct")
                    except Exception as e:
                        print(f"Direct indisponível para {p['id']} ({e}); WhatsApp vai na resposta pública")
                        publica = f"{dm} Chama no WhatsApp: {config.WHATSAPP_LEGIVEL} 📲"
                    instagram.responder_comentario(p["id"], publica)
                else:
                    instagram.enviar_mensagem(p["usuario_id"], d["resposta"], link=config.LINK_WHATSAPP_IG)
        except Exception as e:   # um erro não pode travar as outras respostas
            print(f"Falha ao responder {p['id']}: {e}")
            continue
        (est["comentarios_respondidos"] if p["tipo"] == "comentario" else est["mensagens_respondidas"]).append(p["id"])
        if d.get("interesse"):
            est["leads"].append({"data": estado.agora(), "origem": f"instagram_{p['tipo']}", "post": p.get("ref", ""),
                                 "usuario": p.get("usuario"), "mensagem": p["texto"][:300]})
            if p.get("media_id"):
                _contar_lead(est, p["media_id"])
            onde = f"no post {p['ref']}" if p.get("ref") else "no direct"
            novos_leads.append(f"@{p.get('usuario')} demonstrou interesse {onde}: \"{p['texto'][:120]}\"")
        if d.get("acao") == "responder":
            estado.registrar(est, "resposta_" + p["tipo"], "interessado" if d.get("interesse") else "")
        print(f"{p['tipo']} de @{p.get('usuario')}: {d.get('acao')}")

    _avisar(novos_leads)
    aprendizado.atualizar_metricas_do_dia(est)
    estado.salvar(est)


def _avisar(novos_leads: list[str]) -> None:
    """Manda um e-mail para a equipe quando aparecem interessados novos."""
    if novos_leads:
        aviso.enviar(f"{len(novos_leads)} interessado(s) novo(s) no Instagram",
                     "Novos interessados no Instagram da ELLO:\n\n- " + "\n- ".join(novos_leads)
                     + "\n\nEles receberam o link do WhatsApp com o código do post (ex.: ref R17).")

