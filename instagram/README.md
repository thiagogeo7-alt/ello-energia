# Agente de Instagram da ELLO

O agente roda sozinho no GitHub, de graça, nos horários abaixo:

| Tarefa | Quando | O que faz |
|---|---|---|
| **Reels com vídeo IA** | Dias ímpares, 18h (~15 por mês) | No formato do vídeo modelo: cena ultra-realista de 5s feita com IA (Kling 3.0) + textos por cima + tela animada da marca com "Comente ECONOMIZAR" |
| **Carrossel** | Terça e quinta, 12h | Cria 5 slides educativos com a identidade da ELLO e publica |
| **Respostas** | A cada 15 minutos | Quem comenta a palavra-chave recebe DM com o WhatsApp; os demais comentários e DMs são respondidos |
| **Token** | Toda segunda | Renova o acesso ao Instagram |

- **Para mudar o tom, as regras ou os temas**, edite o arquivo [`marca.md`](marca.md). O agente lê esse arquivo toda vez.
- **Painel de resultados:** https://thiagogeo7-alt.github.io/ello-energia/painel/ (publicações, métricas, respostas, custos e leads).
- **Histórico e métricas** ficam no branch `dados`, no arquivo `estado.json`. Os **leads** ficam em `leads.enc`, criptografados com a senha do segredo `PAINEL_SENHA` (o repositório é público; assim os dados pessoais ficam protegidos, conforme a LGPD).
- **Para pausar tudo**, apague a variável `AGENTE_ATIVO` (veja o passo 7 abaixo).

**Custo por ação (modo padrão `imagem`):**

| Ação | Custo aproximado |
|---|---|
| Reels (foto ultra-realista com movimento + tela da marca) | ~US$ 0,02 de imagem + ~US$ 0,03 de Claude |
| Carrossel | ~US$ 0,03 de Claude (imagens montadas de graça) |
| Respostas a comentários/DMs | menos de US$ 0,01 por rodada |

Para usar vídeo de verdade com IA (Kling 3.0, ~US$ 0,56 por Reels), crie a variável `MODO_CENA` = `video` em *Settings → Secrets and variables → Actions → Variables*. O GitHub é grátis.

**Logo e trilha:** ficam na pasta [`marca/`](marca). A trilha da tela final (`trilha-cartela.m4a`) veio do vídeo modelo; para trocar, substitua o arquivo mantendo o nome.

---

# Como configurar (passo a passo)

Você vai criar 3 chaves de acesso e guardá-las no GitHub. Os nomes dos botões podem mudar um pouco com o tempo; se travar, mande um print para o Claude.

> ⚠️ Nunca cole as chaves em arquivos do repositório, no chat ou em mensagens. O único lugar delas é em **Secrets** do GitHub (passo 5).

## 1. Conta profissional no Instagram
No app do Instagram: **perfil → menu (3 linhas) → Tipo de conta e ferramentas → Mudar para conta profissional → Empresa**.

## 2. Criar o app na Meta e gerar o token do Instagram
1. Acesse **developers.facebook.com** e entre com seu Facebook. Se for a primeira vez, aceite os termos de desenvolvedor.
2. Clique em **Meus apps → Criar app**.
3. Nome do app: `Agente ELLO`. Em caso de uso, escolha a opção de **gerenciar mensagens e conteúdo no Instagram**.
4. Dentro do app, abra **Instagram → Configuração da API com login do Instagram**.
5. Na parte **Gerar tokens de acesso**, clique em **Adicionar conta**, entre com o Instagram da ELLO e autorize todas as permissões.
6. Clique em **Gerar token** ao lado da conta e copie o token (um texto longo). Esse é o **IG_TOKEN**.
7. O número que aparece ao lado da conta é o **IG_USER_ID** (opcional; o agente descobre sozinho se você não cadastrar).
8. Na configuração do app, use como URL da política de privacidade:
   `https://thiagogeo7-alt.github.io/ello-energia/privacidade.html`

> A Meta pode exigir uma revisão do app (gratuita, alguns dias) para o agente responder DMs de qualquer pessoa. Publicar e responder comentários na própria conta costuma funcionar sem isso. O Claude te ajuda com a revisão se for necessária.

## 3. Chave do vídeo com IA (fal.ai)
1. Acesse **fal.ai** e crie uma conta.
2. Em **Billing**, adicione créditos (US$ 10 dá para mais de um mês).
3. Em **Keys** (ou **API Keys**), crie uma chave e copie. Essa é a **FAL_KEY**.

## 4. Chave do Claude (Anthropic)
1. Acesse **console.anthropic.com** e crie uma conta (é separada do seu plano do Claude).
2. Em **Billing**, adicione créditos (US$ 10 dura bastante).
3. Em **API Keys**, crie uma chave e copie. Essa é a **ANTHROPIC_API_KEY**.

## 5. Guardar as chaves no GitHub
1. Abra **github.com/thiagogeo7-alt/ello-energia → Settings**.
2. No menu da esquerda: **Secrets and variables → Actions**.
3. Na aba **Secrets**, clique em **New repository secret** e crie um de cada vez:

| Name | Secret |
|---|---|
| `IG_TOKEN` | o token do passo 2 |
| `FAL_KEY` | a chave do passo 3 |
| `ANTHROPIC_API_KEY` | a chave do passo 4 |
| `PAINEL_SENHA` | uma senha que você inventar, para abrir os leads no painel |

## 6. Testar
0. Primeiro confira a conexão: aba **Actions → Instagram - Verificar conexão / renovar token → Run workflow**, com **Simular desmarcado**. Deve aparecer "Tudo certo!" no resultado.
1. No repositório, abra a aba **Actions**.
2. À esquerda, clique em **Instagram - Carrossel (terça e quinta)**.
3. Clique em **Run workflow**. Com **Simular** marcado, nada é publicado nem cobrado: serve para ver se tudo roda.
4. Depois rode de novo com **Simular desmarcado**: o primeiro carrossel de verdade vai para o Instagram.
5. Repita com **Instagram - Reels**. Esse teste real gera um vídeo e custa cerca de US$ 0,56.

## 7. Ligar o piloto automático
Em **Settings → Secrets and variables → Actions**, aba **Variables**, clique em **New repository variable**:
- Name: `AGENTE_ATIVO`
- Value: `sim`

Pronto: a partir daí os horários da tabela lá em cima passam a valer. Para pausar, apague essa variável.
