import logging
from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import os
from sqlalchemy import create_engine, text
import requests
from urllib.error import URLError
import json
from dotenv import load_dotenv
import re

load_dotenv()  # Add this near the top of the file, after imports

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Change model to a better performing one
API_URL = "https://api-inference.huggingface.co/models/mrm8488/t5-base-finetuned-wikiSQL"
headers = {"Authorization": f"Bearer {os.getenv('HUGGINGFACE_TOKEN')}"}

def query_model(payload):
    """Query the model via Hugging Face API"""
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 503:
            raise Exception("Model is loading, please try again in a few seconds")
        elif response.status_code == 401:
            raise Exception("API token is invalid or missing")
        else:
            raise Exception(f"API request failed with status code: {response.status_code}")
    except requests.exceptions.Timeout:
        raise Exception("Request timed out. Please try again")
    except requests.exceptions.ConnectionError:
        raise Exception("Cannot connect to the API. Please check your internet connection")
    except Exception as e:
        raise Exception(f"API request failed: {str(e)}")

def create_table_schema_from_df(df):
    """Create SQL CREATE TABLE statement from DataFrame"""
    columns = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        if dtype.startswith('int'):
            sql_type = 'INTEGER'
        elif dtype.startswith('float'):
            sql_type = 'REAL'
        else:
            sql_type = 'TEXT'
        columns.append(f'"{col}" {sql_type}')
    
    table_name = 'data_table'
    create_stmt = f'CREATE TABLE {table_name} ({", ".join(columns)})'
    return create_stmt

def validate_sql_query(query):
    """Validate and clean SQL query"""
    query = query.strip()
    
    # Remove SQL prefix if present
    if query.lower().startswith('sql'):
        query = query[3:].strip()

    # Fix incomplete column names or functions
    if '_in' in query and not query.endswith('_in'):
        parts = query.split('_in')
        if len(parts) > 1:
            query = parts[0] + '_in_thousands' + parts[1]

    # Add missing GROUP BY clause
    if 'MAX(' in query or 'MIN(' in query or 'AVG(' in query or 'SUM(' in query:
        if 'GROUP BY' not in query.upper():
            non_agg_columns = [col.strip() for col in query[6:query.find('(')].split(',') if col.strip()]
            if non_agg_columns:
                query = query.rstrip(';') + ' GROUP BY ' + ', '.join(non_agg_columns) + ';'

    # Remove incomplete clauses
    if query.endswith(('WHERE', 'GROUP BY', 'ORDER BY', 'HAVING')):
        query = query.rsplit(' ', 1)[0]

    # Ensure proper query termination
    if not query.endswith(';'):
        query = query + ';'

    # Basic syntax validation
    if not query.upper().startswith('SELECT'):
        raise ValueError("Invalid SQL query: Must start with SELECT")

    return query

def get_column_details(df):
    """Get detailed information about columns"""
    details = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        sample_values = df[col].dropna().head(3).tolist()
        details.append({
            'name': col,
            'type': dtype,
            'sample_values': sample_values
        })
    return details

def generate_sql_query(natural_language_query, table_schema, df):
    """Generate SQL query using Hugging Face API with enhanced context"""
    try:
        # Get sample data and column info
        sample_data = df.head(3).to_dict('records')
        column_types = {col: str(dtype) for col, dtype in df.dtypes.items()}
        
        # Create a more structured prompt
        prompt = {
            "question": natural_language_query,
            "table_name": "data_table",
            "columns": list(df.columns),
            "column_types": column_types,
            "sample_data": sample_data
        }
        
        # Format the prompt for the model
        input_text = (
            f"Convert to SQL: {natural_language_query}\n"
            f"Table: data_table\n"
            f"Columns: {', '.join(df.columns)}\n"
            f"Sample data:\n{pd.DataFrame(sample_data).to_string()}\n"
            "SQL:"
        )
        
        logging.info(f"Prompt to model:\n{input_text}")
        
        # Get SQL from model
        response = query_model({"inputs": input_text})
        
        if isinstance(response, list) and len(response) > 0:
            sql_query = response[0]['generated_text']
            logging.info(f"Raw SQL: {sql_query}")
            
            # Clean the query
            sql_query = clean_sql_query(sql_query, df.columns)
            logging.info(f"Cleaned SQL: {sql_query}")
            
            return sql_query
            
        raise ValueError("Model returned invalid response")
        
    except Exception as e:
        logging.error(f"SQL generation error: {str(e)}")
        raise

def clean_sql_query(query, valid_columns):
    """Clean and validate SQL query"""
    query = query.strip()
    
    # Remove common prefixes
    prefixes = ['SELECT SQL', 'SQL:', 'SQLITE:', 'QUERY:']
    for prefix in prefixes:
        if query.upper().startswith(prefix):
            query = query[len(prefix):].strip()
    
    # Ensure SELECT
    if not query.upper().startswith('SELECT'):
        query = 'SELECT ' + query
    
    # Ensure FROM clause
    if 'FROM' not in query.upper():
        query = query + ' FROM data_table'
    
    # Fix column names
    for col in valid_columns:
        col_pattern = col.replace('_', '[_ ]').replace(' ', '[_ ]')
        query = re.sub(f'(?i){col_pattern}', col, query)
    
    # Add missing semicolon
    if not query.endswith(';'):
        query += ';'
    
    return query

def extract_columns_from_query(query):
    """Extract column names from SQL query"""
    query = query.upper()
    for keyword in ['FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING']:
        query = query.replace(keyword, ',')
    words = set(w.strip('"() ') for w in query.split(','))
    functions = {'SELECT', 'AS', 'AND', 'OR', 'IN', 'MAX', 'MIN', 'AVG', 'SUM', 'COUNT'}
    return {w for w in words if w and w not in functions}

def is_valid_sql(query):
    """Basic SQL syntax validation"""
    required_elements = ['SELECT', 'FROM']
    query_upper = query.upper()
    
    if not all(elem in query_upper for elem in required_elements):
        return False
        
    if query.count('(') != query.count(')'):
        return False
        
    if any(pattern in query_upper for pattern in ['DROP', 'DELETE', 'UPDATE', 'INSERT', '--', ';SELECT']):
        return False
        
    return True

def get_table_schema(df):
    """Generate table schema information"""
    return create_table_schema_from_df(df)

def create_visualization(df, query):
    plt.figure(figsize=(10, 6))
    
    if len(df.columns) == 1:
        col = df.columns[0]
        if df[col].dtype in [np.int64, np.float64]:
            sns.histplot(data=df, x=col, kde=True)
            plt.title(f'Distribution of {col}')
        else:
            value_counts = df[col].value_counts()
            sns.barplot(x=value_counts.index, y=value_counts.values)
            plt.title(f'Frequency of {col}')
            plt.xticks(rotation=45)
    elif len(df.columns) == 2:
        col1, col2 = df.columns
        if df[col1].dtype in [np.int64, np.float64] and df[col2].dtype in [np.int64, np.float64]:
            sns.scatterplot(data=df, x=col1, y=col2)
            plt.title(f'{col2} vs {col1}')
        elif df[col1].dtype in [np.int64, np.float64]:
            sns.boxplot(data=df, x=col2, y=col1)
            plt.title(f'{col1} by {col2}')
            plt.xticks(rotation=45)
        elif df[col2].dtype in [np.int64, np.float64]:
            sns.boxplot(data=df, x=col1, y=col2)
            plt.title(f'{col2} by {col1}')
            plt.xticks(rotation=45)
        else:
            sns.heatmap(pd.crosstab(df[col1], df[col2]), annot=True, fmt='d')
            plt.title(f'Heatmap of {col1} vs {col2}')
    
    plt.tight_layout()
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    plot_data = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    
    return plot_data

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'})
    
    try:
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'})
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Please upload a CSV file'})
        
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(temp_path)
        
        df = pd.read_csv(temp_path)
        
        stats = {
            'row_count': int(len(df)),
            'column_count': int(len(df.columns)),
            'columns': []
        }
        
        for col in df.columns:
            col_stats = {
                'name': str(col),
                'dtype': str(df[col].dtype),
                'null_count': int(df[col].isnull().sum()),
                'unique_count': int(df[col].nunique())
            }
            if df[col].dtype in ['int64', 'float64']:
                col_stats.update({
                    'min': float(df[col].min()),
                    'max': float(df[col].max()),
                    'mean': float(df[col].mean()),
                    'median': float(df[col].median())
                })
            stats['columns'].append(col_stats)
        
        preview_html = df.to_html(classes='table table-striped', index=False)
        table_schema = get_table_schema(df)
        
        return jsonify({
            'preview': preview_html,
            'schema': table_schema,
            'stats': stats,
            'success': True,
            'total_rows': int(len(df))
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'success': False
        })

@app.route('/query', methods=['POST'])
def process_query():
    try:
        data = request.json
        query = data.get('query')
        filename = data.get('filename')
        
        logging.info(f"Processing query: {query}")
        logging.info(f"File: {filename}")
        
        if not query or not filename:
            return jsonify({'error': 'Query and filename are required'})
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'})
        
        df = pd.read_csv(file_path)
        logging.info(f"DataFrame columns: {df.columns.tolist()}")
        
        df.columns = [col.strip().replace(' ', '_').replace('-', '_') for col in df.columns]
        
        table_schema = get_table_schema(df)
        logging.info(f"Table schema: {table_schema}")
        
        try:
            sql_query = generate_sql_query(query, table_schema, df)
            logging.info(f"Generated SQL: {sql_query}")
            
            engine = create_engine('sqlite:///:memory:', echo=True)
            
            with engine.connect() as conn:
                df.to_sql('data_table', conn, index=False, if_exists='replace')
                try:
                    result_df = pd.read_sql_query(sql_query, conn)
                except Exception as sql_error:
                    logging.error(f"SQL execution error: {str(sql_error)}")
                    logging.error(f"Failed query: {sql_query}")
                    raise
                
                if result_df.empty:
                    return jsonify({
                        'error': 'Query returned no results',
                        'sql_query': sql_query
                    })
                
        except Exception as e:
            logging.error(f"Error executing SQL query: {str(e)}")
            return jsonify({
                'error': f'Error executing SQL query: {str(e)}',
                'sql_query': sql_query if 'sql_query' in locals() else 'Query generation failed'
            })

        plot_data = create_visualization(result_df, query)
        
        summary_stats = {}
        for col in result_df.select_dtypes(include=[np.number]).columns:
            summary_stats[col] = {
                'mean': result_df[col].mean(),
                'median': result_df[col].median(),
                'std': result_df[col].std(),
                'min': result_df[col].min(),
                'max': result_df[col].max()
            }
        
        return jsonify({
            'result': result_df.to_dict('records'),
            'sql_query': sql_query,
            'plot': plot_data,
            'summary': summary_stats,
            'columns': list(result_df.columns)
        })
        
    except Exception as e:
        logging.error(f"Error processing query: {str(e)}")
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    app.run(debug=True)