"""Configurações do agente de prospecção (ficha do cliente em clientes/<id>/ + segredos do GitHub)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # raiz do repositório
from nucleo import cliente as _cliente   # noqa: E402

CLIENTE = _cliente.carregar()
_cliente.aplicar_ambiente(CLIENTE)
P = CLIENTE["prospeccao"]
NOME = CLIENTE.get("nome", "")
NOME_CURTO = CLIENTE.get("nome_curto", NOME)
SEGMENTOS = _cliente.segmentos(CLIENTE)

for _n in ("ANTHROPIC_API_KEY", "GOOGLE_MAPS_KEY", "SMTP_SENHA", "PAINEL_SENHA"):
    if os.getenv(_n):
        os.environ[_n] = os.environ[_n].strip().strip('"').strip("'")

RAIZ = Path(__file__).resolve().parent.parent
MARCA = _cliente.marca_md(CLIENTE)
SIMULAR = (os.getenv("SIMULAR") or "0") == "1"

# Claude
ANTHROPIC_API_KEY = (os.getenv("ANTHROPIC_API_KEY") or "")
MODELO_CRIATIVO = (os.getenv("MODELO_CRIATIVO") or "claude-sonnet-5-5")
MODELO_RAPIDO = (os.getenv("MODELO_RAPIDO") or "claude-haiku-5-5")

# Coleta
GOOGLE_MAPS_KEY = (os.getenv("GOOGLE_MAPS_KEY") or "")
BUSCAS_GOOGLE_POR_MES = int((os.getenv("BUSCAS_GOOGLE_POR_MES") or "900"))   # cota grátis: 1.000/mês
CIDADE = (os.getenv("CIDADE") or "")
UF = (os.getenv("UF") or "")
MUNICIPIO_RECEITA = (os.getenv("MUNICIPIO_RECEITA") or "")   # código da cidade na Receita (vazio = descobre sozinho)
RECEITA_BASE = (os.getenv("RECEITA_BASE") or "https://arquivos.receitafederal.gov.br/public.php/webdav")
RECEITA_TOKEN = (os.getenv("RECEITA_TOKEN") or "YggdBLfdninEJX9")   # compartilhamento público da Receita (WebDAV)

# E-mail (preenchidos quando o domínio e a caixa de e-mail existirem)
EMAIL_REMETENTE = (os.getenv("EMAIL_REMETENTE") or "")
NOME_REMETENTE = (os.getenv("NOME_REMETENTE") or NOME)
ASSISTENTE = P.get("assistente") or "assistente"
SMTP_HOST = (os.getenv("SMTP_HOST") or "smtp.hostinger.com")
SMTP_PORTA = int((os.getenv("SMTP_PORTA") or "465"))
IMAP_HOST = (os.getenv("IMAP_HOST") or "imap.hostinger.com")
IMAP_PORTA = int((os.getenv("IMAP_PORTA") or "993"))
SMTP_USUARIO = os.getenv("SMTP_USUARIO") or EMAIL_REMETENTE
SMTP_SENHA = (os.getenv("SMTP_SENHA") or "")

# Ritmo e regras
LIMITE_DIA = int((os.getenv("LIMITE_DIA") or "30"))
DIAS_FOLLOWUP = [3, 7]                    # 1º e 2º lembrete, em dias corridos após o envio anterior
LINK_AGENDA = (os.getenv("LINK_AGENDA") or "")  # link do Google Agenda / Cal.com para marcar reunião
LINK_SITE = (os.getenv("LINK_SITE") or "")
WHATSAPP = CLIENTE["whatsapp"].get("legivel") or ""
LINK_WHATSAPP = _cliente.link_whatsapp(CLIENTE, "")
RODAPE_EMPRESA = (os.getenv("RODAPE_EMPRESA") or NOME)
BRANCH_DADOS = CLIENTE["branches"]["prospeccao"]
BAIRROS = P.get("bairros") or []
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
