    
// Checkbox functionality
document.addEventListener('DOMContentLoaded', function() {
  const selectAll = document.getElementById('selectAll');
  const checkboxes = document.querySelectorAll('.task-checkbox');
  const exportBtn = document.getElementById('exportSelectedBtn');
  const selectedCount = document.getElementById('selectedCount');

  // Select all functionality
  if (selectAll) {
    selectAll.addEventListener('change', function() {
      checkboxes.forEach(cb => cb.checked = selectAll.checked);
      updateExportButton();
    });
  }

  // Individual checkbox change
  checkboxes.forEach(cb => {
    cb.addEventListener('change', updateExportButton);
  });

  function updateExportButton() {
    const checked = document.querySelectorAll('.task-checkbox:checked');
    const count = checked.length;
    
    if (exportBtn) {
      exportBtn.disabled = count === 0;
    }
    if (selectedCount) {
      selectedCount.textContent = count;
    }
  }

  // Delete modal setup
  const deleteModal = document.getElementById('deleteTaskModal');
  if (deleteModal) {
    deleteModal.addEventListener('show.bs.modal', function(event) {
      const button = event.relatedTarget;
      const taskId = button.getAttribute('data-task-id');
      const taskName = button.getAttribute('data-task-name');
      
      // Update modal content
      const taskNameElement = deleteModal.querySelector('#deleteTaskName');
      if (taskNameElement) {
        taskNameElement.textContent = taskName;
      }
      
      // Update form action (URL comes from data-delete-url attribute rendered server-side)
      const form = deleteModal.querySelector('form');
      const deleteUrl = button ? button.getAttribute('data-delete-url') : null;
      if (form && deleteUrl) {
        form.action = deleteUrl;
      }
    });
  }
});

// Export selected function
function exportSelected() {
  const checked = document.querySelectorAll('.task-checkbox:checked');
  const ids = Array.from(checked).map(cb => parseInt(cb.value));
  
  if (ids.length === 0) {
    alert('Выберите задания для экспорта');
    return;
  }

  fetch(window.TASKS_EXPORT_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
    },
    body: JSON.stringify({ task_ids: ids })
  })
  .then(response => {
    if (!response.ok) {
      return response.json().then(data => {
        throw new Error(data.message || 'Ошибка экспорта');
      });
    }
    return response.blob();
  })
  .then(blob => {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tasks_export_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  })
  .catch(error => {
    alert('Ошибка экспорта: ' + error.message);
  });
}