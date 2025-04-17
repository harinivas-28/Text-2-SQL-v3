let currentFileName = null;
let tableSchema = null;
let isProcessing = false;
let processTimeout = null;

// Error handling setup
window.onerror = function(msg, url, lineNo, columnNo, error) {
    console.error('Error:', error);
    return true; // Prevents default browser error handling
};

window.onunhandledrejection = function(event) {
    console.error('Promise rejection:', event.reason);
    event.preventDefault(); // Prevents default browser error handling
};

// File selection handling
document.getElementById('csvFile').addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (file) {
        showSelectedFile(file);
    }
});

function showSelectedFile(file) {
    const selectedFileDiv = document.getElementById('selectedFile');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const uploadProgress = document.getElementById('uploadProgress').querySelector('.progress-bar');
    
    // Show selected file info
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    selectedFileDiv.classList.remove('d-none');
    uploadProgress.style.width = '0%';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

    // File upload handling
    document.getElementById('uploadForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        if (isProcessing) {
            showError('Please wait, a file is being processed');
            return; // Prevent multiple submissions
        }
        
        // Clear any existing timeout
        if (processTimeout) {
            clearTimeout(processTimeout);
        }

        isProcessing = true;
        const fileInput = document.getElementById('csvFile');
        const submitButton = document.getElementById('submitQuery');
        const previewArea = document.getElementById('previewArea');
        const uploadProgress = document.getElementById('uploadProgress').querySelector('.progress-bar');
        
        if (!fileInput.files.length) {
            showError('Please select a file to upload');
            isProcessing = false;
            return;
        }
        document.getElementById('copySQL').addEventListener('click', function() {
            const sqlCode = document.getElementById('sqlCode').textContent;
            navigator.clipboard.writeText(sqlCode).then(() => {
                showSuccess('SQL query copied to clipboard');
            }).catch(err => {
                showError('Failed to copy: ' + err);
            });
        });
        // Clear previous results and disable query
        submitButton.disabled = true;
        document.getElementById('queryResult').innerHTML = '';
        document.getElementById('visualizationArea').innerHTML = '';
        document.getElementById('summaryArea').innerHTML = '';
        document.getElementById('sqlDisplay').classList.add('d-none');
        document.getElementById('resultFooter').classList.add('d-none');
        document.getElementById('chartControls').classList.add('d-none');
        // Drag and drop handling for the upload zone
        const dropZone = document.getElementById('dropZone');
        const browseBtn = document.getElementById('browseBtn');
        const removeFileBtn = document.getElementById('removeFile');

        browseBtn.addEventListener('click', () => {
            fileInput.click();
        });

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                showSelectedFile(e.dataTransfer.files[0]);
            }
        });

        removeFileBtn.addEventListener('click', () => {
            fileInput.value = '';
            document.getElementById('selectedFile').classList.add('d-none');
        });
        // Add chart control event listeners
        document.getElementById('chartType').addEventListener('change', updateChart);
        document.getElementById('xAxis').addEventListener('change', updateChart);
        document.getElementById('yAxis').addEventListener('change', updateChart);

        // Function to update chart based on control changes
        async function updateChart() {
            if (!currentFileName) return;
            
            const chartType = document.getElementById('chartType').value;
            const xAxis = document.getElementById('xAxis').value;
            const yAxis = document.getElementById('yAxis').value;
            
            if (!chartType || !xAxis || !yAxis) return;
            
            try {
                const response = await fetch('/update_chart', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        filename: currentFileName,
                        chart_type: chartType,
                        x_axis: xAxis,
                        y_axis: yAxis
                    })
                });
                
                const result = await response.json();
                
                if (result.error) {
                    showError(result.error);
                    return;
                }
                
                if (result.plot) {
                    updateVisualization(result.plot);
                }
            } catch (error) {
                console.error('Error updating chart:', error);
                showError('Failed to update chart: ' + error.message);
            }
        }
        
        // Show loading state in preview area
        previewArea.innerHTML = `
            <div class="text-center p-4">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2">Loading your data...</p>
            </div>`;

        // Simulate upload progress
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += 5;
            if (progress <= 90) {
                uploadProgress.style.width = progress + '%';
            }
        }, 100);

        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            clearInterval(progressInterval);
            uploadProgress.style.width = '100%';

            const result = await response.json();
            
            if (result.error) {
                showError(result.error);
                currentFileName = null;
                tableSchema = null;
                return;
            }

            // Ensure any previous data is cleared
            document.getElementById('queryResult').innerHTML = '';
            document.getElementById('visualizationArea').innerHTML = '';
            document.getElementById('summaryArea').innerHTML = '';

            // Reset previous data
            currentFileName = file.name;
            tableSchema = result.schema;

            // Update the preview area with the full data
            previewArea.innerHTML = result.preview;
            
            // Show data stats with total rows
            const dataStats = document.getElementById('dataStats');
            dataStats.classList.remove('d-none');
            document.getElementById('rowCount').textContent = result.total_rows;
            document.getElementById('colCount').textContent = document.querySelectorAll('#previewArea th').length;

            // Generate example queries based on columns
            generateExampleQueries(result.stats.columns);
            
        } catch (error) {
            showError('Error uploading file: ' + error.message);
            currentFileName = null;
            tableSchema = null;
        } finally {
            isProcessing = false;
            submitButton.disabled = false;
        }
    });

function generateExampleQueries(columns) {
    const exampleQueriesDiv = document.getElementById('exampleQueries');
    exampleQueriesDiv.innerHTML = '';
    
    const queries = [];
    
    // Get numeric and categorical columns
    const numericColumns = columns.filter(col => ['int64', 'float64'].includes(col.dtype));
    const categoricalColumns = columns.filter(col => !['int64', 'float64'].includes(col.dtype));
    
    // Generate example queries based on column types
    if (numericColumns.length > 0) {
        queries.push(
            `What is the average ${numericColumns[0].name}?`,
            `Show me the highest ${numericColumns[0].name}`,
            `What is the distribution of ${numericColumns[0].name}?`
        );
    }
    
    if (categoricalColumns.length > 0) {
        queries.push(
            `How many entries for each ${categoricalColumns[0].name}?`,
            `Show all unique ${categoricalColumns[0].name} values`
        );
    }
    
    if (numericColumns.length > 0 && categoricalColumns.length > 0) {
        queries.push(
            `What is the average ${numericColumns[0].name} by ${categoricalColumns[0].name}?`,
            `Show ${numericColumns[0].name} distribution for each ${categoricalColumns[0].name}`
        );
    }
    
    // Add example queries to the UI
    queries.forEach(query => {
        const button = document.createElement('button');
        button.className = 'btn btn-outline-secondary btn-sm example-query';
        button.textContent = query;
        button.addEventListener('click', () => {
            document.getElementById('queryInput').value = query;
        });
        exampleQueriesDiv.appendChild(button);
    });
}

// Query processing
document.getElementById('submitQuery').addEventListener('click', async function() {
    if (!currentFileName) {
        showError('Please upload a file first');
        return;
    }

    const queryInput = document.getElementById('queryInput');
    const query = queryInput.value.trim();
    
    if (!query) {
        showError('Please enter a query');
        return;
    }

    // Show loading state
    const querySpinner = document.getElementById('querySpinner');
    querySpinner.classList.remove('d-none');
    this.disabled = true;

    try {
        const response = await fetch('/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                filename: currentFileName
            })
        });

        const result = await response.json();
        
        if (result.error) {
            showError(result.error);
            return;
        }

        // Display results in table view
        displayResults(result.result);

        // Update visualization if available
        if (result.plot) {
            updateVisualization(result.plot);
        } else {
            document.getElementById('visualizationArea').innerHTML = '<div class="no-chart-message text-center p-5"><i class="fas fa-chart-area fa-3x text-muted mb-3"></i><h5 class="text-muted">No visualization available for this query</h5></div>';
        }

        // Update summary statistics if available
        if (result.summary && Object.keys(result.summary).length > 0) {
            updateSummary(result.summary);
        } else {
            document.getElementById('summaryArea').innerHTML = '<div class="text-center p-4">No summary statistics available for this query</div>';
        }

        // Show SQL if checkbox is checked
        const showSQL = document.getElementById('showSQL').checked;
        const sqlDisplay = document.getElementById('sqlDisplay');
        const sqlCode = document.getElementById('sqlCode');
        
        if (showSQL && result.sql_query) {
            sqlDisplay.classList.remove('d-none');
            sqlCode.textContent = result.sql_query;
        } else {
            sqlDisplay.classList.add('d-none');
        }

        // Show result footer with stats
        if (result.result && result.result.length > 0) {
            const resultFooter = document.getElementById('resultFooter');
            resultFooter.classList.remove('d-none');
            document.getElementById('resultCount').textContent = result.result.length;
            document.getElementById('queryTime').textContent = result.execution_time || '0';
        }

        // Update chart controls if we have data
        if (result.columns && result.columns.length > 0) {
            document.getElementById('chartControls').classList.remove('d-none');
            updateAxisSelectors(result.columns);
        } else {
            document.getElementById('chartControls').classList.add('d-none');
        }
        
        // Show success notification
        showSuccess('Query executed successfully');
        
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to execute query: ' + error.message);
    } finally {
        querySpinner.classList.add('d-none');
        this.disabled = false;
    }
});

document.getElementById('exportCSV').addEventListener('click', function(e) {
    e.preventDefault();
    exportData('csv');
});

document.getElementById('exportJSON').addEventListener('click', function(e) {
    e.preventDefault();
    exportData('json');
});

document.getElementById('exportPDF').addEventListener('click', function(e) {
    e.preventDefault();
    exportData('pdf');
});

async function exportData(format) {
    if (!currentFileName) {
        showError('No data available to export');
        return;
    }
    
    try {
        const response = await fetch(`/export/${format}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                filename: currentFileName
            })
        });
        
        if (format === 'pdf') {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `export.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
        } else {
            const result = await response.json();
            if (result.error) {
                showError(result.error);
                return;
            }
            showSuccess(`Data exported as ${format.toUpperCase()}`);
        }
    } catch (error) {
        console.error('Export error:', error);
        showError(`Failed to export as ${format.toUpperCase()}: ${error.message}`);
    }
}

// Helper functions
function showChartLoading() {
    document.getElementById('visualizationArea').innerHTML = `
        <div class="text-center p-5">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading chart...</span>
            </div>
            <p class="mt-2">Generating visualization...</p>
        </div>`;
}

function showSummaryLoading() {
    document.getElementById('summaryArea').innerHTML = `
        <div class="text-center p-5">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading summary...</span>
            </div>
            <p class="mt-2">Calculating statistics...</p>
        </div>`;
}
function displayResults(results) {
    // Clear any existing timeout
    if (processTimeout) {
        clearTimeout(processTimeout);
    }

    const queryResult = document.getElementById('queryResult');
    
    // Clear existing content first
    queryResult.innerHTML = '';
    
    if (!results || !results.length) {
        queryResult.innerHTML = '<div class="p-4 text-center">No results found</div>';
        return;
    }

    let tableHTML = '<table class="table table-striped table-hover"><thead><tr>';
    
    // Add headers
    const headers = Object.keys(results[0]);
    headers.forEach(header => {
        tableHTML += `<th>${header}</th>`;
    });
    
    tableHTML += '</tr></thead><tbody>';

    // Add rows
    results.forEach(row => {
        tableHTML += '<tr>';
        headers.forEach(header => {
            tableHTML += `<td>${row[header]}</td>`;
        });
        tableHTML += '</tr>';
    });

    tableHTML += '</tbody></table>';
    queryResult.innerHTML = tableHTML;
}

function updateVisualization(plotData) {
    const visualizationArea = document.getElementById('visualizationArea');
    if (plotData) {
        visualizationArea.innerHTML = `
            <div class="chart-wrapper">
                <img src="data:image/png;base64,${plotData}" class="img-fluid" alt="Data visualization">
            </div>`;
    } else {
        visualizationArea.innerHTML = '<div class="no-chart-message text-center p-5"><i class="fas fa-chart-area fa-3x text-muted mb-3"></i><h5 class="text-muted">No visualization available</h5></div>';
    }
}

function updateSummary(summary) {
    const summaryArea = document.getElementById('summaryArea');
    if (!summary || Object.keys(summary).length === 0) {
        summaryArea.innerHTML = '<div class="text-center p-4">No summary statistics available</div>';
        return;
    }

    let summaryHTML = '<div class="row g-4">';
    
    // Statistical Summary
    summaryHTML += `
        <div class="col-md-12">
            <div class="card h-100">
                <div class="card-body">
                    <h6 class="card-title">Statistical Summary</h6>
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>Column</th>
                                    <th>Mean</th>
                                    <th>Median</th>
                                    <th>Std Dev</th>
                                    <th>Min</th>
                                    <th>Max</th>
                                </tr>
                            </thead>
                            <tbody>
    `;

    for (const [column, stats] of Object.entries(summary)) {
        summaryHTML += `
            <tr>
                <td>${column}</td>
                <td>${stats.mean.toFixed(2)}</td>
                <td>${stats.median.toFixed(2)}</td>
                <td>${stats.std.toFixed(2)}</td>
                <td>${stats.min.toFixed(2)}</td>
                <td>${stats.max.toFixed(2)}</td>
            </tr>
        `;
    }

    summaryHTML += `
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>`;

    summaryArea.innerHTML = summaryHTML;
}

function updateAxisSelectors(columns) {
    const xAxis = document.getElementById('xAxis');
    const yAxis = document.getElementById('yAxis');
    
    xAxis.innerHTML = '';
    yAxis.innerHTML = '';
    
    columns.forEach(column => {
        xAxis.innerHTML += `<option value="${column}">${column}</option>`;
        yAxis.innerHTML += `<option value="${column}">${column}</option>`;
    });
}

// Replace the existing showError and showSuccess functions in main.js with these:
function showError(message) {
    const toastContainer = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = 'toast-notification error animate__animated animate__fadeInRight';
    toast.innerHTML = `
        <div class="toast-content">
            <i class="fas fa-exclamation-circle"></i>
            <span>${message}</span>
            <button type="button" class="toast-close">&times;</button>
        </div>`;
    
    toastContainer.appendChild(toast);
    
    toast.querySelector('.toast-close').addEventListener('click', () => {
        toast.classList.add('animate__fadeOutRight');
        setTimeout(() => toast.remove(), 300);
    });
    
    setTimeout(() => {
        if (toast.parentNode) {
            toast.classList.add('animate__fadeOutRight');
            setTimeout(() => toast.remove(), 300);
        }
    }, 5000);
}

function showSuccess(message) {
    const toastContainer = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = 'toast-notification success animate__animated animate__fadeInRight';
    toast.innerHTML = `
        <div class="toast-content">
            <i class="fas fa-check-circle"></i>
            <span>${message}</span>
            <button type="button" class="toast-close">&times;</button>
        </div>`;
    
    toastContainer.appendChild(toast);
    
    toast.querySelector('.toast-close').addEventListener('click', () => {
        toast.classList.add('animate__fadeOutRight');
        setTimeout(() => toast.remove(), 300);
    });
    
    setTimeout(() => {
        if (toast.parentNode) {
            toast.classList.add('animate__fadeOutRight');
            setTimeout(() => toast.remove(), 300);
        }
    }, 5000);
}

function createToastContainer() {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1050';
        document.body.appendChild(container);
    }
    return container;
}


// Move styles to head only when document is ready
document.addEventListener('DOMContentLoaded', function() {
    const style = document.createElement('style');
    style.textContent = `
        .toast-notification {
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 4px;
            color: white;
            width: 300px;
            animation: slideIn 0.5s;
        }
        .toast-notification.error {
            background-color: #dc3545;
        }
        .toast-notification.success {
            background-color: #198754;
        }
        .toast-content {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .toast-close {
            background: transparent;
            border: none;
            color: white;
            font-size: 1.2em;
            margin-left: auto;
            cursor: pointer;
            padding: 0 5px;
        }
        .toast-close:hover {
            opacity: 0.8;
        }
        @keyframes slideIn {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
        }
    `;
    document.head.appendChild(style);
});

function updateDataStats(previewHTML) {
    try {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = previewHTML;
        const table = tempDiv.querySelector('table');
        
        if (table) {
            const rowCount = table.getElementsByTagName('tr').length - 1; // Subtract header row
            const colCount = table.getElementsByTagName('th').length;
            
            document.getElementById('rowCount').textContent = rowCount;
            document.getElementById('colCount').textContent = colCount;
        }
    } catch (error) {
        showError('Error updating data statistics');
    }
}

function validateFile(file) {
    // Check file type
    if (!file.name.endsWith('.csv')) {
        showError('Please upload a CSV file');
        return false;
    }
    
    // Check file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
        showError('File size exceeds 10MB limit');
        return false;
    }
    
    return true;
}

function validateQuery(query) {
    if (!query.trim()) {
        showError('Query cannot be empty');
        return false;
    }
    
    if (query.length > 5000) {
        showError('Query is too long (max 5000 characters)');
        return false;
    }
    
    return true;
}