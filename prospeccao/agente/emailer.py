"""Envio (SMTP) e leitura (IMAP) de e-mails da caixa da ELLO."""
import email
import imaplib
import smtplib
import ssl
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr

from . import config

CAIXA_SIMULADA: list = []   # em simulação, os e-mails "enviados" ficam aqui


def _rodape_texto() -> str:
    return (f"\n\n--\n{config.NOME_REMETENTE}\n{config.RODAPE_EMPRESA}\n"
            f"WhatsApp {config.WHATSAPP} · {config.LINK_SITE}\n\n"
            "Encontramos seu contato em fontes públicas da empresa. "
            "Se não quiser receber mais mensagens, é só responder SAIR.")


def montar(destino: str, assunto: str, corpo: str, responder_a: dict | None = None) -> EmailMessage:
    msg = EmailMessage()
    dominio = (config.EMAIL_REMETENTE.split("@")[-1] or "ello.local")
    msg["From"] = formataddr((config.NOME_REMETENTE, config.EMAIL_REMETENTE or "simulado@ello.local"))
    msg["To"] = destino
    msg["Subject"] = assunto
    msg["Message-ID"] = make_msgid(domain=dominio)
    msg["List-Unsubscribe"] = f"<mailto:{config.EMAIL_REMETENTE}?subject=SAIR>"
    if responder_a:
        msg["In-Reply-To"] = responder_a["message_id"]
        msg["References"] = responder_a.get("references", "") + " " + responder_a["message_id"]
    msg.set_content(corpo.strip() + _rodape_texto())
    return msg


def enviar(msg: EmailMessage) -> str:
    if config.SIMULAR or not config.SMTP_SENHA:
        CAIXA_SIMULADA.append(msg)
        print(f"[simulação] e-mail para {msg['To']}: {msg['Subject']}")
        return msg["Message-ID"]
    ctx = ssl.create_default_context()
    if config.SMTP_PORTA == 465:
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORTA, context=ctx, timeout=60) as s:
            s.login(config.SMTP_USUARIO, config.SMTP_SENHA)
            s.send_message(msg)
    else:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORTA, timeout=60) as s:
            s.starttls(context=ctx)
            s.login(config.SMTP_USUARIO, config.SMTP_SENHA)
            s.send_message(msg)
    _copiar_para_enviados(msg)
    return msg["Message-ID"]


def _copiar_para_enviados(msg: EmailMessage) -> None:
    """Guarda uma cópia na pasta Enviados, para você ver as conversas no seu e-mail."""
    try:
        with imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORTA) as im:
            im.login(config.SMTP_USUARIO, config.SMTP_SENHA)
            for pasta in ("Sent", "INBOX.Sent", "Enviados", "[Gmail]/Sent Mail"):
                if im.select(pasta)[0] == "OK":
                    im.append(pasta, "\\Seen", None, msg.as_bytes())
                    break
    except Exception as e:
        print(f"Aviso: não salvei cópia em Enviados ({e})")


def _texto(m: email.message.Message) -> str:
    if m.is_multipart():
        for parte in m.walk():
            if parte.get_content_type() == "text/plain" and "attachment" not in str(parte.get("Content-Disposition")):
                return parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", "replace")
        for parte in m.walk():
            if parte.get_content_type() == "text/html":
                import re
                html = parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", "replace")
                return re.sub(r"<[^>]+>", " ", html)
        return ""
    return m.get_payload(decode=True).decode(m.get_content_charset() or "utf-8", "replace")


def _limpar_citacao(texto: str) -> str:
    """Remove a parte citada do e-mail original ("Em ... escreveu:", linhas com >)."""
    linhas = []
    for l in texto.splitlines():
        if l.strip().startswith(">") or (l.strip().startswith("Em ") and "escreveu" in l) or l.strip().startswith("On ") and "wrote" in l:
            break
        if l.strip() in ("--", "-----Original Message-----", "-----Mensagem original-----"):
            break
        linhas.append(l)
    return "\n".join(linhas).strip()[:3000]


def ler_novos() -> list[dict]:
    """Devolve os e-mails não lidos da caixa de entrada (e marca como lidos)."""
    if config.SIMULAR or not config.SMTP_SENHA:
        return list(getattr(config, "_ENTRADA_SIMULADA", []))
    saida = []
    with imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORTA) as im:
        im.login(config.SMTP_USUARIO, config.SMTP_SENHA)
        im.select("INBOX")
        _, ids = im.search(None, "UNSEEN")
        for num in ids[0].split()[:200]:
            _, dados = im.fetch(num, "(RFC822)")
            m = email.message_from_bytes(dados[0][1])
            saida.append({
                "de": parseaddr(m.get("From", ""))[1].lower(),
                "nome": str(make_header(decode_header(parseaddr(m.get("From", ""))[0] or ""))),
                "assunto": str(make_header(decode_header(m.get("Subject", "")))),
                "message_id": m.get("Message-ID", ""),
                "in_reply_to": m.get("In-Reply-To", ""),
                "references": m.get("References", ""),
                "texto": _limpar_citacao(_texto(m)),
                "auto": bool(m.get("Auto-Submitted", "no") != "no" or m.get("X-Autoreply") or m.get("X-Autorespond")),
            })
            im.store(num, "+FLAGS", "\\Seen")
    return saida
