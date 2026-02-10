"""
Script para importar produtos do CSV para o PostgreSQL
Base de conhecimento do agente - apenas para identificar produtos que a loja trabalha
"""
import pandas as pd
import psycopg2
from pathlib import Path

# Configuração
CSV_PATH = Path(__file__).parent.parent / "LISTA_PRODUTO_IA_GERAL (1).xlsx - LISTA_PRODUTO_IA.csv"
DB_CONNECTION = "postgres://postgres:85885885@31.97.252.6:6087/festinfan-bd-produtos?sslmode=disable"
TABLE_NAME = "produtos"

def main():
    print("🚀 Iniciando importação de produtos...")
    
    # 1. Ler CSV
    print(f"📂 Lendo arquivo: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, encoding='utf-8')
    
    # Limpar nomes das colunas (remover espaços extras)
    df.columns = df.columns.str.strip()
    
    print(f"📊 Total de produtos no CSV: {len(df)}")
    print(f"📋 Colunas encontradas: {list(df.columns)}")
    
    # Identificar a coluna de descrição
    col_name = df.columns[0]  # Primeira coluna
    print(f"📝 Usando coluna: {col_name}")
    
    # 2. Conectar ao PostgreSQL
    print(f"🔌 Conectando ao PostgreSQL...")
    conn = psycopg2.connect(DB_CONNECTION)
    cur = conn.cursor()
    
    # 3. Criar tabela (se não existir)
    print(f"📦 Criando tabela '{TABLE_NAME}'...")
    cur.execute(f"""
        DROP TABLE IF EXISTS {TABLE_NAME};
        CREATE TABLE {TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(500) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    
    # 4. Inserir produtos em batch
    print("📥 Inserindo produtos...")
    
    inserted = 0
    skipped = 0
    batch_size = 1000
    
    # Preparar dados para INSERT em batch
    produtos = []
    for _, row in df.iterrows():
        nome = str(row[col_name]).strip()
        if nome and nome.lower() != 'nan' and len(nome) > 2:
            produtos.append(nome)
        else:
            skipped += 1
    
    # Inserir em batches
    for i in range(0, len(produtos), batch_size):
        batch = produtos[i:i+batch_size]
        args_str = ','.join(cur.mogrify("(%s)", (p,)).decode('utf-8') for p in batch)
        cur.execute(f"INSERT INTO {TABLE_NAME} (nome) VALUES {args_str}")
        inserted += len(batch)
        if inserted % 10000 == 0:
            print(f"  ✅ {inserted} produtos inseridos...")
    
    conn.commit()
    
    # 5. Criar índice para busca rápida
    print("🔍 Criando índice para busca...")
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_produtos_nome_lower 
        ON {TABLE_NAME} (LOWER(nome) varchar_pattern_ops);
    """)
    conn.commit()
    
    # 6. Verificar
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    total = cur.fetchone()[0]
    
    print(f"\n✅ Importação concluída!")
    print(f"   📊 Total inserido: {inserted}")
    print(f"   ⏭️  Ignorados: {skipped}")
    print(f"   📋 Total na tabela: {total}")
    
    # Mostrar alguns exemplos
    cur.execute(f"SELECT nome FROM {TABLE_NAME} LIMIT 5")
    print(f"\n📝 Exemplos de produtos:")
    for row in cur.fetchall():
        print(f"   - {row[0]}")
    
    cur.close()
    conn.close()
    print("\n🎉 Pronto! Base de conhecimento carregada.")

if __name__ == "__main__":
    main()
