
import psycopg2
from config.settings import settings

def count_rows():
    try:
        conn = psycopg2.connect(settings.postgres_connection_string)
        cur = conn.cursor()
        table = settings.postgres_products_table_name
        cur.execute(f"SELECT count(*) FROM {table}")
        print(f"Rows in {table}: {cur.fetchone()[0]}")
        
        cur.execute(f"SELECT count(*) FROM {table} WHERE embedding IS NULL")
        print(f"Rows with NULL embedding: {cur.fetchone()[0]}")
        conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    count_rows()
