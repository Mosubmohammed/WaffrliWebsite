// Like button functionality
document.addEventListener('DOMContentLoaded', function() {
    // Find all like buttons on the page
    const likeButtons = document.querySelectorAll('.like-btn');
    
    // Process each like button
    likeButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Get the product ID from the data attribute
            const productId = this.getAttribute('data-product-id');
            if (!productId) {
                showNotification('Error: No product ID found', 'error');
                return;
            }
            
            // Find the heart icon
            const heartIcon = this.querySelector('i');
            if (!heartIcon) {
                showNotification('Error: No heart icon found', 'error');
                return;
            }
            
            // Check current state
            const isCurrentlyLiked = heartIcon.classList.contains('fas');
            
            // Toggle the icon immediately for better UX
            if (isCurrentlyLiked) {
                heartIcon.classList.remove('fas');
                heartIcon.classList.add('far');
            } else {
                heartIcon.classList.remove('far'); 
                heartIcon.classList.add('fas');
            }
            
            // Send the AJAX request to the existing like endpoint
            fetch(`/like/${productId}/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCookie('csrftoken')
                }
            })
            .then(response => {
                if (!response.ok) {
                    // Revert the icon if there's an error
                    if (isCurrentlyLiked) {
                        heartIcon.classList.remove('far');
                        heartIcon.classList.add('fas');
                    } else {
                        heartIcon.classList.remove('fas');
                        heartIcon.classList.add('far');
                    }
                    
                    return response.json().then(data => {
                        if (data.redirect_url) {
                            window.location.href = data.redirect_url;
                        }
                        throw new Error(data.error || 'An error occurred');
                    });
                }
                return response.json();
            })
            .then(data => {
                // Update the like count
                const likeCountElement = document.getElementById(`like-count-${productId}`);
                if (likeCountElement) {
                    likeCountElement.textContent = data.likes_count;
                }
                
                // Show notification if state changed
                if (data.is_liked !== isCurrentlyLiked) {
                    if (data.is_liked) {
                        heartIcon.classList.remove('far');
                        heartIcon.classList.add('fas');
                        showNotification('You liked this deal!');
                    } else {
                        heartIcon.classList.remove('fas');
                        heartIcon.classList.add('far');
                        showNotification('You removed your like from this deal');
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Error: ' + error.message, 'error');
            });
        });
    });
});

// Community Voting - Completely Rewritten
document.addEventListener('DOMContentLoaded', function() {
    // Remove any event listeners that might be causing the duplicate problem
    const goodDealBtn = document.querySelector('.good-deal');
    const badDealBtn = document.querySelector('.bad-deal');
    
    if (!goodDealBtn || !badDealBtn) {
        console.error('Vote buttons not found');
        return;
    }
    
    // Create new clean elements to replace the existing ones
    const newGoodDealBtn = goodDealBtn.cloneNode(true);
    const newBadDealBtn = badDealBtn.cloneNode(true);
    
    // Replace the old buttons with the cloned ones to remove any event listeners
    goodDealBtn.parentNode.replaceChild(newGoodDealBtn, goodDealBtn);
    badDealBtn.parentNode.replaceChild(newBadDealBtn, badDealBtn);
    
    // Get the voting section and score element
    const votingSection = document.querySelector('.voting-section');
    const scoreElement = document.querySelector('.score');
    
    if (!votingSection || !scoreElement) {
        console.error('Voting section or score element not found');
        return;
    }
    
    // Get the product ID
    const productId = votingSection.getAttribute('data-product-id');
    if (!productId) {
        console.error('No product ID found in voting section');
        return;
    }
    
    // Initialize voting state
    let voteScore = parseInt(scoreElement.textContent.replace('+', '')) || 0;
    let hasVoted = newGoodDealBtn.classList.contains('voted') ? 'up' : 
                 newBadDealBtn.classList.contains('voted') ? 'down' : null;
    
    // Single handler for the 'Good Deal' button
    newGoodDealBtn.addEventListener('click', function() {
        console.log('Good deal clicked, current state:', hasVoted);
        
        if (hasVoted === 'up') {
            // Remove up vote
            voteScore--;
            hasVoted = null;
            newGoodDealBtn.classList.remove('voted');
        } else {
            if (hasVoted === 'down') {
                // Change from down to up vote
                voteScore += 2;
                newBadDealBtn.classList.remove('voted');
            } else {
                // Add up vote
                voteScore++;
            }
            hasVoted = 'up';
            newGoodDealBtn.classList.add('voted');
        }
        
        // Update score display
        scoreElement.textContent = voteScore >= 0 ? `+${voteScore}` : voteScore;
        
        // Send vote to server
        sendVoteToServer(hasVoted, voteScore, productId);
    });
    
    // Single handler for the 'Bad Deal' button
    newBadDealBtn.addEventListener('click', function() {
        console.log('Bad deal clicked, current state:', hasVoted);
        
        if (hasVoted === 'down') {
            // Remove down vote
            voteScore++;
            hasVoted = null;
            newBadDealBtn.classList.remove('voted');
        } else {
            if (hasVoted === 'up') {
                // Change from up to down vote
                voteScore -= 2;
                newGoodDealBtn.classList.remove('voted');
            } else {
                // Add down vote
                voteScore--;
            }
            hasVoted = 'down';
            newBadDealBtn.classList.add('voted');
        }
        
        // Update score display
        scoreElement.textContent = voteScore >= 0 ? `+${voteScore}` : voteScore;
        
        // Send vote to server
        sendVoteToServer(hasVoted, voteScore, productId);
    });
    
    // Function to send vote to server
    function sendVoteToServer(vote, score, id) {
        console.log('Sending vote to server:', vote, score, id);
        
        fetch(`/community-vote/${id}/`, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                vote: vote,
                score: score
            })
        })
        .then(response => {
            if (!response.ok) {
                if (response.status === 401) {
                    window.location.href = '/login/?next=' + window.location.pathname;
                    throw new Error('Please log in to vote');
                }
                throw new Error('Failed to update vote on server');
            }
            return response.json();
        })
        .then(data => {
            // Update score from server if it differs
            if (data.score !== undefined && data.score !== score) {
                voteScore = data.score;
                scoreElement.textContent = voteScore >= 0 ? `+${voteScore}` : voteScore;
            }
            
            // Show notification
            if (vote === 'up') {
                showNotification('You voted this as a good deal!');
            } else if (vote === 'down') {
                showNotification('You voted this as a bad deal!');
            } else {
                showNotification('You removed your vote.');
            }
        })
        .catch(error => {
            console.error('Error updating vote:', error);
            showNotification('Error: ' + error.message, 'error');
            
            // Reset UI on error
            newGoodDealBtn.classList.remove('voted');
            newBadDealBtn.classList.remove('voted');
            
            if (data && data.original_score !== undefined) {
                scoreElement.textContent = data.original_score >= 0 ? 
                    `+${data.original_score}` : data.original_score;
            }
        });
    }
});

// Main functionality for product page
document.addEventListener('DOMContentLoaded', function() {
    // --- SAVE BUTTON FUNCTIONALITY ---
    const saveButtons = document.querySelectorAll('.save-btn');
    saveButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const productId = this.getAttribute('data-product-id');
            if (!productId) {
                showNotification('Error: No product ID found', 'error');
                return;
            }
            
            fetch(`/toggle-save/${productId}/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCookie('csrftoken')
                }
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        if (data.redirect_url) {
                            window.location.href = data.redirect_url;
                        }
                        throw new Error(data.error || 'An error occurred');
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.is_saved) {
                    this.innerHTML = '<i class="fas fa-bookmark"></i>';
                    this.title = 'Unsave this item';
                    showNotification(data.message || 'Item saved to your bookmarks!');
                } else {
                    this.innerHTML = '<i class="far fa-bookmark"></i>';
                    this.title = 'Save this item';
                    showNotification(data.message || 'Item removed from your bookmarks');
                }
            })
            .catch(error => {
                showNotification('Error: ' + error.message, 'error');
            });
        });
    });
    
    // --- MENU DROPDOWN FUNCTIONALITY ---
    const menuBtn = document.getElementById('menuBtn');
    const menuDropdown = document.getElementById('menuDropdown');
    
    if (menuBtn && menuDropdown) {
        // Toggle menu on button click
        menuBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            e.preventDefault();
            menuDropdown.classList.toggle('hidden');
            menuDropdown.classList.toggle('show');
        });
        
        // Close menu when clicking outside
        document.addEventListener('click', function(e) {
            if (!menuDropdown.contains(e.target) && !menuBtn.contains(e.target)) {
                menuDropdown.classList.add('hidden');
                menuDropdown.classList.remove('show');
            }
        });
        
        // Handle menu items with links
        const menuItems = menuDropdown.querySelectorAll('.menu-item');
        menuItems.forEach(function(item) {
            const link = item.querySelector('a');
            if (link) {
                item.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    window.location.href = link.href;
                });
            }
        });
    }
    
    // --- TAB FUNCTIONALITY ---
    const tabs = document.querySelectorAll('.Details-tab-btn');
    const contents = document.querySelectorAll('.Details-tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all tabs and contents
            tabs.forEach(t => t.classList.remove('Detailsactive'));
            contents.forEach(c => c.classList.remove('Detailsactive'));

            // Add active class to clicked tab and corresponding content
            tab.classList.add('Detailsactive');
            document.getElementById(tab.dataset.tab).classList.add('Detailsactive');
        });
    });
    
    // --- SLIDER FUNCTIONALITY ---
    const slider = document.querySelector('.deals-slider');
    const prevBtn = document.querySelector('.prev');
    const nextBtn = document.querySelector('.next');

    if (slider && prevBtn && nextBtn) {
        let currentSlide = 0;
        const slideCount = document.querySelectorAll('.deal-slide').length;

        prevBtn.addEventListener('click', () => {
            currentSlide = Math.max(0, currentSlide - 1);
            updateSlider();
        });

        nextBtn.addEventListener('click', () => {
            currentSlide = Math.min(slideCount - 5, currentSlide + 1);
            updateSlider();
        });

        function updateSlider() {
            slider.style.transform = `translateX(-${currentSlide * 20}%)`;
        }
    }
    
    // --- REPORT MODAL FUNCTIONALITY ---
    const reportButton = document.getElementById('reportButton');
    const reportModal = document.getElementById('reportModal');
    const closeModal = document.getElementById('closeModal');
    const reportForm = document.getElementById('reportForm');

    if (reportButton && reportModal) {
        reportButton.addEventListener('click', function() {
            reportModal.style.display = 'flex';
        });
    }

    if (closeModal && reportModal) {
        closeModal.addEventListener('click', function() {
            reportModal.style.display = 'none';
        });
    }

    if (reportModal) {
        reportModal.addEventListener('click', function(event) {
            if (event.target === reportModal) {
                reportModal.style.display = 'none';
            }
        });
    }

    if (reportForm) {
        reportForm.addEventListener('submit', function(event) {
            event.preventDefault();
            
            // Get the form data
            const formData = new FormData(reportForm);
            
            // Get product ID from the URL path - matches /product/123/
            const productId = window.location.pathname.split('/')[2]; 
            
            // Debug logs
            console.log("Submitting report for product ID:", productId);
            console.log("Form data reason:", formData.get('reason'));
            console.log("Form data message:", formData.get('message'));
            
            // Show loading state
            const submitButton = reportForm.querySelector('button[type="submit"]');
            const originalButtonText = submitButton.innerHTML;
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
            
            // Send report to server - using the URL pattern that matches your Django URLs
            fetch(`/product/${productId}/report/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            })
            .then(response => {
                console.log("Response status:", response.status);
                return response.json();
            })
            .then(data => {
                console.log("Response data:", data);
                reportModal.style.display = 'none';
                reportForm.reset();
                
                if (data.success) {
                    showNotification(data.message || 'Thank you for your report!');
                } else {
                    showNotification(data.message || 'Failed to submit report.', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('An error occurred while submitting your report. Please try again.', 'error');
            })
            .finally(() => {
                // Restore button state
                submitButton.disabled = false;
                submitButton.innerHTML = originalButtonText;
            });
        });
    }
    
    // --- COMMENT FORM AJAX FUNCTIONALITY ---
    const commentForm = document.getElementById('comment-form');
    const postCommentBtn = document.getElementById('post-comment-btn');
    
    if (commentForm && postCommentBtn) {
        commentForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const commentText = document.getElementById('comment-input').value.trim();
            if (!commentText) {
                alert('Please write a comment before posting.');
                return;
            }
            
            postCommentBtn.disabled = true;
            postCommentBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Posting...';
            
            const formData = new FormData(commentForm);
            
            fetch(commentForm.action, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    if (response.status === 401) {
                        throw new Error('Please log in to comment.');
                    }
                    return response.json().then(data => {
                        throw new Error(data.error || 'An error occurred');
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    addNewCommentToDOM(data.comment);
                    document.getElementById('comment-input').value = '';
                    showNotification('Your comment has been posted successfully!');
                    
                    // Update comment count if it exists
                    const commentCountElement = document.querySelector('.comments');
                    if (commentCountElement) {
                        const countText = commentCountElement.textContent;
                        const match = countText.match(/(\d+)/);
                        if (match) {
                            const currentCount = parseInt(match[1]);
                            const newCount = currentCount + 1;
                            commentCountElement.textContent = countText.replace(/(\d+)/, newCount);
                        }
                    }
                } else {
                    throw new Error(data.error || 'Error posting comment');
                }
            })
            .catch(error => {
                showNotification(error.message, 'error');
            })
            .finally(() => {
                postCommentBtn.disabled = false;
                postCommentBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Post Comment';
            });
        });
    }
    
    // Process any existing popup messages
    const popups = document.querySelectorAll('.popup-message');
    popups.forEach(popup => {
        setTimeout(() => {
            popup.classList.add('fade-out');
            popup.addEventListener('animationend', function() {
                popup.remove();
            });
        }, 5000);
    });
});

// --- GLOBAL FUNCTIONS ---

// Helper function to get CSRF token from cookies
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Add a new comment to the DOM
function addNewCommentToDOM(commentData) {
    // Create a new comment element
    const newComment = document.createElement('div');
    newComment.classList.add('comment');
    
    // Create the comment header
    const commentHeader = document.createElement('div');
    commentHeader.classList.add('comment-header');
    
    // Add avatar
    const avatar = document.createElement('img');
    avatar.classList.add('Section-avatar');
    avatar.src = commentData.user_image || '/static/images/default-avatar.jpg';
    avatar.alt = 'User Avatar';
    commentHeader.appendChild(avatar);
    
    // Add user details
    const userDetails = document.createElement('div');
    userDetails.classList.add('user-details');
    
    const userName = document.createElement('h3');
    userName.textContent = commentData.username;
    userDetails.appendChild(userName);
    
    const commentMeta = document.createElement('div');
    commentMeta.classList.add('comment-meta');
    
    const time = document.createElement('span');
    time.classList.add('time');
    time.textContent = commentData.time_ago || 'Just now';
    commentMeta.appendChild(time);
    
    const commentActions = document.createElement('div');
    commentActions.classList.add('comment-actions');
    commentMeta.appendChild(commentActions);
    
    userDetails.appendChild(commentMeta);
    commentHeader.appendChild(userDetails);
    
    // Add comment content
    const commentContent = document.createElement('div');
    commentContent.classList.add('comment-content');
    
    const commentBody = document.createElement('p');
    commentBody.textContent = commentData.text;
    commentContent.appendChild(commentBody);
    
    // Append header and content to the new comment
    newComment.appendChild(commentHeader);
    newComment.appendChild(commentContent);
    
    // Find the comment section
    const commentSection = document.querySelector('.comment-section');
    const noComments = commentSection.querySelector('.no-comments');
    
    if (noComments) {
        // Replace "no comments" message with the new comment
        noComments.replaceWith(newComment);
    } else {
        // Insert at the top of the comments
        const firstComment = commentSection.querySelector('.comment');
        if (firstComment) {
            commentSection.insertBefore(newComment, firstComment);
        } else {
            commentSection.insertBefore(newComment, commentSection.querySelector('.comment-form'));
        }
    }
}

// Delete confirmation function
function confirmDelete(productId) {
    if (confirm('Are you sure you want to delete this deal?')) {
        const form = document.getElementById('delete-form');
        form.action = form.action.replace(/\/0\//, `/${productId}/`);
        form.submit();
    }
}

// Function to archive a deal
function archiveDeal(dealId) {
    if (!dealId) {
      alert("Invalid deal ID.");
      return;
    }

    fetch(`/deal/${dealId}/archive/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/json'
      },
    })
    .then(response => {
      if (!response.ok) {
        throw new Error("Failed to archive deal.");
      }
      return response.json();
    })
    .then(data => {
      alert(data.message || "Deal archived successfully.");
      // Optionally remove the product card or reload the page
      location.reload();
    })
    .catch(error => {
      alert("An error occurred while archiving the deal.");
      console.error(error);
    });
}

// Show notification message
function showNotification(message, type = 'success') {
    // Create popup container if it doesn't exist
    let container = document.querySelector('.popup-messages-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'popup-messages-container';
        document.body.appendChild(container);
    }
    
    // Create popup message
    const popup = document.createElement('div');
    popup.className = `popup-message alert-${type === 'success' ? 'secondary' : 'danger'} fade show`;
    popup.setAttribute('role', 'alert');
    
    popup.innerHTML = `
        <div class="popup-content">
            <span class="popup-text">${message}</span>
            <button class="popup-close">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    // Add close button functionality
    const closeBtn = popup.querySelector('.popup-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            popup.classList.add('fade-out');
            popup.addEventListener('animationend', function() {
                popup.remove();
            });
        });
    }
    
    // Add to container
    container.appendChild(popup);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        popup.classList.add('fade-out');
        popup.addEventListener('animationend', function() {
            popup.remove();
        });
    }, 5000);
}

// Get CSRF token from DOM
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

// Follow/unfollow user functionality
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.follow-btn').forEach(button => {
        button.addEventListener('click', function () {
            const userId = this.dataset.userId;
            const isFollowing = this.dataset.following === 'true';
            const url = isFollowing ? `/unfollow/${userId}/` : `/follow/${userId}/`;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRFToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(res => res.json())
            .then(data => {
                const icon = this.querySelector('i');
                const text = this.querySelector('span');

                if (data.status === 'followed') {
                    icon.classList.remove('fa-user-plus');
                    icon.classList.add('fa-user-minus');
                    text.textContent = 'Unfollow';
                    this.dataset.following = 'true';
                } else if (data.status === 'unfollowed') {
                    icon.classList.remove('fa-user-minus');
                    icon.classList.add('fa-user-plus');
                    text.textContent = 'Follow';
                    this.dataset.following = 'false';
                }
            })
            .catch(err => console.error('Error:', err));
        });
    });
});