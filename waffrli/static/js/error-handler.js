// static/js/error-handler.js
document.addEventListener('DOMContentLoaded', function() {
  // Get all popup messages
  const popups = document.querySelectorAll('.popup-message');
  
  // Set timeout for each popup
  popups.forEach(popup => {
      // Auto-dismiss after 5 seconds
      setTimeout(() => {
          popup.classList.add('fade-out');
          popup.addEventListener('animationend', function() {
              popup.remove();
          });
      }, 7000);
  });
});



(function() {
    // Store the original console.error method
    const originalConsoleError = console.error;
  
    // Override console.error to capture errors
    console.error = function(...args) {
      // Call the original console.error
      originalConsoleError.apply(console, args);
      
      // Display the error in a nice popup
      displayErrorMessage(args.join(' '));
    };
  
    // Global error handler
    window.onerror = function(message, source, lineno, colno, error) {
      // Create a readable error message
      const errorMsg = `${message}\nLine: ${lineno}, Column: ${colno}`;
      
      // Display the error in a nice popup
      displayErrorMessage(errorMsg);
      
      // Return true to prevent the default browser error handling
      return true;
    };
  
    // Handler for unhandled promise rejections
    window.addEventListener('unhandledrejection', function(event) {
      displayErrorMessage(`Unhandled Promise Rejection: ${event.reason}`);
    });
  
    // Function to display error messages in a nice popup
    function displayErrorMessage(message) {
      // Don't show errors in production if you don't want users to see them
      if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
        // Optional: log to server instead
        // sendErrorToServer(message);
        message = "An error occurred. Our team has been notified.";
      }
  
      // Create popup container if it doesn't exist
      let container = document.querySelector('.js-error-container');
      if (!container) {
        container = document.createElement('div');
        container.className = 'js-error-container';
        document.body.appendChild(container);
      }
  
      // Create the error popup
      const popup = document.createElement('div');
      popup.className = 'js-error-popup';
      popup.innerHTML = `
        <div class="js-error-content">
          <div class="js-error-icon">
            <i class="fas fa-exclamation-circle"></i>
          </div>
          <div class="js-error-message">${message}</div>
          <button class="js-error-close">
            <i class="fas fa-times"></i>
          </button>
        </div>
      `;
  
      // Add to container
      container.appendChild(popup);
  
      // Add close button functionality
      const closeBtn = popup.querySelector('.js-error-close');
      closeBtn.addEventListener('click', function() {
        popup.classList.add('js-error-fade-out');
        popup.addEventListener('animationend', function() {
          popup.remove();
        });
      });
  
      // Auto-remove after 10 seconds
      setTimeout(() => {
        if (popup.parentNode) {
          popup.classList.add('js-error-fade-out');
          popup.addEventListener('animationend', function() {
            popup.remove();
          });
        }
      }, 7000);
    }
  
    // Helper function to get CSRF token
    function getCsrfToken() {
      const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
      return cookieValue || '';
    }
  })();