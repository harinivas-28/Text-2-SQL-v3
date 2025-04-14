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
import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize T5 model and tokenizer
tokenizer = T5Tokenizer.from_pretrained('t5-small', legacy=False)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = T5ForConditionalGeneration.from_pretrained('cssupport/t5-small-awesome-text-to-sql')
model = model.to(device)
model.eval()

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

def generate_sql_query(natural_language_query, table_schema):
    """Generate SQL query using T5 model"""
    input_prompt = f"tables:\n{table_schema}\nquery for:{natural_language_query}"
    
    # Tokenize input
    inputs = tokenizer(input_prompt, padding=True, truncation=True, return_tensors="pt").to(device)
    
    # Generate SQL
    with torch.no_grad():
        outputs = model.generate(**inputs, max_length=512)
    
    # Decode the output
    sql_query = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return sql_query

def get_table_schema(df):
    """Generate table schema information"""
    return create_table_schema_from_df(df)

def create_visualization(df, query):
    plt.figure(figsize=(10, 6))
    
    # Enhanced visualization logic based on query and data types
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
    
    # Convert plot to base64 string
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
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Please upload a CSV file'})
    
    try:
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(temp_path)
        
        # Read and analyze the data
        df = pd.read_csv(temp_path)
        
        # Generate comprehensive statistics
        stats = {
            'row_count': len(df),
            'column_count': len(df.columns),
            'columns': []
        }
        
        for col in df.columns:
            col_stats = {
                'name': col,
                'dtype': str(df[col].dtype),
                'null_count': df[col].isnull().sum(),
                'unique_count': df[col].nunique()
            }
            if df[col].dtype in ['int64', 'float64']:
                col_stats.update({
                    'min': df[col].min(),
                    'max': df[col].max(),
                    'mean': df[col].mean(),
                    'median': df[col].median()
                })
            stats['columns'].append(col_stats)
        
        preview_html = df.head().to_html(classes='table table-striped')
        table_schema = get_table_schema(df)
        
        return jsonify({
            'preview': preview_html,
            'message': 'File uploaded successfully',
            'schema': table_schema,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/query', methods=['POST'])
def process_query():
    try:
        data = request.json
        query = data.get('query')
        filename = data.get('filename')
        
        if not query or not filename:
            return jsonify({'error': 'Query and filename are required'})
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'})
        
        # Read the CSV file into a pandas DataFrame
        df = pd.read_csv(file_path)
        
        # Get table schema for the model
        table_schema = get_table_schema(df)
        
        # Generate SQL query using the model
        sql_query = generate_sql_query(query, table_schema)
        
        # Create a temporary SQLite database
        engine = create_engine('sqlite:///:memory:')
        table_name = 'data_table'
        df.to_sql(table_name, engine, index=False)
        
        # Execute the generated SQL query
        with engine.connect() as conn:
            try:
                result_df = pd.read_sql(text(sql_query), conn)
            except Exception as e:
                return jsonify({
                    'error': f'Error executing SQL query: {str(e)}',
                    'sql_query': sql_query
                })
        
        # Create visualization
        plot_data = create_visualization(result_df, query)
        
        # Generate summary statistics
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
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)