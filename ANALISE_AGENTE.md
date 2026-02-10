# Análise do Agente "Martinha" (Festinfan & Amelinha)

## 1. Visão Geral da Arquitetura
O agente é construído sobre uma arquitetura robusta e moderna, utilizando **Python** como linguagem principal. Ele combina o poder de LLMs (Large Language Models) com ferramentas específicas para varejo.

*   **Framework de Agente**: `LangGraph` (evolução do LangChain) para orquestração de fluxo conversacional e estado.
*   **Servidor Web**: `FastAPI` para receber webhooks do WhatsApp e gerenciar requisições de forma assíncrona.
*   **Banco de Dados**: `PostgreSQL` com extensão `pgvector` para busca semântica de produtos e persistência de histórico de chat.
*   **Cache & Buffer**: `Redis` para gerenciamento de buffer de mensagens, controle de "digitando" e sessões.
*   **Modelos de IA**: Suporte híbrido para **Google Gemini** (Gemini 2.0 Flash/Lite) e **OpenAI** (GPT-4o), configurável via variáveis de ambiente.

## 2. Capacidades Principais

### 🧠 Inteligência & Raciocínio
*   **Prompt de Sistema Otimizado**: O agente possui uma persona bem definida ("Martinha"), com regras claras de atendimento, horários de funcionamento e limites de atuação.
*   **Memória Contextual**: Utiliza `LimitedPostgresChatMessageHistory` para manter o contexto da conversa, com lógica inteligente para limpar o contexto se o agente ficar "confuso".

### 👁️ Multimodalidade (Visão e Audição)
*   **Processamento de Imagens**: Capaz de analisar fotos enviadas pelos clientes (usando Gemini Vision) para identificar produtos, marcas e variantes.
*   **Transcrição de Áudio**: Converte áudios do WhatsApp em texto automaticamente (usando Gemini) para que o agente possa responder.
*   **Leitura de PDF**: Extrai texto de comprovantes ou listas enviadas em PDF.

### 🛠️ Ferramentas (Tools)
1.  **`conhecimento_vetorial` (Busca de Produtos)**:
    *   Utiliza embeddings (OpenAI `text-embedding-3-small`) para buscar produtos no catálogo por similaridade semântica.
    *   Permite que o cliente descreva o produto de forma vaga e ainda assim encontre resultados relevantes.
2.  **`especialista_humano` (Transbordo)**:
    *   Transfere o atendimento para um humano em casos complexos, fechamento de pedido ou quando o produto não é identificado.
    *   Adiciona etiquetas (labels) no WhatsApp para sinalizar "Novo Pedido".
3.  **`time_tool` (Consciência Temporal)**:
    *   Verifica se a loja está aberta, fechada ou em intervalo, adaptando a resposta (ex: avisar que a vendedora só verá na segunda-feira).

## 3. Estrutura de Código

*   **`server.py`**: O "cérebro" da entrada de dados.
    *   Recebe webhooks do WhatsApp.
    *   Normaliza mensagens (texto, áudio, imagem).
    *   Gerencia buffer de mensagens (para não responder cada frase picada do cliente separadamente).
    *   Simula comportamento humano (delay de leitura, status "digitando").
*   **`agent_langgraph_simple.py`**: O "coração" da lógica.
    *   Define o grafo de execução do agente.
    *   Configura o LLM e as ferramentas.
    *   Calcula custos de tokens.
*   **`tools/`**: Contém a implementação das ferramentas (`vector_search.py`, `time_tool.py`, etc.).
*   **`memory/`**: Gerenciamento customizado de memória no Postgres.

## 4. Pontos Fortes
*   **Robustez**: Tratamento de erros em várias camadas (banco de dados, API, LLM).
*   **Experiência do Usuário (UX)**: Simulação de digitação e delay torna a interação mais natural.
*   **Escalabilidade**: Uso de Redis e Postgres permite escalar para muitos atendimentos simultâneos.
*   **Custo-Eficiência**: Uso de modelos "Flash/Lite" e "Mini" reduz custos operacionais mantendo boa qualidade.

## 5. Observações e Sugestões
*   **Complexidade do `server.py`**: O arquivo concentra muita responsabilidade (processamento de mídia, buffer, rotas). Poderia ser refatorado para dividir responsabilidades.
*   **Dependência de APIs**: O sistema depende fortemente da estabilidade da API do WhatsApp (não oficial/gateway) e das APIs de IA. O tratamento de falhas nessas pontas parece bem implementado.
*   **Manutenção de Prompt**: As regras de negócio (endereço, horários) estão no prompt (`prompts/agent_system_optimized.md`). Mudanças nesses dados exigem deploy/update do arquivo.

---
**Conclusão**: É um agente de nível de produção, bem estruturado para o varejo, cobrindo as principais necessidades de um atendimento automatizado híbrido (IA + Humano).
