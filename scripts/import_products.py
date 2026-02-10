import pandas as pd
import psycopg2
import sys
import os

# Adiciona o diretório raiz ao PYTHONPATH para conseguir importar config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings

def import_products():
    """
    Importa produtos do arquivo CSV para o banco de dados Postgres.
    """
    csv_path = '/Users/samuel/Desktop/agente-martinha/LISTA_PRODUTO_IA_GERAL (1).xlsx - LISTA_PRODUTO_IA.csv'
    
    print(f"📖 Lendo arquivo: {csv_path}")
    try:
        # Tenta ler como CSV. Como parece ter apenas uma coluna, o separador pode ser irrelevante se for linha a linha,
        # mas vamos assumir vírgula ou ponto e vírgula. Pelo head, parece ser apenas linhas.
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"❌ Erro ao ler CSV: {e}")
        return

    # Verificar colunas
    # O arquivo tem cabeçalho 'Descricao_Mercadoria'
    target_col = 'Descricao_Mercadoria'
    
    # Normalizar nome das colunas (strip)
    df.columns = [c.strip() for c in df.columns]
    
    if target_col not in df.columns:
        # Tentar pegar a primeira coluna se o nome não bater
        print(f"⚠️ Coluna '{target_col}' não encontrada exatamente. Usando a primeira coluna: {df.columns[0]}")
        target_col = df.columns[0]

    # Conectar ao banco
    conn_str = settings.products_db_connection_string
    if not conn_str:
        print("❌ Connection string não configurada.")
        return

    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        
        table_name = settings.postgres_products_table_name
        
        print(f"🛠️ Criando/Recriando tabela '{table_name}'...")
        
        # Recria tabela focada apenas em nome
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                id SERIAL PRIMARY KEY,
                ean TEXT,
                nome TEXT,
                nome_unaccent TEXT
            );
        """)
        
        # Limpar tabela antes de importar
        cur.execute(f'TRUNCATE TABLE "{table_name}"')
        
        # Instalar extensão unaccent se possível
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")
        except:
            print("⚠️ Não foi possível criar extensão unaccent (falta permissão?).")
            conn.rollback()
        
        print("📥 Importando dados...")
        
        count = 0
        inserted_names = set() # Evitar duplicatas exatas
        
        for index, row in df.iterrows():
            nome = str(row[target_col]).strip()
            
            if not nome or nome.lower() == 'nan':
                continue
                
            if nome in inserted_names:
                continue
                
            inserted_names.add(nome)
            
            # Inserir (sem EAN por enquanto, pois o CSV não tem)
            cur.execute(f"""
                INSERT INTO "{table_name}" (nome, nome_unaccent)
                VALUES (%s, unaccent(%s))
            """, (nome, nome))
            
            count += 1
            if count % 1000 == 0:
                print(f"   Processados: {count}...")
        
        conn.commit()
        print(f"✅ Importação concluída! {count} produtos inseridos.")
        
        # Criar índices para performance
        print("⚡ Criando índices...")
        try:
            cur.execute(f'CREATE INDEX IF NOT EXISTS idx_produtos_nome_trgm ON "{table_name}" USING gin (nome gin_trgm_ops);')
        except Exception as e:
             print(f"⚠️ Não foi possível criar índice trgm (falta extensão pg_trgm?): {e}")
             
        cur.execute(f'CREATE INDEX IF NOT EXISTS idx_produtos_nome_unaccent ON "{table_name}" (nome_unaccent);')
        conn.commit()
        
    except Exception as e:
        print(f"❌ Erro no banco de dados: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
    finally:
        if 'cur' in locals() and cur: cur.close()
        if 'conn' in locals() and conn: conn.close()

if __name__ == "__main__":
    # Tentar instalar pg_trgm caso não exista (melhor busca)
    try:
        conn = psycopg2.connect(settings.products_db_connection_string)
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Aviso: Extensão pg_trgm pode não estar disponível: {e}")

    import_products()
