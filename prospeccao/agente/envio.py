"""Envio diário: lembretes primeiro, depois primeiros contatos, respeitando o aquecimento da caixa de e-mail."""
import re
from datetime import datetime, timedelta

from . import config, emailer, estado, mensagens
from .segmentos import SEGMENTOS


def limite_hoje(crm: dict) -> int:
    """Aquecimento: 10/dia na 1ª semana, 20/dia na 2ª, depois o limite configurado (30)."""
    dias = sorted(crm["envios_por_dia"])
    if not dias:
        return min(10, config.LIMITE_DIA)
    idade = (datetime.now().date() - datetime.fromisoformat(dias[0]).date()).days
    if idade < 7:
        return min(10, config.LIMITE_DIA)
    if idade < 14:
        return min(20, config.LIMITE_DIA)
    return config.LIMITE_DIA


def _devidos(crm: dict) -> list[tuple[dict, str]]:
    agora = estado.agora()
    fila = []
    for c in crm["contatos"].values():
        if c["status"] == "enviado" and c["enviados"]:
            ultimo = datetime.fromisoformat(c["enviados"][-1]["data"])
            if agora - ultimo >= timedelta(days=config.DIAS_FOLLOWUP[0]):
                fila.append((c, "lembrete1"))
        elif c["status"] == "lembrete1" and c["enviados"]:
            ultimo = datetime.fromisoformat(c["enviados"][-1]["data"])
            if agora - ultimo >= timedelta(days=config.DIAS_FOLLOWUP[1] - config.DIAS_FOLLOWUP[0]):
                fila.append((c, "lembrete2"))
    return fila


# Empresas em recuperação judicial, falência ou liquidação não recebem prospecção
EVITAR = re.compile(r"recupera[cç][aã]o judicial|fal[eê]ncia|falid[ao]|em liquida[cç][aã]o", re.I)


def _novos(crm: dict, n: int) -> list[tuple[dict, str]]:
    """Distribui os primeiros contatos entre os segmentos e prefere e-mails vindos do site da empresa."""
    por_seg = {k: [] for k in SEGMENTOS}
    for c in crm["contatos"].values():
        if c["status"] == "novo" and not EVITAR.search(c.get("empresa") or ""):
            por_seg.setdefault(c.get("segmento") or "comercio", []).append(c)
    for lst in por_seg.values():
        lst.sort(key=lambda c: (c.get("fonte") != "site", c.get("criado", "")))
    escolhidos = []
    while len(escolhidos) < n and any(por_seg.values()):
        for lst in por_seg.values():
            if lst and len(escolhidos) < n:
                escolhidos.append((lst.pop(0), "inicial"))
    return escolhidos


def executar(metade: bool = True) -> int:
    config.exigir("EMAIL_REMETENTE", "SMTP_SENHA", "ANTHROPIC_API_KEY", "PAINEL_SENHA")
    if datetime.now().weekday() >= 5:
        print("Fim de semana: não enviamos e-mails de prospecção.")
        return 0
    crm = estado.carregar()
    hoje = datetime.now().date().isoformat()
    ja = crm["envios_por_dia"].get(hoje, 0)
    total = limite_hoje(crm)
    cota = (total + 1) // 2 if metade and ja == 0 else total - ja   # 2 rodadas por dia (manhã e tarde)
    cota = max(0, min(cota, total - ja))
    if cota == 0:
        print(f"Limite de hoje já atingido ({ja}/{total}).")
        return 0
    lote = _devidos(crm)[:cota]
    lote += _novos(crm, cota - len(lote))
    textos = mensagens.escrever(lote)
    enviados = 0
    for (c, tipo), t in zip(lote, textos):
        responder = None
        if tipo != "inicial" and c["enviados"]:
            responder = {"message_id": c["enviados"][-1]["message_id"]}
        try:
            mid = emailer.enviar(emailer.montar(c["email"], t["assunto"], t["corpo"], responder))
        except Exception as e:
            print(f"Falha ao enviar para {c['id']}: {e}")
            c["status"] = "erro"
            continue
        c["enviados"].append({"data": estado.iso(), "tipo": tipo, "assunto": t["assunto"], "message_id": mid})
        c["status"] = {"inicial": "enviado", "lembrete1": "lembrete1", "lembrete2": "lembrete2"}[tipo]
        enviados += 1
        estado.evento(crm, f"envio_{tipo}", c.get("segmento", ""))
    crm["envios_por_dia"][hoje] = ja + enviados
    if enviados:
        crm["custos"].append({"data": estado.iso(), "servico": "Claude (e-mails)", "usd": round(0.002 * enviados, 3)})
    # Quem recebeu o último lembrete há mais de 7 dias sem responder sai da fila
    for c in crm["contatos"].values():
        if c["status"] == "lembrete2" and c["enviados"]:
            if estado.agora() - datetime.fromisoformat(c["enviados"][-1]["data"]) > timedelta(days=7):
                c["status"] = "sem_resposta"
    estado.salvar(crm)
    print(f"Enviados hoje: {ja + enviados}/{total} ({enviados} nesta rodada).")
    return enviados
