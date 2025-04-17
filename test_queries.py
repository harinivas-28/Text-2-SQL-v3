import pandas as pd
from sqlalchemy import create_engine
import logging
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Configure Google Generative AI
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")
genai.configure(api_key=GOOGLE_API_KEY)

def generate_sql_query(user_query, df_info):
    """Generate SQL query using Google's Generative AI"""
    try:
        # Create a model instance using Gemini 1.5 Pro
        model = genai.GenerativeModel('models/gemini-1.5-pro')
        
        # Prepare a more structured prompt for better SQL generation
        prompt = f"""You are an SQL expert. Generate a SQL query for the following request.

        Table Information:
        Table name: data_table
        Columns: {', '.join(df_info.columns)}
        Sample data first row: {df_info.iloc[0].to_dict()}
        
        User Request: {user_query}
        
        Important Instructions:
        1. Return ONLY the SQL query, no explanations
        2. Use proper column names exactly as provided
        3. Always use the table name 'data_table'
        4. Use standard SQL syntax compatible with SQLite
        
        SQL Query:"""
        
        # Generate the response
        response = model.generate_content(prompt)
        sql_query = response.text.strip()
        
        # Basic validation that it's a SQL query
        if not any(keyword in sql_query.upper() for keyword in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']):
            raise ValueError("Generated text is not a valid SQL query")
        
        # Clean up the query if needed
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
            
        return sql_query
    except Exception as e:
        logging.error(f"Error generating SQL query: {str(e)}")
        raise

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

def process_natural_query(user_query, df):
    """Process natural language query and return SQL results"""
    try:
        # Generate SQL query from natural language
        sql_query = generate_sql_query(user_query, df)
        
        # Test the generated query
        success, result = test_sql_query(sql_query, df)
        
        if success:
            return True, result, sql_query
        else:
            return False, f"Generated query failed: {result}", sql_query
            
    except Exception as e:
        return False, f"Error processing query: {str(e)}", None

if __name__ == '__main__':
    # Test with sample data
    df = pd.read_csv('uploads/car_sales_data.csv')
    test_query = "Show me the average price of cars by brand"
    success, result, sql_query = process_natural_query(test_query, df)
    print(f"Generated SQL: {sql_query}")
    print(f"Query {'succeeded' if success else 'failed'}: {result}")
