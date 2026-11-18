"""Avisos por e-mail para a equipe (só biblioteca padrão).

Usa a mesma caixa de e-mail da prospecção (segredo SMTP_SENHA, variável EMAIL_REMETENTE).
Destino: variável ALERTA_EMAIL no GitHub; se não existir, a própria caixa comercial.
Nunca derruba o agente: se o envio falhar, só escreve um aviso no registro.

Uso pelo terminal (passo "se falhar" dos workflows):
  python3 scripts/alerta.py "assunto" "texto"
"""
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formataddr, make_msgid


def enviar(assunto: str, texto: str) -> bool:
    if os.getenv("SIMULAR") == "1":
        print(f"[simulação] aviso: {assunto}")
        return False
    senha = os.getenv("SMTP_SENHA", "")
    remetente = os.getenv("EMAIL_REMETENTE") or "comercial@elloeconomia-energia.com"
    destino = os.getenv("ALERTA_EMAIL") or remetente
    if not senha:
        print("Aviso por e-mail não enviado: falta o segredo SMTP_SENHA neste workflow.")
        return False
    msg = EmailMessage()
    msg["From"] = formataddr(("Agente ELLO", remetente))
    msg["To"] = destino
    msg["Subject"] = f"[Agente ELLO] {assunto}"
    msg["Message-ID"] = make_msgid(domain=remetente.split("@")[-1])
    msg.set_content(texto + "\n\nPainel: https://elloeconomia-energia.com/painel/\n")
    host = os.getenv("SMTP_HOST") or "smtp.hostinger.com"
    porta = int(os.getenv("SMTP_PORTA") or "465")
    usuario = os.getenv("SMTP_USUARIO") or remetente
    try:
        ctx = ssl.create_default_context()
        if porta == 465:
            with smtplib.SMTP_SSL(host, porta, context=ctx, timeout=30) as s:
                s.login(usuario, senha)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, porta, timeout=30) as s:
                s.starttls(context=ctx)
                s.login(usuario, senha)
                s.send_message(msg)
        print(f"Aviso enviado para a equipe: {assunto}")
        return True
    except Exception as e:   # o aviso nunca pode travar o agente
        print(f"Não consegui enviar o aviso por e-mail ({e})")
        return False


if __name__ == "__main__":
    enviar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
