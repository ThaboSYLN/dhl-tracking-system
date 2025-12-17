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
