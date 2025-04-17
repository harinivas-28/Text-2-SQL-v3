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
import google.generativeai as genai
from dotenv import load_dotenv
import re
from contextlib import contextmanager

# Load environment variables
load_dotenv()

# Configure Google Generative AI
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")
genai.configure(api_key=GOOGLE_API_KEY)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Create a single engine instance for the application
engine = create_engine('sqlite:///:memory:', echo=False)

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    connection = engine.connect()
    try:
        yield connection
    finally:
        connection.close()

def create_visualization(df, query):
    plt.figure(figsize=(12, 8))  # Increase figure size
    
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
    
    plt.tight_layout(pad=2.0)  # Increase padding
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    plot_data = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    
    return plot_data

def generate_sql_query(natural_language_query, df):
    """Generate SQL query using Google's Generative AI"""
    try:
        # Create a model instance using Gemini 1.5 Pro
        models = [
            'models/gemini-1.5-pro',
            'models/gemini-1.0-pro', 
            'models/gemini-1.0',
            'models/gemini-1.5',
            'models/gemini-1.5-beta'
        ]
        last_error = None
        for model_name in models:
            try:
                model = genai.GenerativeModel(model_name)
        
                # Prepare a more structured prompt for better SQL generation
                prompt = f"""You are an SQL expert. Generate a SQL query for the following request.

                Table Information:
                Table name: data_table
                Columns: {', '.join(df.columns)}
                Sample data first row: {df.iloc[0].to_dict()}
                
                User Request: {natural_language_query}
                
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
                last_error = e
                logging.warning(f"Failed with model {model_name}: {str(e)}")
                continue
            logging.error(f"All models failed: {str(last_error)}")
            raise ValueError("Error generating SQL Query - all models failed")
    except Exception as e:
        logging.error(f"Error generating SQL query: {str(e)}")
        # Check if it's a rate limit error (429)
        if "429" in str(e) and "quota" in str(e):
            raise ValueError("Error generating SQL Query - code-1.5")
        raise
    

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
        
        return jsonify({
            'preview': preview_html,
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
        
        try:
            sql_query = generate_sql_query(query, df)
            logging.info(f"Generated SQL: {sql_query}")
            
            with get_db_connection() as conn:
                # Create or replace the table
                df.to_sql('data_table', conn, index=False, if_exists='replace')
                
                try:
                    # Execute the query within a transaction
                    with conn.begin():
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
                
                plot_data = create_visualization(result_df, query)
                
                summary_stats = {}
                for col in result_df.select_dtypes(include=[np.number]).columns:
                    stats = {
                        'mean': float(result_df[col].mean()) if not pd.isna(result_df[col].mean()) else None,
                        'median': float(result_df[col].median()) if not pd.isna(result_df[col].median()) else None,
                        'std': float(result_df[col].std()) if not pd.isna(result_df[col].std()) else None,
                        'min': float(result_df[col].min()) if not pd.isna(result_df[col].min()) else None,
                        'max': float(result_df[col].max()) if not pd.isna(result_df[col].max()) else None
                    }
                    summary_stats[col] = {k: v for k, v in stats.items() if v is not None}
                
                return jsonify({
                    'result': result_df.to_dict('records'),
                    'sql_query': sql_query,
                    'plot': plot_data,
                    'summary': summary_stats,
                    'columns': list(result_df.columns)
                })
        except ValueError as ve:
            # Handle the specific error we raised
            if "Error generating SQL Query - code-1.5" in str(ve):
                return jsonify({
                    'error': 'Error generating SQL Query - code-1.5'
                })
            return jsonify({
                'error': str(ve)
            })  
        except Exception as e:
            logging.error(f"Error executing SQL query: {str(e)}")
            return jsonify({
                'error': f'Error executing SQL query: {str(e)}',
                'sql_query': sql_query if 'sql_query' in locals() else 'Query generation failed'
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