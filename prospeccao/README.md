# Agente de prospecção da ELLO

Encontra empresas de Campinas, manda e-mails personalizados, responde quem retorna e leva os
interessados para uma reunião. Tudo roda sozinho no GitHub e os resultados aparecem na aba
**Prospecção** do painel: https://elloeconomia-energia.com/painel/

| Tarefa | Quando | O que faz |
|---|---|---|
| **Coleta Google** | Toda segunda, 6h | Busca empresas dos 4 segmentos por bairro no Google Maps e pega o e-mail público do site delas (até 900 buscas/mês, dentro da cota grátis) |
| **Coleta CNPJ** | Todo dia 20 | Lê a base aberta da Receita: empresas ativas de Campinas, dos segmentos escolhidos, com e-mail (exclui MEI e e-mails de contador) |
| **Envio** | Dias úteis, 9h e 14h | Lembretes primeiro, depois novos contatos. Aquecimento: 10/dia na 1ª semana, 20 na 2ª, depois 30 |
| **Respostas** | De hora em hora | Classifica cada resposta (interessado, dúvida, sem interesse, sair, ausente), responde, manda o link da agenda e registra reuniões marcadas |

**Sequência de cada empresa:** 1º e-mail → lembrete após 3 dias → último lembrete após 7 dias → para.
Quem responde sai da sequência na hora.

**Regras de boa prática e LGPD já embutidas:**
- Só e-mails corporativos de fontes públicas; empresário individual (MEI) é excluído.
- Todo e-mail diz de onde veio o contato e como sair ("responda SAIR"), e leva o cabeçalho de descadastro.
- Quem pede para sair entra numa lista de bloqueio e nunca mais recebe nada.
- Os contatos ficam criptografados com a senha do painel (`PAINEL_SENHA`); só números vão a público.
- Nada é enviado no fim de semana.

**Custo:** Google dentro da cota grátis; Claude ~US$ 0,002 por e-mail escrito (≈ US$ 1,50/mês a 30/dia).

---

# Como configurar

## 1. Caixa de e-mail no domínio novo (depois de comprar o domínio)
Na Hostinger (ou onde comprar o domínio): **E-mails → Criar conta**, por exemplo `contato@seudominio.com.br`.
- Confira em **E-mails → Configurações de DNS** se **SPF, DKIM e DMARC** estão ativos (verde). Isso evita cair no spam.
- Use essa caixa normalmente também: as respostas dos clientes chegam nela.

## 2. Link da agenda para as reuniões
Opção simples e grátis: **Google Agenda → Criar → Agenda de horários** (ou cal.com).
Defina dias/horários livres e duração (ex.: 20 min) e copie o **link de reserva**.
Configure a agenda para enviar a confirmação para a caixa do passo 1: assim o agente conta as reuniões marcadas.

## 3. Chave do Google Maps
1. Acesse **console.cloud.google.com**, crie um projeto `ELLO Prospecção`.
2. Em **APIs e serviços → Biblioteca**, ative **Places API (New)**.
3. O Google pede uma conta de faturamento (cartão), mesmo para a cota grátis. Em **Faturamento → Orçamentos e alertas**, crie um alerta de **US$ 1** para ficar tranquilo.
4. Em **APIs e serviços → Credenciais → Criar credenciais → Chave de API**. Em *Restringir chave*, permita só a **Places API (New)**.

## 4. Guardar no GitHub
**Settings → Secrets and variables → Actions**

Aba **Secrets** (sigilosos):
| Nome | Valor |
|---|---|
| `GOOGLE_MAPS_KEY` | chave do passo 3 |
| `SMTP_SENHA` | senha da caixa de e-mail do passo 1 |

Aba **Variables** (não sigilosos):
| Nome | Exemplo |
|---|---|
| `EMAIL_REMETENTE` | `contato@seudominio.com.br` |
| `NOME_REMETENTE` | `Thiago \| ELLO Energia` |
| `LINK_AGENDA` | link do passo 2 |
| `RODAPE_EMPRESA` | `ELLO Energia · CNPJ 00.000.000/0001-00 · Campinas/SP` |
| `SMTP_HOST` / `IMAP_HOST` | só se não for Hostinger (ex.: `smtp.gmail.com` / `imap.gmail.com`) |

## 5. Testar
Aba **Actions → Prospecção - Verificar configuração → Run workflow** (desmarque *Simular*). Tudo deve aparecer com ✅.

## 6. Ligar
Em **Variables**:
- `PROSPECCAO_COLETA` = `sim` → liga as coletas automáticas (pode ligar antes do e-mail ficar pronto).
- `PROSPECCAO_ATIVA` = `sim` → liga envios e respostas. Para pausar, apague a variável.
