const improveButton = document.querySelector('#ai-improve');
const resumeText = document.querySelector('#resume-text');
const targetRole = document.querySelector('#target-role');
const aiStatus = document.querySelector('#ai-status');
const resumeFile = document.querySelector('#resume-file');
const fileName = document.querySelector('#file-name');

resumeFile?.addEventListener('change', () => {
    fileName.textContent = resumeFile.files[0]?.name || 'Choose PDF or DOCX';
});

if (improveButton) {
    improveButton.addEventListener('click', async () => {
        improveButton.disabled = true;
        improveButton.textContent = 'Improving...';
        aiStatus.textContent = '';
        try {
            const response = await fetch('/ai-improve', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({resume_text: resumeText.value, target_role: targetRole.value})
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Could not improve the draft.');
            resumeText.value = result.resume_text;
            aiStatus.textContent = 'Draft improved. Review it, then save your changes.';
            resumeText.focus();
        } catch (error) {
            aiStatus.textContent = error.message;
        } finally {
            improveButton.disabled = false;
            improveButton.textContent = 'Improve draft';
        }
    });
}

const categoryTabs = document.querySelectorAll('.category-tab');
const templateCards = document.querySelectorAll('.template-card');
categoryTabs.forEach((tab) => tab.addEventListener('click', () => {
    categoryTabs.forEach((item) => item.classList.remove('active'));
    tab.classList.add('active');
    const category = tab.dataset.category;
    templateCards.forEach((card) => {
        card.hidden = category !== 'all' && card.dataset.category !== category;
    });
}));

const builderForm = document.querySelector('#builder-form');
const preview = document.querySelector('#resume-preview');
if (builderForm && preview) {
    const draftKey = 'resume-atlas-builder-draft';
    const fields = builderForm.querySelectorAll('[data-preview]');
    const restoreDraft = () => {
        try {
            const draft = JSON.parse(localStorage.getItem(draftKey) || '{}');
            fields.forEach((field) => {
                if (!field.value && draft[field.name]) field.value = draft[field.name];
            });
        } catch (error) {
            localStorage.removeItem(draftKey);
        }
    };
    const updatePreview = (field) => {
        const target = preview.querySelector(`[data-target="${field.dataset.preview}"]`);
        if (target && field.value.trim()) target.textContent = field.value;
    };
    restoreDraft();
    fields.forEach((field) => {
        updatePreview(field);
        field.addEventListener('input', () => {
            updatePreview(field);
            const draft = Object.fromEntries([...fields].map((item) => [item.name, item.value]));
            localStorage.setItem(draftKey, JSON.stringify(draft));
        });
    });
    builderForm.addEventListener('submit', () => localStorage.removeItem(draftKey));
    const accentControl = document.querySelector('#accent-control');
    const fontControl = document.querySelector('#font-control');
    accentControl?.addEventListener('input', () => preview.style.setProperty('--accent', accentControl.value));
    fontControl?.addEventListener('change', () => preview.style.setProperty('--resume-font', `'${fontControl.value}', sans-serif`));
}
