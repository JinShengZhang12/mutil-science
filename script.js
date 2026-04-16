function setEditState(card, editable) {
  const button = card.querySelector('[data-toggle-edit]');
  const cells = card.querySelectorAll('[data-editable]');

  cells.forEach((cell) => {
    cell.setAttribute('contenteditable', editable ? 'true' : 'false');
    if (editable && !cell.dataset.placeholder) {
      cell.dataset.placeholder = '点击输入内容';
    }
  });

  button.classList.toggle('active', editable);
  button.textContent = editable ? '结束编辑' : '启用编辑';
}

function createRowFromTemplate(card) {
  const tbody = card.querySelector('tbody');
  const firstRow = tbody.querySelector('tr');
  const newRow = firstRow.cloneNode(true);

  newRow.querySelectorAll('[data-editable]').forEach((cell) => {
    cell.textContent = '';
    cell.setAttribute('contenteditable', 'false');
  });

  tbody.appendChild(newRow);
}

function initTableCards() {
  const cards = document.querySelectorAll('[data-table-card]');

  cards.forEach((card) => {
    setEditState(card, false);

    card.addEventListener('click', (event) => {
      const target = event.target;

      if (target.matches('[data-toggle-edit]')) {
        const isEditing = target.classList.contains('active');
        setEditState(card, !isEditing);
      }

      if (target.matches('[data-add-row]')) {
        createRowFromTemplate(card);
      }

      if (target.matches('[data-delete-row]')) {
        const tbody = card.querySelector('tbody');
        const rows = tbody.querySelectorAll('tr');
        const row = target.closest('tr');

        if (rows.length === 1) {
          row.querySelectorAll('[data-editable]').forEach((cell) => {
            cell.textContent = '';
          });
          return;
        }

        row.remove();
      }
    });
  });
}

async function exportToPdf() {
  const exportBtn = document.getElementById('exportPdfBtn');
  const statusMsg = document.getElementById('statusMsg');
  const exportArea = document.getElementById('export-area');

  exportBtn.disabled = true;
  statusMsg.textContent = '正在生成 PDF，请稍候...';

  try {
    const options = {
      margin: [8, 8, 8, 8],
      filename: `科研成果信息_${new Date().toISOString().slice(0, 10)}.pdf`,
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
      pagebreak: { mode: ['css', 'legacy'] }
    };

    await html2pdf().set(options).from(exportArea).save();
    statusMsg.textContent = 'PDF 导出成功。';
  } catch (error) {
    console.error(error);
    statusMsg.textContent = '导出失败，请检查浏览器控制台错误信息。';
  } finally {
    exportBtn.disabled = false;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initTableCards();
  document.getElementById('exportPdfBtn').addEventListener('click', exportToPdf);
});
