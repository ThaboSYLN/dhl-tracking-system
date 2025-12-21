const startAutomation = document.getElementById('start-automation');

startAutomation.addEventListener('click', async () => {
    startAutomation.disabled = true;
    startAutomation.textContent = 'Running...';

    try {
        const response = await fetch('http://127.0.0.1:8000/api/v1/automation/trigger', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to trigger automation');
        }

        alert(
            `✅ ${data.message}\n\n` +
            `Files Found: ${data.files_found}\n` +
            `Processed: ${data.files_processed}\n` +
            `Failed: ${data.files_failed}\n` +
            `Reports Generated: ${data.reports_generated}\n` +
            `Time: ${data.processing_time}s`
        );

    } catch (error) {
        alert(`❌ ${error.message}`);
    } finally {
        startAutomation.disabled = false;
        startAutomation.textContent = 'Start';
    }
});

const uploadBtn = document.getElementById('upload-btn');
const fileInput = document.getElementById('upload-file');

uploadBtn.addEventListener('click', async () => {
    if (!fileInput.files.length) {
        alert('❌ Please select a file first');
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file); // MUST match endpoint param name

    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Uploading...';

    try {
        const response = await fetch('http://127.0.0.1:8000/api/v1/tracking/upload', {
            method: 'POST',
            body: formData
        });

        const text = await response.text();
        let data = {};

        try {
            data = text ? JSON.parse(text) : {};
        } catch {
            throw new Error('Invalid response from server');
        }

        if (!response.ok) {
            throw new Error(data.detail || 'File upload failed');
        }

        alert(
            `✅ File processed successfully\n\n` +
            `Total Requested: ${data.total_requested}\n` +
            `Successful: ${data.successful}\n` +
            `Failed: ${data.failed}\n` +
            `Batch ID: ${data.batch_id}\n` +
            `Processing Time: ${data.processing_time}s`
        );

         // Auto-download the generated PDF
        if (data.filename) {
            const downloadUrl = `http://127.0.0.1:8000/api/v1/tracking/download/${encodeURIComponent(data.filename)}`;
            window.open(downloadUrl, '_blank');  // ← Opens in new tab

            
        } else {
            console.warn('No PDF filename returned – auto-download skipped');
        }

        // Optional: reset input
        fileInput.value = '';

    } catch (error) {
        alert(`❌ ${error.message}`);
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Upload';
    }
});
