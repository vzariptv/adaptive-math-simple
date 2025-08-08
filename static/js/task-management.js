/**
 * Библиотека для управления заданиями
 * Функции импорта/экспорта заданий для админки и интерфейса преподавателя
 */

class TaskManager {
    constructor(importUrl, exportUrl) {
        this.importUrl = importUrl;
        this.exportUrl = exportUrl;
    }

    /**
     * Открывает модальное окно для импорта заданий
     */
    openImportModal() {
        const modal = document.getElementById('importModal');
        if (!modal) {
            console.error('Import modal not found');
            return;
        }
        
        modal.style.display = 'block';
        
        // Обработка закрытия модального окна
        const closeBtn = modal.querySelector('.close');
        if (closeBtn) {
            closeBtn.onclick = () => this.closeImportModal();
        }
        
        // Закрытие при клике вне модального окна
        window.onclick = (event) => {
            if (event.target === modal) {
                this.closeImportModal();
            }
        };
    }

    /**
     * Закрывает модальное окно импорта
     */
    closeImportModal() {
        const modal = document.getElementById('importModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    /**
     * Обрабатывает импорт заданий из файла
     */
    async handleImport(event) {
        event.preventDefault();
        
        const form = event.target;
        const formData = new FormData(form);
        const submitBtn = form.querySelector('button[type="submit"]');
        const statusDiv = document.getElementById('importResult');
        
        if (!submitBtn || !statusDiv) {
            console.error('Required elements not found');
            return;
        }
        
        const originalBtnText = submitBtn.innerHTML;
        
        // Показываем состояние загрузки
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Импорт...';
        statusDiv.style.display = 'none';
        
        try {
            // Получаем CSRF токен
            const csrfToken = this.getCSRFToken();
            if (csrfToken) {
                formData.append('csrf_token', csrfToken);
            }
            
            // Отправляем запрос на сервер
            const response = await fetch(this.importUrl, {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Ошибка сервера');
            }
            
            const data = await response.json();
            
            if (data.success) {
                statusDiv.className = 'alert alert-success';
                statusDiv.innerHTML = data.message;
                
                // Показываем ошибки, если они есть
                if (data.errors && data.errors.length > 0) {
                    const errorsList = data.errors.map(err => `<div class="small text-muted">${err}</div>`).join('');
                    statusDiv.innerHTML += `<div class="mt-2"><strong>Детали ошибок:</strong>${errorsList}</div>`;
                }
                
                // Обновляем страницу через 2 секунды, если были успешно импортированы задания
                if (data.imported > 0) {
                    setTimeout(() => window.location.reload(), 2000);
                }
            } else {
                throw new Error(data.message || 'Произошла ошибка при импорте');
            }
            
        } catch (error) {
            console.error('Ошибка при импорте:', error);
            statusDiv.className = 'alert alert-danger';
            statusDiv.innerHTML = `Ошибка: ${error.message}`;
        } finally {
            statusDiv.style.display = 'block';
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
        }
    }

    /**
     * Экспорт всех заданий
     */
    async exportTasks() {
        try {
            const response = await fetch(this.exportUrl, {
                method: 'GET',
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                throw new Error('Ошибка при экспорте заданий');
            }
            
            // Получаем данные как blob
            const blob = await response.blob();
            
            // Создаем ссылку для скачивания
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `tasks_export_${new Date().toISOString().split('T')[0]}.json`;
            
            document.body.appendChild(a);
            a.click();
            
            // Очищаем ресурсы
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
        } catch (error) {
            console.error('Ошибка при экспорте:', error);
            alert(`Ошибка при экспорте заданий: ${error.message}`);
        }
    }

    /**
     * Экспорт выбранных заданий
     */
    async exportSelectedTasks(taskIds) {
        if (!taskIds || taskIds.length === 0) {
            alert('Не выбрано ни одного задания для экспорта');
            return;
        }
        
        try {
            const response = await fetch(this.exportUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ task_ids: taskIds }),
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                throw new Error('Ошибка при экспорте выбранных заданий');
            }
            
            // Получаем данные как blob
            const blob = await response.blob();
            
            // Создаем ссылку для скачивания
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `selected_tasks_export_${new Date().toISOString().split('T')[0]}.json`;
            
            document.body.appendChild(a);
            a.click();
            
            // Очищаем ресурсы
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
        } catch (error) {
            console.error('Ошибка при экспорте выбранных заданий:', error);
            alert(`Ошибка при экспорте: ${error.message}`);
        }
    }

    /**
     * Очистка базы данных (только для админов)
     */
    async clearDatabase() {
        if (!confirm('Вы уверены, что хотите очистить ВСЮ базу данных? Это действие необратимо!')) {
            return;
        }
        
        if (!confirm('ВНИМАНИЕ! Будут удалены ВСЕ пользователи, задания и попытки решения. Продолжить?')) {
            return;
        }
        
        try {
            const response = await fetch('/admin/clear-database', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                throw new Error('Ошибка при очистке базы данных');
            }
            
            const data = await response.json();
            
            if (data.success) {
                alert('База данных успешно очищена');
                window.location.reload();
            } else {
                throw new Error(data.message || 'Произошла ошибка при очистке');
            }
            
        } catch (error) {
            console.error('Ошибка при очистке базы данных:', error);
            alert(`Ошибка: ${error.message}`);
        }
    }

    /**
     * Получает CSRF токен из meta тега или скрытого поля
     */
    getCSRFToken() {
        // Сначала пробуем получить из meta тега
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        if (metaToken) {
            return metaToken.getAttribute('content');
        }
        
        // Если нет, ищем скрытое поле
        const hiddenToken = document.querySelector('input[name="csrf_token"]');
        if (hiddenToken) {
            return hiddenToken.value;
        }
        
        console.warn('CSRF token not found');
        return null;
    }

    /**
     * Инициализация обработчиков событий
     */
    init() {
        // Обработчик формы импорта
        const importForm = document.getElementById('importForm');
        if (importForm) {
            importForm.addEventListener('submit', (e) => this.handleImport(e));
        }
        
        // Глобальные функции для обратной совместимости
        window.openImportModal = () => this.openImportModal();
        window.closeImportModal = () => this.closeImportModal();
        window.exportTasks = () => this.exportTasks();
        window.clearDatabase = () => this.clearDatabase();
    }
}

// Автоматическая инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    // Определяем URL-ы в зависимости от текущей страницы
    const currentPath = window.location.pathname;
    let importUrl, exportUrl;
    
    if (currentPath.includes('/admin/')) {
        importUrl = '/admin/tasks/import';
        exportUrl = '/admin/tasks/export';
    } else if (currentPath.includes('/teacher/') || currentPath.includes('/tasks/')) {
        importUrl = '/tasks/import';
        exportUrl = '/tasks/export';
    } else {
        // Дефолтные URL для админки
        importUrl = '/admin/tasks/import';
        exportUrl = '/admin/tasks/export';
    }
    
    // Создаем экземпляр менеджера заданий
    window.taskManager = new TaskManager(importUrl, exportUrl);
    window.taskManager.init();
});

// Экспорт для использования в модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TaskManager;
}
