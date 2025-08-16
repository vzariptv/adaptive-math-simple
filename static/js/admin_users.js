// Страница «Управление пользователями».
// Логика чекбоксов, экспорт выбранных, и подстановка данных в модалку удаления.

(function () {
    const $  = (s, r=document) => r.querySelector(s);
    const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));
  
    const selectAll = $('#selectAllUsers');
    const exportBtn = $('#exportSelectedUsersBtn');
    const countSpan = $('#selectedUsersCount');
  
    function updateExportBtn() {
      if (!exportBtn) return;
      const n = $$('.user-checkbox:checked').length;
      exportBtn.disabled = n === 0;
      if (countSpan) countSpan.textContent = n;
    }
  
    if (selectAll) {
      selectAll.addEventListener('change', () => {
        $$('.user-checkbox').forEach(cb => cb.checked = selectAll.checked);
        updateExportBtn();
      });
    }
  
    $$('.user-checkbox').forEach(cb => cb.addEventListener('change', updateExportBtn));
    updateExportBtn();
  
    // Экспорт выбранных пользователей
    window.exportSelectedUsers = async function exportSelectedUsers() {
      const ids = $$('.user-checkbox:checked').map(cb => parseInt(cb.value, 10));
      if (!ids.length) {
        alert('Выберите пользователей для экспорта');
        return;
      }
      try {
        const resp = await fetch(window.USERS_EXPORT_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
          },
          body: JSON.stringify({ user_ids: ids })
        });
        if (!resp.ok) {
          // попытаемся прочитать текст ошибки из JSON
          let msg = 'Ошибка при экспорте';
          try {
            const j = await resp.json();
            if (j.message) msg = j.message;
          } catch (_) {}
          throw new Error(msg);
        }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `selected_users_export_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.json`;
        document.body.appendChild(a); a.click(); a.remove();
        URL.revokeObjectURL(url);
      } catch (e) {
        alert('Ошибка при экспорте: ' + (e.message || e));
      }
    };
  
    // Модалка удаления: подставляем имя и action
    document.addEventListener('DOMContentLoaded', () => {
      const modalEl = document.getElementById('deleteUserModal');
      if (!modalEl) return;
    
      modalEl.addEventListener('show.bs.modal', (event) => {
        const btn = event.relatedTarget;
        if (!btn) return;
    
        const userId   = btn.getAttribute('data-user-id');
        const userName = btn.getAttribute('data-user-name');
        const attempts = parseInt(btn.getAttribute('data-attempts') || '0', 10);
    
        // подставляем имя и число попыток
        const spanName = modalEl.querySelector('#deleteUserName');
        const spanCnt  = modalEl.querySelector('#attemptsCount');
        if (spanName) spanName.textContent = userName || '';
        if (spanCnt)  spanCnt.textContent  = isNaN(attempts) ? 0 : attempts;
    
        // выставляем action формы
        const form = modalEl.querySelector('form');
        if (form) form.action = `/admin/users/${userId}/delete`;
    
        // сброс чекбокса и скрытого поля
        const chk = modalEl.querySelector('#deleteAttemptsCheck');
        const hid = modalEl.querySelector('#deleteAttemptsField');
        if (chk) chk.checked = false;
        if (hid) hid.value = '0';
    
        // синхронизация чекбокса со скрытым полем
        if (chk && hid) {
          chk.addEventListener('change', () => {
            hid.value = chk.checked ? '1' : '0';
          }, { once: true }); // хватит одного подписчика на показ
        }
      });
    });
  })();
  