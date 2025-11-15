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
            if (views[key]) { // Check if the element actually exists
                views[key].classList.remove('active');
            }
        }
        // Show the requested view
        if (views[viewId]) {
            views[viewId].classList.add('active');
        }
    }

    // Event Listeners for Navigation
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
    
    // Set Initial State: Start with the login view active
    switchView('login');


    // --- 2. Generic Show/Hide Password Logic ---
    const allToggles = document.querySelectorAll('.toggle-password');
    allToggles.forEach(toggle => {
        toggle.addEventListener('click', function () {
            // Find the password input field right before the toggle
            const passwordInput = this.previousElementSibling; 
            
            if (passwordInput && (passwordInput.type === 'password' || passwordInput.type === 'text')) {
                // Toggle the type attribute
                const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
                passwordInput.setAttribute('type', type);
                
                // Toggle the text
                this.textContent = type === 'password' ? 'Show' : 'Hide';
            }
        });
    });


    // --- 3. Password Length Validation ---
    // Get the form elements from the 'views' object we defined earlier
    const userRegisterForm = views.userRegister ? views.userRegister.querySelector('form') : null;
    const farmerRegisterForm = views.farmerRegister ? views.farmerRegister.querySelector('form') : null;

    const validatePassword = (event) => {
        // Find the password field within the form that was submitted
        const passwordInput = event.target.querySelector('input[name="password"]');
        
        if (passwordInput && passwordInput.value.length < 8) {
            // Prevent the form from being submitted to the backend
            event.preventDefault(); 
            // Inform the user
            alert('Password must be at least 8 characters long.');
        }
    };

    // Attach the validation function to the submit event of both registration forms
    if (userRegisterForm) {
        userRegisterForm.addEventListener('submit', validatePassword);
    }
    if (farmerRegisterForm) {
        farmerRegisterForm.addEventListener('submit', validatePassword);
    }

}); // --- End of DOMContentLoaded ---
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
            if (views[key]) { // Check if the element actually exists
                views[key].classList.remove('active');
            }
        }
        // Show the requested view
        if (views[viewId]) {
            views[viewId].classList.add('active');
        }
    }

    // Event Listeners for Navigation
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
    
    // Set Initial State: Start with the login view active
    switchView('login');


    // --- 2. Generic Show/Hide Password Logic ---
    const allToggles = document.querySelectorAll('.toggle-password');
    allToggles.forEach(toggle => {
        toggle.addEventListener('click', function () {
            // Find the password input field right before the toggle
            const passwordInput = this.previousElementSibling; 
            
            if (passwordInput && (passwordInput.type === 'password' || passwordInput.type === 'text')) {
                // Toggle the type attribute
                const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
                passwordInput.setAttribute('type', type);
                
                // Toggle the text
                this.textContent = type === 'password' ? 'Show' : 'Hide';
            }
        });
    });


    // --- 3. Password Length Validation ---
    const userRegisterForm = views.userRegister ? views.userRegister.querySelector('form') : null;
    const farmerRegisterForm = views.farmerRegister ? views.farmerRegister.querySelector('form') : null;

    const validatePassword = (event) => {
        // Find the password field within the form that was submitted
        const passwordInput = event.target.querySelector('input[name="password"]');
        
        if (passwordInput && passwordInput.value.length < 8) {
            // Prevent the form from being submitted to the backend
            event.preventDefault(); 
            // Inform the user
            alert('Password must be at least 8 characters long.');
        }
    };

    // Attach the validation function to the submit event of both registration forms
    if (userRegisterForm) {
        userRegisterForm.addEventListener('submit', validatePassword);
    }
    if (farmerRegisterForm) {
        farmerRegisterForm.addEventListener('submit', validatePassword);
    }

}); // --- End of DOMContentLoaded ---