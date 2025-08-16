// static/js/admin_attempts.js
// JS для страницы: Админ → Журнал попыток
// Никаких Jinja-выражений здесь быть не должно — только data-атрибуты из шаблона

(function(){
    'use strict';
  
    // Утилита: делегирование событий
    function on(el, evt, selector, handler){
      el.addEventListener(evt, function(e){
        const t = e.target.closest(selector);
        if (t && el.contains(t)) handler(e, t);
      });
    }
  
    document.addEventListener('DOMContentLoaded', function(){
      // Сбрасывает пагинацию на первую страницу
      function resetToFirstPage(form){
        if (!form) return;
        let page = form.querySelector('input[name="page"]');
        if (!page) {
          page = document.createElement('input');
          page.type = 'hidden';
          page.name = 'page';
          form.appendChild(page);
        }
        page.value = '1';
      }
      // -------------------------------
      // 1) Модалка удаления попытки
      // -------------------------------
      const modalEl = document.getElementById('deleteAttemptModal');
      if (modalEl) {
        modalEl.addEventListener('show.bs.modal', function (event) {
          const button = event.relatedTarget;
          const title  = button ? button.getAttribute('data-attempt-title') : '';
          const url    = button ? button.getAttribute('data-delete-url')  : '';
          const nameEl = modalEl.querySelector('#deleteAttemptTitle');
          if (nameEl) nameEl.textContent = title || '';
          const form = modalEl.querySelector('form');
          if (form && url) form.setAttribute('action', url);
        });
      }
  
      // -------------------------------
      // 2) Автосабмит по смене "На странице"
      // -------------------------------
      const filterForm = document.querySelector('form[action*="/admin/attempts"][method="get"]');
      if (filterForm) {
        const perPage = filterForm.querySelector('select[name="per_page"]');
        if (perPage) {
          perPage.addEventListener('change', function(){
            resetToFirstPage(filterForm);
            filterForm.requestSubmit ? filterForm.requestSubmit() : filterForm.submit();
          });
        }
      }
  
      // -------------------------------
      // 3) UX: enter в полях фильтра отправляет форму
      // -------------------------------
      if (filterForm) {
        on(filterForm, 'keydown', 'input,select', function(e){
          if (e.key === 'Enter') {
            e.preventDefault();
            resetToFirstPage(filterForm);
            filterForm.requestSubmit ? filterForm.requestSubmit() : filterForm.submit();
          }
        });
      }

        // -------------------------------
    // 4) Быстрые пресеты дат (сегодня / неделя / месяц)
    // Кнопки должны иметь data-date-preset="today|7d|30d|week|month"
    // -------------------------------
    (function(){
        const filterForm = document.querySelector('form[action*="/admin/attempts"][method="get"]');
        if (!filterForm) return;

        // Поиск полей дат
        const fromEl = filterForm.querySelector('input[name="date_from"]');
        const toEl   = filterForm.querySelector('input[name="date_to"]');
        if (!fromEl || !toEl) return;

        function fmt(d){
        const y = d.getFullYear();
        const m = String(d.getMonth()+1).padStart(2,'0');
        const a = String(d.getDate()).padStart(2,'0');
        return `${y}-${m}-${a}`;
        }

        function startOfWeek(d){
        const dt = new Date(d.getFullYear(), d.getMonth(), d.getDate());
        const day = dt.getDay(); // 0 Sun ... 6 Sat
        const iso = (day === 0 ? 7 : day); // 1..7 Mon..Sun
        dt.setDate(dt.getDate() - (iso - 1)); // Monday
        return dt;
        }

        function endOfWeek(d){
        const s = startOfWeek(d);
        const e = new Date(s);
        e.setDate(s.getDate() + 6);
        return e;
        }

        function startOfMonth(d){ return new Date(d.getFullYear(), d.getMonth(), 1); }
        function endOfMonth(d){ return new Date(d.getFullYear(), d.getMonth()+1, 0); }

        document.querySelectorAll('[data-date-preset]').forEach(btn => {
        btn.addEventListener('click', function(){
            const now = new Date();
            let from = null, to = null;
            switch (btn.getAttribute('data-date-preset')) {
            case 'today':
                from = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                to   = new Date(from);
                break;
            case '7d':
            case 'last7':
                to   = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                from = new Date(to); from.setDate(to.getDate() - 6);
                break;
            case '30d':
            case 'last30':
                to   = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                from = new Date(to); from.setDate(to.getDate() - 29);
                break;
            case 'week':
                from = startOfWeek(now);
                to   = endOfWeek(now);
                break;
            case 'month':
                from = startOfMonth(now);
                to   = endOfMonth(now);
                break;
            default:
                return;
            }
            fromEl.value = fmt(from);
            toEl.value   = fmt(to);
            resetToFirstPage(filterForm);
            filterForm.requestSubmit ? filterForm.requestSubmit() : filterForm.submit();
        });
        });
    })();

      // 4.1) Сброс страницы при изменении фильтров (select/input)
      (function(){
        if (!filterForm) return;
        const selectors = [
          'select[name="student_id"]',
          'select[name="task_id"]',
          'select[name="topic_id"]',
          'input[name="date_from"]',
          'input[name="date_to"]'
        ];
        selectors.forEach(function(sel){
          const el = filterForm.querySelector(sel);
          if (el) {
            el.addEventListener('change', function(){
              resetToFirstPage(filterForm);
              filterForm.requestSubmit ? filterForm.requestSubmit() : filterForm.submit();
            });
          }
        });
      })();

    // -------------------------------
    // 5) Массовое удаление (только для админа)
    // Требуется разметка:
    //  - чекбоксы строк: .attempt-checkbox (value=id)
    //  - чекбокс «выбрать все»: #selectAllAttempts
    //  - кнопка удалить: #bulkDeleteAttemptsBtn[data-action="<url>"]
    //  - счётчик: #attemptsSelectedCount (опц.)
    //  - в документе должен быть скрытый input[name=csrf_token] (например, в любой форме на странице)
    // -------------------------------
    (function(){
        const table = document.querySelector('table');
        const selectAll = document.getElementById('selectAllAttempts');
        const delBtn = document.getElementById('bulkDeleteAttemptsBtn');
        const countEl = document.getElementById('attemptsSelectedCount');

        function getIds(){
        return Array.from(document.querySelectorAll('.attempt-checkbox:checked')).map(el => el.value);
        }

        function updateUI(){
        const ids = getIds();
        if (countEl) countEl.textContent = String(ids.length);
        if (delBtn) delBtn.disabled = ids.length === 0;
        }

        if (selectAll) {
        selectAll.addEventListener('change', function(){
            document.querySelectorAll('.attempt-checkbox').forEach(cb => { cb.checked = selectAll.checked; });
            updateUI();
        });
        }

        if (table) {
        table.addEventListener('change', function(e){
            const t = e.target;
            if (t && t.classList && t.classList.contains('attempt-checkbox')) updateUI();
        });
        }

        async function postForm(url, data){
        // Пытаемся найти CSRF токен в любом скрытом инпуте на странице
        const csrf = document.querySelector('input[name="csrf_token"]');
        const fd = new FormData();
        if (csrf) fd.append('csrf_token', csrf.value);
        (data.ids || []).forEach(id => fd.append('ids', id));
        return fetch(url, { method: 'POST', body: fd, credentials: 'same-origin' });
        }

        if (delBtn) {
        delBtn.addEventListener('click', async function(){
            const url = delBtn.getAttribute('data-action');
            const ids = getIds();
            if (!url || ids.length === 0) return;
            if (!confirm(`Удалить выбранные попытки (${ids.length})? Это действие нельзя отменить.`)) return;
            try {
            const resp = await postForm(url, { ids });
            if (resp.ok) {
                // Обновим страницу, чтобы увидеть изменения
                window.location.reload();
            } else {
                const text = await resp.text();
                alert('Ошибка удаления: ' + text);
            }
            } catch (e) {
            console.error(e);
            alert('Не удалось выполнить запрос. Проверьте соединение.');
            }
        });
        }

        // первичная инициализация
        updateUI();
    })();

    });
  })();
