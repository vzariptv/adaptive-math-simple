(function(){
    const $ = (s, r=document)=>r.querySelector(s);
    const $$ = (s, r=document)=>Array.from(r.querySelectorAll(s));
  
    const selectAll = $('#selectAll');
    const exportBtn = $('#exportSelectedBtn');
  
    function updateExportButton(){
      if (!exportBtn) return;
      const n = $$('.topic-checkbox:checked').length;
      exportBtn.disabled = n === 0;
      const cnt = $('#selectedCount'); if (cnt) cnt.textContent = n;
    }
  
    if (selectAll) {
      selectAll.addEventListener('change', () => {
        $$('.topic-checkbox').forEach(cb => cb.checked = selectAll.checked);
        updateExportButton();
      });
    }
    $$('.topic-checkbox').forEach(cb => cb.addEventListener('change', updateExportButton));
  
    document.addEventListener('DOMContentLoaded', () => {
      const modalEl = $('#deleteTopicModal');
      if (!modalEl) return;
      modalEl.addEventListener('show.bs.modal', (event) => {
        const btn = event.relatedTarget;
        if (!btn) return;
        const topicId = btn.getAttribute('data-topic-id');
        const topicName = btn.getAttribute('data-topic-name');
        modalEl.querySelector('#deleteTopicName').textContent = topicName || '';
        const form = modalEl.querySelector('form');
        if (form) form.action = `/admin/topics/${topicId}/delete`;
      });
    });
  
    window.exportSelected = async function exportSelected(){
      const ids = $$('.topic-checkbox:checked').map(cb => parseInt(cb.value));
      if (!ids.length) return alert('Выберите темы для экспорта');
  
      try {
        const resp = await fetch(window.TOPICS_EXPORT_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
          },
          body: JSON.stringify({topic_ids: ids})
        });
        if (!resp.ok) {
          const j = await resp.json().catch(()=>({message:'Server error'}));
          throw new Error(j.message || 'Ошибка при экспорте');
        }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `selected_topics_export_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.json`;
        document.body.appendChild(a); a.click(); a.remove();
        URL.revokeObjectURL(url);
      } catch (e) {
        alert('Ошибка при экспорте: ' + (e.message || e));
      }
    };
  })();
  