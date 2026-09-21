// Global JavaScript functions

// Initialize DataTables
$(document).ready(function() {
    $('.data-table').DataTable({
        "pageLength": 25,
        "language": {
            "search": "Search:",
            "lengthMenu": "Show _MENU_ entries",
            "info": "Showing _START_ to _END_ of _TOTAL_ entries",
            "paginate": {
                "first": "First",
                "last": "Last",
                "next": "Next",
                "previous": "Previous"
            }
        }
    });
});

// Real-time face recognition simulation
function startFaceRecognition() {
    const video = document.createElement('video');
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    
    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            video.srcObject = stream;
            video.play();
            
            setInterval(() => {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                context.drawImage(video, 0, 0, canvas.width, canvas.height);
                
                // In a real implementation, send this to the face recognition API
                // For now, just simulate
                simulateFaceRecognition();
            }, 5000);
        })
        .catch(err => {
            console.error("Camera error: ", err);
        });
}

function simulateFaceRecognition() {
    // Simulate random access attempts
    const statuses = ['granted', 'denied'];
    const methods = ['face', 'card', 'manual'];
    const names = ['John Doe', 'Jane Smith', 'Admin User', 'Unknown Person'];
    
    const randomStatus = statuses[Math.floor(Math.random() * statuses.length)];
    const randomMethod = methods[Math.floor(Math.random() * methods.length)];
    const randomName = names[Math.floor(Math.random() * names.length)];
    
    // Update dashboard with simulated data
    updateAccessLog(randomName, randomMethod, randomStatus);
}

function updateAccessLog(name, method, status) {
    // This would update the dashboard in real-time
    console.log(`Access attempt: ${name} via ${method} - ${status}`);
}

// Auto-refresh access logs every 30 seconds
setInterval(function() {
    if (window.location.pathname === '/') {
        fetch('/api/access-logs?page=1')
            .then(response => response.json())
            .then(data => {
                // Update the table with new data
                console.log('Refreshed access logs');
            });
    }
}, 30000);

// Handle keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl + L to lock door
    if (e.ctrlKey && e.key === 'l') {
        controlDoor('lock');
    }
    
    // Ctrl + U to unlock door
    if (e.ctrlKey && e.key === 'u') {
        controlDoor('unlock');
    }
    
    // Escape to close modals
    if (e.key === 'Escape') {
        $('.modal').modal('hide');
    }
});

// Toast notification system
function showToast(message, type = 'info') {
    const toast = $(`
        <div class="toast align-items-center text-white bg-${type} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `);
    
    $('#toastContainer').append(toast);
    const bsToast = new bootstrap.Toast(toast[0]);
    bsToast.show();
    
    // Remove toast after it hides
    toast.on('hidden.bs.toast', function() {
        $(this).remove();
    });
}

// Create toast container if it doesn't exist
if (!$('#toastContainer').length) {
    $('body').append(`
        <div id="toastContainer" class="position-fixed bottom-0 end-0 p-3" style="z-index: 11"></div>
    `);
}