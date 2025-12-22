const singleTrackBtn = document.getElementById('track-single-btn');
const trackingInput = document.getElementById('single-track');
const resultBox = document.getElementById('tracking-result');

singleTrackBtn.addEventListener('click', async () => {
    const trackingNumber = trackingInput.value.trim();

    if (!trackingNumber) {
        alert("Please enter a tracking number");
        return;
    }

    singleTrackBtn.disabled = true;
    singleTrackBtn.textContent = "Tracking...";
    resultBox.style.display = "none";

    try {
        const url = `http://127.0.0.1:8000/api/v1/tracking/single/${encodeURIComponent(trackingNumber)}`;

        const response = await fetch(url);
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Tracking failed");
        }

        const data = await response.json();

        // 🔹 Build result UI
        resultBox.innerHTML = `
        <div class="card-header">
            <h3>Tracking Result</h3>
            <button class="close-btn" id="close-result">&times;</button>
        </div>

        <div class="result-row">
            <span class="result-label">Status</span>
            <span class="status-badge">${data.status_code}</span>
        </div>

        <div class="result-row">
            <span class="result-label">Tracking Number</span>
            <span>${data.tracking_number}</span>
        </div>

        <div class="result-row">
            <span class="result-label">Origin</span>
            <span>${data.origin}</span>
        </div>

        <div class="result-row">
            <span class="result-label">Destination</span>
            <span>${data.destination}</span>
        </div>
    `;

    document.getElementById('close-result').addEventListener('click', () => {
    resultBox.style.display = "none";
    resultBox.innerHTML = "";
});


        resultBox.style.display = "block";

    } catch (error) {
        resultBox.innerHTML = `<p style="color:red;">${error.message}</p>`;
        resultBox.style.display = "block";
    } finally {
        singleTrackBtn.disabled = false;
        singleTrackBtn.textContent = "Track";
    }
});


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

        // alert(
        //     `✅ ${data.message}\n\n` +
        //     `Files Found: ${data.files_found}\n` +
        //     `Processed: ${data.files_processed}\n` +
        //     `Failed: ${data.files_failed}\n` +
        //     `Reports Generated: ${data.reports_generated}\n` +
        //     `Time: ${data.processing_time}s`
        // );

    } catch (error) {
        alert(`❌ ${error.message}`);
    } finally {
        startAutomation.disabled = false;
        startAutomation.textContent = 'Start';
    }
});

const uploadBtn = document.getElementById('upload-btn');
const fileInput = document.getElementById('upload-file');

uploadBtn.addEventListener('click', async (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (!fileInput.files.length) {
        alert('❌ Please select a file first');
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Uploading...';

    try {
        const response = await fetch(
            'http://127.0.0.1:8000/api/v1/tracking/upload',
            {
                method: 'POST',
                body: formData
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Upload failed');
        }

        alert(
            `✅ File processed successfully\n\n` +
            `Total Requested: ${data.total_requested}\n` +
            `Successful: ${data.successful}\n` +
            `Failed: ${data.failed}\n` +
            `Batch ID: ${data.batch_id}\n` +
            `Processing Time: ${data.processing_time}s`
        );

        if (data.filename) {
            const downloadUrl =
                `http://127.0.0.1:8000/api/v1/tracking/download/${data.filename}`;

            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = data.filename;

            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        fileInput.value = '';

    } catch (error) {
        console.error(error);
        alert(`❌ ${error.message}`);
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Upload';
        uploadBtn.textContent = 'Upload';
    }
});
