(() => {
  const input = document.getElementById('photo-input');
  const preview = document.getElementById('photo-preview');
  input?.addEventListener('change', () => {
    const file = input.files?.[0];
    if (!file || !file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = event => { preview.src = event.target.result; preview.classList.add('updated'); };
    reader.readAsDataURL(file);
  });
})();
