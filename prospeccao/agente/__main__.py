"""Uso:  python -m agente coletar-google | coletar-cnpj | enviar | respostas | verificar
Coloque SIMULAR=1 para testar sem enviar e-mails nem gastar cota.
"""
import os
import sys

from . import config


def verificar() -> None:
    print(f"Cidade: {config.CIDADE}/{config.UF} (código Receita {config.MUNICIPIO_RECEITA})")
    for n in ("GOOGLE_MAPS_KEY", "ANTHROPIC_API_KEY", "PAINEL_SENHA", "EMAIL_REMETENTE", "SMTP_SENHA", "LINK_AGENDA"):
        print(f"{n}: {'ok ✅' if (os.getenv(n) or getattr(config, n, '')) else 'FALTANDO ❌'}")
    if config.SMTP_SENHA and config.EMAIL_REMETENTE:
        import imaplib
        import smtplib
        import ssl
        try:
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORTA, context=ssl.create_default_context(), timeout=30) as s:
                s.login(config.SMTP_USUARIO, config.SMTP_SENHA)
            print("Envio (SMTP): conectado ✅")
        except Exception as e:
            print(f"Envio (SMTP): FALHOU ❌ {e}")
        try:
            with imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORTA) as im:
                im.login(config.SMTP_USUARIO, config.SMTP_SENHA)
            print("Leitura (IMAP): conectado ✅")
        except Exception as e:
            print(f"Leitura (IMAP): FALHOU ❌ {e}")
    if config.GOOGLE_MAPS_KEY:
        from .coleta import _buscar_google
        try:
            r = _buscar_google(f"padaria em {config.CIDADE} {config.UF}")
            print(f"Google Maps: ok ✅ ({len(r)} resultados no teste — conta 1 busca da cota)")
        except Exception as e:
            print(f"Google Maps: FALHOU ❌ {e}")


def main() -> None:
    tarefa = sys.argv[1] if len(sys.argv) > 1 else ""
    if tarefa == "verificar":
        verificar()
        return
    from . import estado
    if tarefa == "coletar-google":
        from . import coleta
        crm = estado.carregar()
        coleta.coletar_google(crm)
        estado.salvar(crm)
    elif tarefa == "coletar-cnpj":
        from . import coleta
        crm = estado.carregar()
        coleta.coletar_cnpj(crm)
        estado.salvar(crm)
    elif tarefa == "enviar":
        from . import envio
        envio.executar()
    elif tarefa == "previa":
        # Mostra como ficariam os primeiros e-mails (1 por segmento). Não envia nada e não altera os dados.
        from . import emailer, envio, mensagens
        crm = estado.carregar()
        lote = envio._novos(crm, 4)
        print(f"Contatos na fila: {sum(1 for c in crm['contatos'].values() if c['status'] == 'novo')}\n")
        for (c, tipo), t in zip(lote, mensagens.escrever(lote)):
            msg = emailer.montar("(destinatário oculto)", t["assunto"], t["corpo"])
            print("=" * 70)
            print(f"Segmento: {c.get('segmento')} | Empresa: {c.get('empresa')}")
            print(f"De: {msg['From']}\nAssunto: {msg['Subject']}\n")
            print(msg.get_content())
    elif tarefa == "respostas":
        from . import respostas
        respostas.executar()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
