"""
Agente de IA para Atendimento de Varejo usando LangGraph
Versão com suporte a VISÃO
"""

from typing import Dict, Any, TypedDict, Sequence, List
import re
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# (get_openai_callback removido - não funciona com Gemini)
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition, create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from pathlib import Path
import json
import os

from config.settings import settings
from config.logger import setup_logger
# db_search.conhecimento substituído por vector_search.conhecimento_vetorial
from tools.time_tool import get_current_time
from memory.limited_postgres_memory import LimitedPostgresChatMessageHistory

logger = setup_logger(__name__)

# ============================================
# Definição das Ferramentas (Tools)
# ============================================

@tool
def especialista_humano(consulta: str = "", telefone_cliente: str = "") -> str:
    """
    Transfer the conversation to a human specialist whenever the customer's request is outside the AI agent's scope,
    when more complex human intervention is required, or when all relevant information has already been collected.
    
    Use this tool if you are unable to resolve the customer's query using the knowledge base,
    if the customer explicitly requests to speak with a human, or if the situation requires personalized or sensitive handling.
    
    Args:
        consulta: Resumo do pedido ou motivo da transferência
        telefone_cliente: Número do telefone do cliente (extraído de TELEFONE_CLIENTE no contexto)
    """
    from tools.whatsapp_api import whatsapp
    from config.settings import settings
    from tools.redis_tools import set_agent_cooldown
    
    # Adicionar etiqueta "Novo Pedido" se configurada
    label_id = settings.novo_pedido_label_id
    if telefone_cliente:
        try:
            # Limpar telefone (remover não-numéricos)
            import re
            telefone_limpo = re.sub(r"\D", "", telefone_cliente)
            
            # 1. Adicionar Etiqueta
            if label_id:
                success = whatsapp.add_label_to_chat(telefone_limpo, label_id)
                if success:
                    logger.info(f"🏷️ Etiqueta 'Novo Pedido' adicionada ao chat {telefone_limpo}")
            
            # 2. Pausar IA (Cooldown)
            ttl = settings.human_takeover_ttl
            set_agent_cooldown(telefone_limpo, ttl)
            logger.info(f"⏸️ IA Pausada para {telefone_limpo} por {ttl}s (Transferência para Vendedor)")
            
            # 3. Log Analytics
            from tools.analytics import log_event
            log_event(telefone_limpo, "human_handoff", {"reason": consulta})
            
        except Exception as e:
            logger.error(f"Erro ao processar transferência: {e}")
    
    return "TRANSBORDO_HUMANO: Transferindo para um vendedor finalizar o pedido."

@tool
def time_tool() -> str:
    """Retorna a data e hora atual e o status de funcionamento da loja."""
    return get_current_time()

# Ferramentas ativas
from tools.vector_search import conhecimento_vetorial
ACTIVE_TOOLS = [
    conhecimento_vetorial,
    especialista_humano,
    time_tool,
]

# ============================================
# Funções do Grafo
# ============================================

def load_system_prompt() -> str:
    base_dir = Path(__file__).resolve().parent
    prompt_path = str((base_dir / "prompts" / "agent_system_optimized.md"))
    try:
        text = Path(prompt_path).read_text(encoding="utf-8")
        text = text.replace("{base_url}", settings.supermercado_base_url)
        text = text.replace("{ean_base}", settings.estoque_ean_base_url)
        return text
    except Exception as e:
        logger.error(f"Falha ao carregar prompt: {e}")
        raise

def _build_llm():
    model = getattr(settings, "llm_model", "gemini-2.5-flash-lite")
    temp = float(getattr(settings, "llm_temperature", 0.0))
    provider = getattr(settings, "llm_provider", "google")
    
    if provider == "google":
        logger.info(f"🚀 Usando Google Gemini: {model}")
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,
            temperature=temp,
            convert_system_message_to_human=True,  # Necessário para Gemini processar system prompts
        )
    else:
        base_url = getattr(settings, "openai_api_base", None)
        logger.info(f"🚀 Usando OpenAI-compat: {model} | Base: {base_url or 'default'}")
        kwargs = {
            "model": model,
            "openai_api_key": settings.openai_api_key,
            "temperature": temp,
        }
        if base_url:
            kwargs["openai_api_base"] = base_url
        return ChatOpenAI(**kwargs)

def create_agent_with_history():
    system_prompt = load_system_prompt()
    llm = _build_llm()
    memory = MemorySaver()
    
    # Substituindo a busca antiga pela vetorial
    # Mantemos o nome 'conhecimento' para não quebrar o prompt
    from tools.vector_search import conhecimento_vetorial
    
    tools_list = [
        conhecimento_vetorial,
        especialista_humano,
        time_tool
    ]
    
    # Atualizar o prompt para refletir que agora ele "entende" melhor
    agent = create_react_agent(llm, tools_list, prompt=system_prompt, checkpointer=memory)
    return agent

_agent_graph = None
def get_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_agent_with_history()
    return _agent_graph

# ============================================
# Função Principal
# ============================================

def run_agent_langgraph(telefone: str, mensagem: str) -> Dict[str, Any]:
    """
    Executa o agente. Suporta texto e imagem (via tag [MEDIA_URL: ...]).
    """
    print(f"[AGENT] Telefone: {telefone} | Msg bruta: {mensagem[:50]}...")
    
    # 1. Extrair URL de imagem se houver (Formato: [MEDIA_URL: https://...])
    image_url = None
    clean_message = mensagem
    
    # Regex para encontrar a tag de mídia injetada pelo server.py
    media_match = re.search(r"\[MEDIA_URL:\s*(.*?)\]", mensagem)
    if media_match:
        image_url = media_match.group(1)
        # Remove a tag da mensagem de texto para não confundir o histórico visual
        # Mas mantemos o texto descritivo original
        clean_message = mensagem.replace(media_match.group(0), "").strip()
        if not clean_message:
            clean_message = "Analise esta imagem/comprovante enviada."
        logger.info(f"📸 Mídia detectada para visão: {image_url}")

    # 2. Salvar histórico (User)
    history_handler = None
    try:
        history_handler = get_session_history(telefone)
        history_handler.add_user_message(mensagem)
    except Exception as e:
        logger.error(f"Erro DB User: {e}")

    try:
        agent = get_agent_graph()
        
        # 3. Construir mensagem (Texto Simples ou Multimodal)
        # IMPORTANTE: Injetar telefone no contexto para que o LLM saiba qual usar nas tools
        telefone_context = f"[TELEFONE_CLIENTE: {telefone}]\n\n"
        
        if image_url:
            # Formato multimodal para GPT-4o / GPT-4o-mini
            message_content = [
                {"type": "text", "text": telefone_context + clean_message},
                {
                    "type": "image_url",
                    "image_url": {"url": image_url}
                }
            ]
            initial_message = HumanMessage(content=message_content)
        else:
            initial_message = HumanMessage(content=telefone_context + clean_message)

        initial_state = {"messages": [initial_message]}
        config = {"configurable": {"thread_id": telefone}, "recursion_limit": 100}
        
        logger.info("Executando agente...")
        
        result = agent.invoke(initial_state, config)
        
        # 4. Extrair resposta (com fallback para Gemini empty responses)
        output = ""
        if isinstance(result, dict) and "messages" in result:
            messages = result["messages"]
            logger.debug(f"📨 Total de mensagens no resultado: {len(messages) if messages else 0}")
            if messages:
                # Log das últimas mensagens para debug
                for i, msg in enumerate(messages[-5:]):
                    msg_type = type(msg).__name__
                    has_tool_calls = hasattr(msg, 'tool_calls') and msg.tool_calls
                    content_preview = str(msg.content)[:100] if msg.content else "(vazio)"
                    logger.debug(f"📝 Msg[{i}] type={msg_type} tool_calls={has_tool_calls} content={content_preview}")
                
                # Tentar pegar a última mensagem AI que tenha conteúdo real (não tool call)
                for msg in reversed(messages):
                    # Verificar se é AIMessage
                    if not isinstance(msg, AIMessage):
                        continue
                    
                    # Ignorar mensagens que são tool calls (não tem resposta textual)
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        continue
                    
                    # Extrair conteúdo
                    content = msg.content if isinstance(msg.content, str) else str(msg.content)
                    
                    # Ignorar mensagens vazias
                    if not content or not content.strip():
                        continue
                    
                    # Ignorar mensagens que parecem ser dados estruturados
                    if content.strip().startswith(("[", "{")):
                        continue
                    
                    output = content
                    break
        
        # Fallback se ainda estiver vazio
        if not output or not output.strip():
            # Logar o que foi rejeitado para debug
            if isinstance(result, dict) and "messages" in result:
                last_ai = None
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage):
                        last_ai = msg
                        break
                if last_ai:
                    logger.warning(f"⚠️ Última AIMessage rejeitada: content='{str(last_ai.content)[:200]}' tool_calls={getattr(last_ai, 'tool_calls', None)}")
            
            # FALLBACK SIMPLIFICADO (Adaptado para nova lógica n8n)
            # Se o agente chamou uma tool mas não gerou resposta final, tentamos inferir algo ou pedir desculpas.
            # No caso do n8n, se chamar 'especialista_humano', o próprio retorno da tool já é a resposta.
            
            tool_results = []
            for msg in result.get("messages", []):
                if hasattr(msg, 'content') and isinstance(msg.content, str):
                    content = msg.content
                    if "TRANSBORDO_HUMANO" in content:
                         tool_results.append("transbordo")
            
            if "transbordo" in tool_results:
                output = "Transferindo para um especialista..."
            else:
                output = "Desculpe, não consegui processar sua solicitação. Pode repetir?"
                logger.warning("⚠️ Resposta vazia do LLM, usando fallback genérico")
        
        logger.info("✅ Agente executado")
        logger.info(f"💬 RESPOSTA: {output[:200]}{'...' if len(output) > 200 else ''}")
        
        # 5. Salvar histórico (IA)
        if history_handler:
            try:
                history_handler.add_ai_message(output)
            except Exception as e:
                logger.error(f"Erro DB AI: {e}")

        return {"output": output, "error": None}
        
    except Exception as e:
        logger.error(f"Falha agente: {e}", exc_info=True)
        return {"output": "Tive um problema técnico, tente novamente.", "error": str(e)}

def get_session_history(session_id: str) -> LimitedPostgresChatMessageHistory:
    return LimitedPostgresChatMessageHistory(
        connection_string=settings.postgres_connection_string,
        session_id=session_id,
        table_name=settings.postgres_table_name,
        max_messages=settings.postgres_message_limit
    )

run_agent = run_agent_langgraph
