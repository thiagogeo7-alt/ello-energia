# ELLO Energia — estrutura de marketing

| Pasta | O que tem |
|---|---|
| `docs/` | O site (landing page). O GitHub Pages exige que a pasta do site se chame `docs`. |
| `instagram/` | Agente de gestão do Instagram — veja [instagram/README.md](instagram/README.md) |
| `prospeccao/` | Agente de prospecção por e-mail — veja [prospeccao/README.md](prospeccao/README.md) |
| `docs/painel/` | Painel de resultados (Instagram e Prospecção). Outros clientes: `/painel/?cliente=nome-da-pasta&nome=Nome` |
| `clientes/` | **Uma pasta por cliente** (a ELLO é `clientes/ello`). Tudo o que muda de um cliente para outro fica ali |
| `nucleo/` | Peças comuns do produto: leitura da ficha do cliente, lista de clientes ativos, criação de cliente novo |

## Produto multi-cliente — como instalar um cliente novo
1. **Actions → Produto - Novo cliente → Run workflow**: preencha nome, cidade, WhatsApp, site e descrição. A IA cria `clientes/<nome>/` (desligado).
2. Revise `marca.md` e `cliente.yaml`, coloque o logo em `marca/logo.svg` (ou `.png`).
3. Cadastre os segredos com o prefixo do cliente (ex.: `CLINICA_SORRISO_IG_TOKEN`, `CLINICA_SORRISO_PAINEL_SENHA`).
   As chaves do Claude (`ANTHROPIC_API_KEY`) e do vídeo (`FAL_KEY`) da agência servem para todos, se o cliente não tiver as próprias.
4. Rode qualquer workflow manualmente com **cliente = nome da pasta** (comece por *Verificar conexão* e por uma *prévia* de Reels).
5. Aprovado: mude `ligado: nao` → `ligado: sim` na ficha. Os horários automáticos passam a incluir o cliente.

Segurança: cada cliente só enxerga os próprios segredos (nunca o token de outro). Execuções manuais usam `ello` como padrão.

## Site
- Simulador de economia, FAQ, formulário que abre o WhatsApp.
- Configurações (número do WhatsApp, desconto do simulador, endpoint de leads) ficam no topo do `<script>` em `docs/index.html`.

> Nunca coloque senhas, tokens ou chaves de API neste repositório.
