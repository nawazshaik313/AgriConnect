// Save this as static/script.js
document.addEventListener('DOMContentLoaded', function() {

    // --- 1. View Switching Logic ---
    const views = {
        login: document.getElementById('login-view'),
        registerChooser: document.getElementById('register-chooser-view'),
        userRegister: document.getElementById('user-register-view'),
        farmerRegister: document.getElementById('farmer-register-view')
    };

    function switchView(viewId) {
        // Hide all views
        for (const key in views) {
            if (views[key]) {
                views[key].classList.remove('active');
            }
        }
        // Show the requested view
        if (views[viewId]) {
            views[viewId].classList.add('active');
        }
    }

    // Navigation Buttons
    const showRegisterChooser = document.getElementById('show-register-chooser');
    if (showRegisterChooser) {
        showRegisterChooser.addEventListener('click', (e) => {
            e.preventDefault();
            switchView('registerChooser');
        });
    }

    const showUserRegister = document.getElementById('show-user-register');
    if (showUserRegister) {
        showUserRegister.addEventListener('click', (e) => {
            e.preventDefault();
            switchView('userRegister');
        });
    }

    const showFarmerRegister = document.getElementById('show-farmer-register');
    if (showFarmerRegister) {
        showFarmerRegister.addEventListener('click', (e) => {
            e.preventDefault();
            switchView('farmerRegister');
        });
    }

    document.querySelectorAll('.show-login').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            switchView('login');
        });
    });

    // Start with login view active
    switchView('login');


    // --- 2. Show/Hide Password Logic ---
    const allToggles = document.querySelectorAll('.toggle-password');

    allToggles.forEach(toggle => {
        toggle.addEventListener('click', function () {
            const passwordInput = this.previousElementSibling;

            if (passwordInput && (passwordInput.type === 'password' || passwordInput.type === 'text')) {
                const type = passwordInput.getAttribute('type') === 'password'
                             ? 'text'
                             : 'password';
                
                passwordInput.setAttribute('type', type);

                // Change button text
                this.textContent = type === 'password' ? 'Show' : 'Hide';
            }
        });
    });


    // --- 3. Password Length Validation ---
    const userRegisterForm = views.userRegister ? views.userRegister.querySelector('form') : null;
    const farmerRegisterForm = views.farmerRegister ? views.farmerRegister.querySelector('form') : null;

    const validatePassword = (event) => {
        const passwordInput = event.target.querySelector('input[name="password"]');

        if (passwordInput && passwordInput.value.length < 8) {
            event.preventDefault();
            alert('Password must be at least 8 characters long.');
        }
    };

    if (userRegisterForm) {
        userRegisterForm.addEventListener('submit', validatePassword);
    }
    if (farmerRegisterForm) {
        farmerRegisterForm.addEventListener('submit', validatePassword);
    }

}); // End of DOMContentLoaded
