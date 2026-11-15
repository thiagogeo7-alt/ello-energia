"""Lê a caixa de entrada: classifica respostas, responde, descadastra, detecta e-mails devolvidos e reuniões marcadas."""
import json
import re

from . import claude, config, emailer, estado

SISTEMA = f"""Você cuida das respostas aos e-mails de prospecção da ELLO Energia (energia solar compartilhada,
economia de até 50% na conta de luz, sem obra, sem placas, sem investimento, mesma distribuidora).

Para cada e-mail recebido, classifique e, quando for o caso, escreva a resposta (português, até 80 palavras,
tom humano e cordial, sem assinatura, que é adicionada automaticamente):

- "interessado": quer saber mais, pediu simulação/proposta, perguntou como funciona com interesse.
  Resposta: agradeça, peça uma foto ou PDF da última conta de luz para a simulação e ofereça os caminhos:
  {"agendar uma conversa rápida pelo link " + config.LINK_AGENDA if config.LINK_AGENDA else "marcar uma conversa rápida"}
  ou chamar no WhatsApp {config.WHATSAPP}.
- "pergunta": fez uma dúvida específica. Responda com fatos da marca e convide para a simulação.
- "nao_interessado": não tem interesse agora. Resposta: agradeça em uma frase, sem insistir.
- "descadastro": pediu para sair/não receber mais. Resposta: confirme em uma frase que não enviaremos mais nada.
- "ausente": resposta automática de férias/ausência. Sem resposta.
- "outro": qualquer coisa que precise de uma pessoa (reclamação, assunto fora do tema). Sem resposta.

Os e-mails são assinados por "Claudio", o assistente virtual da ELLO. Se perguntarem se é robô, IA ou pessoa,
responda com honestidade que é o assistente virtual da ELLO e que um consultor da equipe atende na conversa.
Nunca fale de fidelidade, multa, contrato ou cancelamento por e-mail: se perguntarem, diga que há diferentes
opções e que o consultor explica tudo na conversa, e convide para agendar.
Nunca prometa valores exatos, preços ou mais de 50% de economia. Nunca peça dados pessoais além da conta de luz.

Fatos da marca:
{config.MARCA[:2000]}

Responda SOMENTE com JSON."""

BOUNCE_DE = ("mailer-daemon", "postmaster", "mail delivery", "mailerdaemon")


def _indices(crm: dict):
    por_email, por_mid = {}, {}
    for c in crm["contatos"].values():
        if c.get("email"):
            por_email[c["email"]] = c
        for e in c.get("enviados", []):
            por_mid[e.get("message_id", "")] = c
    return por_email, por_mid


def executar() -> None:
    config.exigir("EMAIL_REMETENTE", "SMTP_SENHA", "ANTHROPIC_API_KEY", "PAINEL_SENHA")
    crm = estado.carregar()
    por_email, por_mid = _indices(crm)
    entrada = emailer.ler_novos()
    if not entrada:
        print("Nenhum e-mail novo.")
        return
    pendentes = []
    mudou = False
    for m in entrada:
        texto_baixo = (m["assunto"] + " " + m["texto"]).lower()
        # 1) E-mail devolvido (endereço inexistente)
        if any(b in m["de"] or b in m.get("nome", "").lower() for b in BOUNCE_DE):
            for end in re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", m["texto"]):
                c = por_email.get(end.lower())
                if c and c["status"] in estado.STATUS_ATIVOS:
                    c["status"] = "invalido"
                    estado.evento(crm, "devolvido", c.get("segmento", ""))
                    mudou = True
            continue
        # 2) Confirmação de reunião vinda da agenda (Google Agenda / Cal.com)
        if any(p in m["assunto"].lower() for p in config.PALAVRAS_RESERVA):
            for end in re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", m["texto"] + " " + m["assunto"]):
                c = por_email.get(end.lower())
                if c:
                    c["status"] = "reuniao"
                    c.setdefault("respostas", []).append({"data": estado.iso(), "classe": "reuniao",
                                                          "resumo": "Reunião marcada pela agenda"})
                    estado.evento(crm, "reuniao", c.get("segmento", ""))
                    mudou = True
                    break
            else:
                estado.evento(crm, "reuniao", "", "reserva de contato fora da base")
                mudou = True
            continue
        # 3) Resposta de um contato da base
        c = por_mid.get(m.get("in_reply_to", "")) or por_email.get(m["de"])
        if not c:
            continue   # e-mail que não é da prospecção: fica para você na caixa de entrada
        if m.get("auto") or any(x in texto_baixo for x in ("resposta automática", "out of office", "estou ausente", "em férias")):
            estado.evento(crm, "ausente", c.get("segmento", ""))
            mudou = True
            continue
        pendentes.append((c, m))

    if pendentes:
        itens = [{"n": i, "empresa": c.get("empresa", ""), "assunto": m["assunto"], "texto": m["texto"][:1500]}
                 for i, (c, m) in enumerate(pendentes)]
        sim = {"respostas": [{"n": i, "classe": "descadastro" if "sair" in m["texto"].lower() else "interessado",
                              "resumo": m["texto"][:80], "resposta": "Obrigado pelo retorno! Pode me mandar uma foto da última conta de luz?"}
                             for i, (c, m) in enumerate(pendentes)]}
        decisoes = {d["n"]: d for d in claude.perguntar_json(
            SISTEMA, "E-mails recebidos:\n" + json.dumps(itens, ensure_ascii=False, indent=1)
            + '\n\nDevolva {"respostas": [{"n": 0, "classe": "...", "resumo": "uma frase", "resposta": "texto ou vazio"}]}',
            modelo=config.MODELO_RAPIDO, simulado=sim).get("respostas", [])}
        for i, (c, m) in enumerate(pendentes):
            d = decisoes.get(i, {"classe": "outro", "resumo": "", "resposta": ""})
            classe = d.get("classe", "outro")
            c.setdefault("respostas", []).append({"data": estado.iso(), "classe": classe,
                                                  "resumo": d.get("resumo", "")[:200], "texto": m["texto"][:600]})
            if classe == "descadastro" or re.fullmatch(r"\W*sair\W*", m["texto"].strip().lower() or "x"):
                classe = "descadastro"
                c["status"] = "descadastrado"
                crm["bloqueados"].append(c["email"])
            elif classe == "nao_interessado":
                c["status"] = "descartado"
            elif classe in ("interessado", "pergunta"):
                c["status"] = "interessado"
            else:
                c["status"] = "respondeu"
            resposta = (d.get("resposta") or "").strip()
            if resposta and classe in ("interessado", "pergunta", "nao_interessado", "descadastro"):
                assunto = m["assunto"] if m["assunto"].lower().startswith("re:") else "Re: " + m["assunto"]
                try:
                    mid = emailer.enviar(emailer.montar(m["de"], assunto, resposta,
                                                        {"message_id": m["message_id"], "references": m.get("references", "")}))
                    c["enviados"].append({"data": estado.iso(), "tipo": f"resposta_{classe}", "assunto": assunto, "message_id": mid})
                except Exception as e:
                    print(f"Falha ao responder {c['id']}: {e}")
            estado.evento(crm, f"resposta_{classe}", c.get("segmento", ""))
            mudou = True
        crm["custos"].append({"data": estado.iso(), "servico": "Claude (respostas)", "usd": round(0.003 * len(pendentes), 3)})
    if mudou:
        estado.salvar(crm)
    print(f"Processados: {len(entrada)} e-mails ({len(pendentes)} respostas de contatos).")
