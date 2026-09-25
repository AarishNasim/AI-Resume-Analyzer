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

const loginForm = document.querySelector('#login-form');
const loginIdentifier = document.querySelector('#login-identifier');
const loginStatus = document.querySelector('#login-status');
const forgotReveal = document.querySelector('#forgot-reveal');
const forgotPassword = document.querySelector('#forgot-password');
const resetModal = document.querySelector('#reset-modal');
const closeResetModal = document.querySelector('#close-reset-modal');
const resetStatus = document.querySelector('#reset-status');
const resetOtpForm = document.querySelector('#reset-otp-form');
const newPasswordForm = document.querySelector('#new-password-form');

const showForgotPassword = () => {
    if (!forgotReveal) return;
    forgotReveal.classList.remove('is-hidden');
    forgotReveal.classList.add('is-visible');
    forgotReveal.setAttribute('aria-hidden', 'false');
};

const resetModalState = () => {
    resetOtpForm?.reset();
    newPasswordForm?.reset();
    resetOtpForm?.classList.remove('is-hidden');
    newPasswordForm?.classList.add('is-hidden');
};

const setResetModal = (visible) => {
    if (!resetModal) return;
    resetModal.classList.toggle('is-hidden', !visible);
    resetModal.classList.toggle('is-visible', visible);
    resetModal.setAttribute('aria-hidden', String(!visible));
};

const postJSON = async (url, body) => {
    const response = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
        body: JSON.stringify(body)
    });
    const result = await response.json();
    return {response, result};
};

loginForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const submitButton = loginForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    loginStatus.textContent = '';
    try {
        const {response, result} = await postJSON('/login', {
            identifier: loginIdentifier.value,
            password: loginForm.elements.password.value
        });
        if (!response.ok) {
            if (result.show_forgot_password) showForgotPassword();
            throw new Error(result.error || 'Invalid credentials.');
        }
        window.location.assign(result.redirect || '/dashboard');
    } catch (error) {
        loginStatus.textContent = error.message;
    } finally {
        submitButton.disabled = false;
    }
});

forgotPassword?.addEventListener('click', async () => {
    forgotPassword.disabled = true;
    resetStatus.textContent = 'Sending a verification code...';
    resetModalState();
    try {
        const {response, result} = await postJSON('/api/send-reset-otp', {identifier: loginIdentifier.value});
        if (!response.ok) throw new Error(result.error || 'Could not start password reset.');
        resetStatus.textContent = result.message;
        resetOtpForm?.classList.remove('is-hidden');
        newPasswordForm?.classList.add('is-hidden');
        setResetModal(true);
        resetOtpForm?.elements.otp.focus();
    } catch (error) {
        loginStatus.textContent = error.message;
    } finally {
        forgotPassword.disabled = false;
    }
});

closeResetModal?.addEventListener('click', () => {
    setResetModal(false);
    resetModalState();
});
resetModal?.addEventListener('click', (event) => {
    if (event.target === resetModal) {
        setResetModal(false);
        resetModalState();
    }
});

resetOtpForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
        const {response, result} = await postJSON('/api/verify-reset-otp', {
            identifier: loginIdentifier.value,
            otp: resetOtpForm.elements.otp.value
        });
        if (!response.ok) throw new Error(result.error || 'Invalid or expired code.');
        resetStatus.textContent = 'Code verified. Choose a new password.';
        resetOtpForm.classList.add('is-hidden');
        newPasswordForm.classList.remove('is-hidden');
        newPasswordForm.elements.new_password.focus();
    } catch (error) {
        resetStatus.textContent = error.message;
    }
});

newPasswordForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
        const {response, result} = await postJSON('/api/reset-password', {
            new_password: newPasswordForm.elements.new_password.value,
            confirm_password: newPasswordForm.elements.confirm_password.value
        });
        if (!response.ok) throw new Error(result.error || 'Could not update password.');
        setResetModal(false);
        loginStatus.textContent = result.message;
    } catch (error) {
        resetStatus.textContent = error.message;
    }
});

const registerForm = document.querySelector('#register-form');
const registerUsername = document.querySelector('#register-username');
const usernameStatus = document.querySelector('#username-status');
const registerStatus = document.querySelector('#register-status');
let usernameCheckTimer;

registerUsername?.addEventListener('input', () => {
    clearTimeout(usernameCheckTimer);
    const username = registerUsername.value.trim();
    usernameStatus.textContent = 'Checking availability...';
    if (!/^[A-Za-z0-9_]{3,30}$/.test(username)) {
        usernameStatus.textContent = '3-30 letters, numbers, or underscores.';
        return;
    }
    usernameCheckTimer = window.setTimeout(async () => {
        try {
            const response = await fetch(`/api/check-username?username=${encodeURIComponent(username)}`);
            const result = await response.json();
            usernameStatus.textContent = result.available ? 'Username is available.' : 'Username is already taken.';
            usernameStatus.classList.toggle('field-success', Boolean(result.available));
            usernameStatus.classList.toggle('field-error', !result.available);
        } catch (error) {
            usernameStatus.textContent = 'Could not check username availability.';
        }
    }, 300);
});

registerForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
        const formData = Object.fromEntries(new FormData(registerForm));
        const {response, result} = await postJSON('/register', formData);
        if (!response.ok) throw new Error(result.error || 'Could not create account.');
        window.location.assign('/login');
    } catch (error) {
        registerStatus.textContent = error.message;
    }
});
