import pandas as pd
from sqlalchemy import create_engine
import logging

def test_sql_query(query, df):
    """Test if a SQL query is valid for given DataFrame"""
    engine = create_engine('sqlite:///:memory:', echo=False)
    
    try:
        # Create table with sample data
        df.to_sql('data_table', engine, index=False)
        
        # Try executing query
        result = pd.read_sql_query(query, engine)
        return True, result
        
    except Exception as e:
        return False, str(e)
    
    finally:
        engine.dispose()

if __name__ == '__main__':
    # Test with sample data
    df = pd.read_csv('path/to/your/test.csv')
    query = "SELECT * FROM data_table LIMIT 5;"
    success, result = test_sql_query(query, df)
    print(f"Query {'succeeded' if success else 'failed'}: {result}")
