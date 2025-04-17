# Text-to-SQL Converter (Using Flask) 🔄

Convert natural language questions to SQL queries using Google's Generative AI! 🤖

## 📁 Project Structure

```
Text-2-SQL-v3/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── static/
│   ├── css/           # Stylesheets
│   └── js/            # JavaScript files
├── templates/         
│   ├── base.html      # Base template
│   └── index.html     # Main application page
├── uploads/           # Temporary CSV storage
└── model_cache/       # Cached model files
```

## ✨ Features

- 📊 Upload and analyze CSV files
- 💬 Natural language to SQL conversion using Google's Generative AI
- 📈 Automatic data visualization
- 📑 Statistical summaries
- 🎯 Interactive query examples
- 📱 Responsive design

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git
- Google API key for Generative AI

### Set Up Google API Key

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Generative Language API
4. Create credentials (API key) for the Generative Language API
5. Copy your API key
6. Add it to the `.env` file:
   ```
   GOOGLE_API_KEY=your_google_api_key_here
   ```

### Clone the Repository

```bash
git clone https://github.com/yourusername/Text-2-SQL-v3.git
cd Text-2-SQL-v3
```

### Set Up Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# For Windows
venv\Scripts\activate
# For Unix or MacOS
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run the Application

```bash
python app.py
```

Visit `http://localhost:5000` in your web browser 🌐

## 💡 Usage

1. Upload your CSV file using the upload button or drag-and-drop
2. Wait for the data preview to load
3. Type your question in natural language or use example queries
4. Click "Generate Insights" to get SQL and results
5. Explore visualizations and statistics in the results section

## 🔧 Technical Details

- **Backend**: Flask (Python)
- **AI Model**: Google Generative AI (Gemini) for text-to-SQL conversion
- **Frontend**: HTML5, CSS3, JavaScript
- **Data Processing**: Pandas, NumPy
- **Visualization**: Matplotlib, Seaborn

## 📝 Example Queries

- "Show all rows from the table"
- "What is the average [column]?"
- "Find records where [column] > [value]"
- "Show the top 5 rows"

## ⚠️ Important Notes

- Maximum file size: 10MB
- Supported format: CSV
- Model files are cached locally after first run
- Requires active internet connection for first-time model download

## 🤝 Contributing

Feel free to:
- 🐛 Report bugs
- 💡 Suggest enhancements
- 🔀 Submit pull requests

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Google for the Generative AI API
- Flask team for the web framework
- Open source community for various libraries
