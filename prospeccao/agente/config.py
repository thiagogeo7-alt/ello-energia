"""Configurações do agente de prospecção (lidas dos segredos e variáveis do GitHub)."""
import os
from pathlib import Path

for _n in ("ANTHROPIC_API_KEY", "GOOGLE_MAPS_KEY", "SMTP_SENHA", "PAINEL_SENHA"):
    if os.getenv(_n):
        os.environ[_n] = os.environ[_n].strip().strip('"').strip("'")

RAIZ = Path(__file__).resolve().parent.parent
MARCA = (RAIZ.parent / "instagram" / "marca.md").read_text(encoding="utf-8")
SIMULAR = (os.getenv("SIMULAR") or "0") == "1"

# Claude
ANTHROPIC_API_KEY = (os.getenv("ANTHROPIC_API_KEY") or "")
MODELO_CRIATIVO = (os.getenv("MODELO_CRIATIVO") or "claude-sonnet-5-5")
MODELO_RAPIDO = (os.getenv("MODELO_RAPIDO") or "claude-haiku-5-5")

# Coleta
GOOGLE_MAPS_KEY = (os.getenv("GOOGLE_MAPS_KEY") or "")
BUSCAS_GOOGLE_POR_MES = int((os.getenv("BUSCAS_GOOGLE_POR_MES") or "900"))   # cota grátis: 1.000/mês
CIDADE = (os.getenv("CIDADE") or "Campinas")
UF = (os.getenv("UF") or "SP")
MUNICIPIO_RECEITA = (os.getenv("MUNICIPIO_RECEITA") or "6291")             # código da Receita (TOM) de Campinas
RECEITA_BASE = (os.getenv("RECEITA_BASE") or "https://arquivos.receitafederal.gov.br/public.php/webdav")
RECEITA_TOKEN = (os.getenv("RECEITA_TOKEN") or "YggdBLfdninEJX9")   # compartilhamento público da Receita (WebDAV)

# E-mail (preenchidos quando o domínio e a caixa de e-mail existirem)
EMAIL_REMETENTE = (os.getenv("EMAIL_REMETENTE") or "comercial@elloeconomia-energia.com")                    # ex.: contato@elloeconomia-energia.com
NOME_REMETENTE = (os.getenv("NOME_REMETENTE") or "Claudio | ELLO Energia")
SMTP_HOST = (os.getenv("SMTP_HOST") or "smtp.hostinger.com")
SMTP_PORTA = int((os.getenv("SMTP_PORTA") or "465"))
IMAP_HOST = (os.getenv("IMAP_HOST") or "imap.hostinger.com")
IMAP_PORTA = int((os.getenv("IMAP_PORTA") or "993"))
SMTP_USUARIO = os.getenv("SMTP_USUARIO") or EMAIL_REMETENTE
SMTP_SENHA = (os.getenv("SMTP_SENHA") or "")

# Ritmo e regras
LIMITE_DIA = int((os.getenv("LIMITE_DIA") or "30"))
DIAS_FOLLOWUP = [3, 7]                    # 1º e 2º lembrete, em dias corridos após o envio anterior
LINK_AGENDA = (os.getenv("LINK_AGENDA") or "https://cal.com/ello-energia/conversa")  # link do Google Agenda / Cal.com para marcar reunião
LINK_SITE = (os.getenv("LINK_SITE") or "https://elloeconomia-energia.com/")
WHATSAPP = "(19) 99562-1927"
LINK_WHATSAPP = "https://wa.me/5519995621927"
RODAPE_EMPRESA = (os.getenv("RODAPE_EMPRESA") or "Ello Global LTDA · CNPJ 69.972.832/0001-76 · Campinas/SP")
PALAVRAS_RESERVA = [p.strip().lower() for p in os.getenv(
    "PALAVRAS_RESERVA", "nova reserva,novo evento,new booking,new event,agendamento confirmado,reserva confirmada,booked").split(",")]

# Dados (branch "dados", pasta prospeccao/)
DADOS_DIR = Path(os.getenv("DADOS_DIR", RAIZ / "dados-local"))
PASTA = DADOS_DIR / "prospeccao"


def exigir(*nomes: str) -> None:
    if SIMULAR:
        return
    faltando = [n for n in nomes if not (os.getenv(n) or globals().get(n))]
    if faltando:
        raise SystemExit("Faltam configurações no GitHub: " + ", ".join(faltando)
                         + ". Veja o passo a passo em prospeccao/README.md.")
