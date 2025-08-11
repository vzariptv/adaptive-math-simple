document.addEventListener('DOMContentLoaded', function () {
    const flashContainer = document.getElementById('flash-messages');

    if (flashContainer) {
        flashContainer.querySelectorAll('.alert').forEach(alertEl => {
            alertEl.addEventListener('closed.bs.alert', function () {
                if (flashContainer.querySelectorAll('.alert').length === 0) {
                    flashContainer.style.display = 'none';
                }
            });
        });
    }
});
