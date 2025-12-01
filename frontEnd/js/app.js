const API_BASE_URL = 'https://dhl-tracking-api.onrender.com/api/v1';
//https://dhl-tracking-api.onrender.com/api/v1

// Tab switching
document.querySelectorAll('.tab-button').forEach(button => {
    button.addEventListener('click', () => {
        const tabId = button.dataset.tab;
        
        document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        
        button.classList.add('active');
        document.getElementById(tabId).classList.add('active');
    });
});

// Loading overlay
function showLoading() {
    document.getElementById('loading').classList.add('active');
}

function hideLoading() {
    document.getElementById('loading').classList.remove('active');
}

// Track single shipment
async function trackSingle() {
    const trackingNumber = document.getElementById('single-tracking').value.trim();
    const resultDiv = document.getElementById('single-result');
    
    if (!trackingNumber) {
        resultDiv.innerHTML = '<div class="error">Please enter a tracking number</div>';
        return;
    }
    
    showLoading();
    resultDiv.innerHTML = '';
    
    try {
        const response = await fetch(`${API_BASE_URL}/tracking/single/${trackingNumber}`);
        
        if (!response.ok) {
            const data = await response.json();
            resultDiv.innerHTML = `<div class="error">Error: ${data.detail || 'Failed to track shipment'}</div>`;
            hideLoading();
            return;
        }
        
        const data = await response.json();
        console.log('Tracking data received:', data);
        
        if (data && data.tracking_number) {
            resultDiv.innerHTML = formatDetailedTrackingResult(data);
        } else {
            resultDiv.innerHTML = '<div class="error">No tracking data received</div>';
        }
    } catch (error) {
        console.error('Tracking error:', error);
        resultDiv.innerHTML = `<div class="error">Connection error: ${error.message}</div>`;
    } finally {
        hideLoading();
    }
}

// Upload file
async function uploadFile() {
    const fileInput = document.getElementById('file-upload');
    const resultDiv = document.getElementById('upload-result');
    
    if (!fileInput.files[0]) {
        resultDiv.innerHTML = '<div class="error">Please select a file</div>';
        return;
    }
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    
    showLoading();
    resultDiv.innerHTML = '';
    
    try {
        const response = await fetch(`${API_BASE_URL}/tracking/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const data = await response.json();
            resultDiv.innerHTML = `<div class="error">Error: ${data.detail || 'Failed to process file'}</div>`;
            hideLoading();
            return;
        }
        
        const data = await response.json();
        console.log('Upload response:', data);
        
        let html = '<div class="success"><h4>File Processed Successfully</h4></div>';
        html += '<div class="batch-info">';
        html += `<h4>Processing Summary</h4>`;
        html += `<p><strong>Batch ID:</strong> ${data.batch_id || 'N/A'}</p>`;
        html += `<p><strong>Total Requested:</strong> ${data.total_requested || 0}</p>`;
        html += `<p><strong>Successful:</strong> ${data.successful || 0}</p>`;
        html += `<p><strong>Failed:</strong> ${data.failed || 0}</p>`;
        html += `<p><strong>Processing Time:</strong> ${data.processing_time ? data.processing_time.toFixed(2) : '0'}s</p>`;
        html += '</div>';
        
        if (data.results && data.results.length > 0) {
            html += '<h3 style="margin-top: 20px; margin-bottom: 10px;">Tracking Results</h3>';
            html += '<table><thead><tr>';
            html += '<th>Tracking Number</th>';
            html += '<th>Status Code</th>';
            html += '<th>Status Description</th>';
            html += '<th>Origin</th>';
            html += '<th>Destination</th>';
            html += '<th>Last Checked</th>';
            html += '</tr></thead><tbody>';
            
            data.results.forEach(result => {
                html += `<tr>
                    <td>${result.tracking_number || 'N/A'}</td>
                    <td>${result.status_code || 'N/A'}</td>
                    <td>${result.status || 'N/A'}</td>
                    <td>${result.origin || 'N/A'}</td>
                    <td>${result.destination || 'N/A'}</td>
                    <td>${result.last_checked ? new Date(result.last_checked).toLocaleString() : 'N/A'}</td>
                </tr>`;
            });
            
            html += '</tbody></table>';
        } else {
            html += '<div class="info" style="margin-top: 15px;">No results available to display. Check batch ID: ' + (data.batch_id || 'N/A') + '</div>';
        }
        
        resultDiv.innerHTML = html;
    } catch (error) {
        console.error('Upload error:', error);
        resultDiv.innerHTML = `<div class="error">Connection error: ${error.message}</div>`;
    } finally {
        hideLoading();
    }
}

// View batch results
async function viewBatchResults(batchId) {
    const resultDiv = document.getElementById('upload-result');
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE_URL}/tracking/history/batch/${batchId}`);
        
        if (!response.ok) {
            // If endpoint doesn't exist, show message
            resultDiv.innerHTML += '<div class="info">Batch results are stored in the database. Use the export feature to download them.</div>';
            hideLoading();
            return;
        }
        
        const data = await response.json();
        
        if (data.results && data.results.length > 0) {
            let html = '<div class="success">Batch Results</div>';
            html += '<table><thead><tr>';
            html += '<th>Tracking Number</th>';
            html += '<th>Status Code</th>';
            html += '<th>Status</th>';
            html += '<th>Origin</th>';
            html += '<th>Destination</th>';
            html += '<th>Last Checked</th>';
            html += '</tr></thead><tbody>';
            
            data.results.forEach(result => {
                html += `<tr>
                    <td>${result.tracking_number}</td>
                    <td>${result.status_code || 'N/A'}</td>
                    <td>${result.status || 'N/A'}</td>
                    <td>${result.origin || 'N/A'}</td>
                    <td>${result.destination || 'N/A'}</td>
                    <td>${result.last_checked ? new Date(result.last_checked).toLocaleString() : 'N/A'}</td>
                </tr>`;
            });
            
            html += '</tbody></table>';
            resultDiv.innerHTML += html;
        }
    } catch (error) {
        resultDiv.innerHTML += `<div class="info">Results stored. Use Export feature to download them.</div>`;
    } finally {
        hideLoading();
    }
}

// List recent exports
async function listRecentExports() {
    const limit = document.getElementById('export-limit').value;
    const resultDiv = document.getElementById('export-list');
    
    showLoading();
    resultDiv.innerHTML = '';
    
    try {
        const response = await fetch(`${API_BASE_URL}/tracking/exports/recent?limit=${limit}`);
        const data = await response.json();
        
        if (response.ok) {
            if (data.exports && data.exports.length > 0) {
                let html = '<div class="file-list">';
                data.exports.forEach(file => {
                    html += `
                        <div class="file-item">
                            <div class="file-info">
                                <div class="file-name">${file.filename}</div>
                                <div class="file-meta">
                                    ${file.created_at} | ${file.file_size} | ${file.record_count} records | ${file.export_type.toUpperCase()}
                                </div>
                            </div>
                            <div class="file-actions">
                                <button class="btn-small" onclick="downloadFile('${file.filename}')">Download</button>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
                resultDiv.innerHTML = html;
            } else {
                resultDiv.innerHTML = '<div class="info">No export files found</div>';
            }
        } else {
            resultDiv.innerHTML = `<div class="error">Error: ${data.detail || 'Failed to list exports'}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div class="error">Connection error: ${error.message}</div>`;
    } finally {
        hideLoading();
    }
}

// Download file
function downloadFile(filename) {
    window.open(`${API_BASE_URL}/tracking/download/${filename}`, '_blank');
}

// Export files
async function exportFiles(event) {
    if (event) event.preventDefault();
    
    const trackingText = document.getElementById('export-tracking').value.trim();
    const format = document.getElementById('export-format').value;
    const includeDetails = document.getElementById('export-details').checked;
    const resultDiv = document.getElementById('export-result');
    
    if (!trackingText) {
        resultDiv.innerHTML = '<div class="error">Please enter tracking numbers</div>';
        return false;
    }
    
    showLoading();
    resultDiv.innerHTML = '';
    
    try {
        const response = await fetch(`${API_BASE_URL}/tracking/export`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                tracking_numbers_text: trackingText,
                format: format,
                include_details: includeDetails
            })
        });
        const data = await response.json();
        
        if (response.ok) {
            resultDiv.innerHTML = `
                <div class="success">
                    <h4>Export Created Successfully</h4>
                    <p><strong>File:</strong> ${data.file_name}</p>
                    <p><strong>Format:</strong> ${format.toUpperCase()}</p>
                    <p><strong>Records Exported:</strong> ${data.record_count}</p>
                    <p><strong>Status:</strong> File is ready for download</p>
                    <button onclick="downloadFile('${data.file_name}')">Download File</button>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `<div class="error">Error: ${data.detail || 'Failed to create export'}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div class="error">Connection error: ${error.message}</div>`;
    } finally {
        hideLoading();
    }
    
    return false;
}

// Export batch
async function exportBatch(event) {
    if (event) event.preventDefault();
    
    const batchId = document.getElementById('batch-id').value.trim();
    const format = document.getElementById('batch-format').value;
    const resultDiv = document.getElementById('batch-export-result');
    
    if (!batchId) {
        resultDiv.innerHTML = '<div class="error">Please enter a batch ID</div>';
        return false;
    }
    
    showLoading();
    resultDiv.innerHTML = '';
    
    try {
        const response = await fetch(`${API_BASE_URL}/export/batch/${batchId}?format=${format}`);
        const data = await response.json();
        
        if (response.ok) {
            resultDiv.innerHTML = `
                <div class="success">
                    <h4>Batch Export Created Successfully</h4>
                    <p><strong>File:</strong> ${data.file_name}</p>
                    <p><strong>Records:</strong> ${data.record_count}</p>
                    <button onclick="downloadFile('${data.file_name}')">Download File</button>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `<div class="error">Error: ${data.detail || 'Failed to export batch'}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div class="error">Connection error: ${error.message}</div>`;
    } finally {
        hideLoading();
    }
    
    return false;
}

// Get statistics
async function getStatistics() {
    const resultDiv = document.getElementById('stats-result');
    
    showLoading();
    resultDiv.innerHTML = '';
    
    try {
        const response = await fetch(`${API_BASE_URL}/stats`);
        const data = await response.json();
        
        if (response.ok) {
            resultDiv.innerHTML = `
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Total Records</div>
                        <div class="stat-value">${data.total_tracking_records || 0}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">API Requests Today</div>
                        <div class="stat-value">${data.api_requests_today || 0}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Requests Remaining</div>
                        <div class="stat-value">${data.api_requests_remaining || 0}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Successful Today</div>
                        <div class="stat-value">${data.successful_requests_today || 0}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Failed Today</div>
                        <div class="stat-value">${data.failed_requests_today || 0}</div>
                    </div>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `<div class="error">Error: ${data.detail || 'Failed to get statistics'}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div class="error">Connection error: ${error.message}</div>`;
    } finally {
        hideLoading();
    }
}

// Get API usage
async function getApiUsage() {
    const resultDiv = document.getElementById('usage-result');
    
    showLoading();
    resultDiv.innerHTML = '';
    
    try {
        const response = await fetch(`${API_BASE_URL}/tracking/usage`);
        const data = await response.json();
        
        if (response.ok) {
            resultDiv.innerHTML = `
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Date</div>
                        <div class="stat-value">${data.date}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Requests Used</div>
                        <div class="stat-value">${data.requests_used}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Requests Remaining</div>
                        <div class="stat-value">${data.requests_remaining}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Daily Limit</div>
                        <div class="stat-value">${data.daily_limit}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Usage Percentage</div>
                        <div class="stat-value">${data.percentage_used}%</div>
                    </div>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `<div class="error">Error: ${data.detail || 'Failed to get API usage'}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div class="error">Connection error: ${error.message}</div>`;
    } finally {
        hideLoading();
    }
}

// Format tracking result (simple version for tables)
function formatTrackingResult(data) {
    let html = '<div class="tracking-result">';
    html += `<h3>Tracking Details</h3>`;
    html += `<div class="detail-row"><span class="detail-label">Tracking Number:</span><span class="detail-value">${data.tracking_number}</span></div>`;
    html += `<div class="detail-row"><span class="detail-label">Status Code:</span><span class="detail-value">${data.status_code || 'N/A'}</span></div>`;
    html += `<div class="detail-row"><span class="detail-label">Status Description:</span><span class="detail-value">${data.status || 'N/A'}</span></div>`;
    html += `<div class="detail-row"><span class="detail-label">Origin:</span><span class="detail-value">${data.origin || 'N/A'}</span></div>`;
    html += `<div class="detail-row"><span class="detail-label">Destination:</span><span class="detail-value">${data.destination || 'N/A'}</span></div>`;
    html += `<div class="detail-row"><span class="detail-label">Last Checked:</span><span class="detail-value">${data.last_checked ? new Date(data.last_checked).toLocaleString() : 'N/A'}</span></div>`;
    html += `<div class="detail-row"><span class="detail-label">Success:</span><span class="detail-value">${data.is_successful ? 'Yes' : 'No'}</span></div>`;
    
    if (data.error_message) {
        html += `<div class="detail-row"><span class="detail-label">Error:</span><span class="detail-value">${data.error_message}</span></div>`;
    }
    
    html += '</div>';
    return html;
}

// Format detailed tracking result (like PDF/DOCX format)
function formatDetailedTrackingResult(data) {
    let html = '<div class="success"><h4>Tracking Information Retrieved</h4></div>';
    html += '<table><thead><tr>';
    html += '<th>Tracking Number</th>';
    html += '<th>Status Code</th>';
    html += '<th>Status Description</th>';
    html += '<th>Origin</th>';
    html += '<th>Destination</th>';
    html += '<th>Last Checked</th>';
    html += '</tr></thead><tbody>';
    html += `<tr>
        <td>${data.tracking_number}</td>
        <td>${data.status_code || 'N/A'}</td>
        <td>${data.status || 'N/A'}</td>
        <td>${data.origin || 'N/A'}</td>
        <td>${data.destination || 'N/A'}</td>
        <td>${data.last_checked ? new Date(data.last_checked).toLocaleString() : 'N/A'}</td>
    </tr>`;
    html += '</tbody></table>';
    
    if (data.error_message) {
        html += `<div class="error" style="margin-top: 15px;"><strong>Error:</strong> ${data.error_message}</div>`;
    }
    
    return html;
}

