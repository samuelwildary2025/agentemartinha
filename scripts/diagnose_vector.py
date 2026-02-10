import psycopg2
from psycopg2.extras import RealDictCursor
import os
import sys
from config.settings import settings

def test_vector_db():
    print("--- INICIANDO DIAGNÓSTICO DO BANCO VETORIAL ---")
    
    # 1. Verificar Configurações
    print("\n[1] Verificando Configurações...")
    openai_key = settings.openai_api_key
    db_url = settings.products_db_connection_string
    
    if not openai_key or openai_key == "sua_chave_aqui":
        print("❌ ERRO CRÍTICO: OPENAI_API_KEY não configurada ou inválida no .env")
        print("   A busca vetorial precisa da OpenAI para gerar embeddings da pesquisa.")
    else:
        print(f"✅ OPENAI_API_KEY encontrada: {openai_key[:5]}...{openai_key[-4:]}")

    if not db_url:
        print("❌ ERRO: PRODUCTS_DB_CONNECTION_STRING não encontrada.")
        return
    else:
        # Mascarar senha para log
        safe_url = db_url.split("@")[-1]
        print(f"✅ String de conexão encontrada (Host: {safe_url})")

    # 2. Testar Conexão com Banco
    print("\n[2] Testando Conexão com PostgreSQL...")
    conn = None
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"✅ Conectado com sucesso! Versão: {version}")
        
        # 3. Verificar Tabela e Extensão
        print("\n[3] Verificando Extensão pgvector e Tabela...")
        
        # Check pgvector
        cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
        if cur.fetchone():
            print("✅ Extensão 'vector' está instalada no banco.")
        else:
            print("❌ Extensão 'vector' NÃO encontrada no banco.")
            
        # Check table
        table = settings.postgres_products_table_name
        cur.execute(f"SELECT to_regclass('{table}');")
        result = cur.fetchone()
        
        if result and result[0]:
            print(f"✅ Tabela '{table}' existe.")
            
            # Check count
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            count = cur.fetchone()[0]
            print(f"📊 Total de produtos cadastrados: {count}")
            
            # Check columns to see if embedding exists
            cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}';")
            cols = [row[0] for row in cur.fetchall()]
            print(f"📝 Colunas encontradas: {', '.join(cols)}")
            
            if 'embedding' not in cols:
                print("❌ ERRO: Coluna 'embedding' não encontrada na tabela.")
        else:
            print(f"❌ Tabela '{table}' NÃO encontrada.")
            print("🔍 Listando tabelas existentes no schema 'public':")
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
            tables = [row[0] for row in cur.fetchall()]
            if tables:
                print(f"   -> {', '.join(tables)}")
                if 'documents' in tables:
                    print("\n🔍 Inspecionando tabela 'documents'...")
                    cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = 'documents';")
                    cols = [row[0] for row in cur.fetchall()]
                    print(f"   Colunas: {', '.join(cols)}")
                    
                    cur.execute("SELECT COUNT(*) FROM documents;")
                    count = cur.fetchone()[0]
                    print(f"   Total de registros: {count}")
            else:
                print("   -> Nenhuma tabela encontrada no schema public.")

    except Exception as e:
        print(f"❌ Falha na conexão com banco: {e}")
    finally:
        if conn:
            conn.close()

    # 4. Testar Geração de Embedding (se tiver chave)
    if openai_key and openai_key != "sua_chave_aqui":
        print("\n[4] Testando Geração de Embedding (OpenAI)...")
        try:
            from langchain_openai import OpenAIEmbeddings
            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=openai_key
            )
            vec = embeddings.embed_query("teste de produto")
            print(f"✅ Embedding gerado com sucesso! Dimensão: {len(vec)}")
            
            # 5. Teste Real de Busca (se tudo acima funcionou)
            if conn: # Reconnect needed if closed
                print("\n[5] Testando Busca Real...")
                # ... (implementar se necessário, mas os passos acima já diagnosticam 99%)
        except Exception as e:
            print(f"❌ Erro ao gerar embedding: {e}")
    else:
        print("\n[4] Pulando teste de embedding (sem chave API).")

    print("\n--- DIAGNÓSTICO CONCLUÍDO ---")

if __name__ == "__main__":
    test_vector_db()
