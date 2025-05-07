
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

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        // Does this cookie string begin with the name we want?
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }




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
                // Change to outline heart
                heartIcon.classList.remove('fas');
                heartIcon.classList.add('far');
            } else {
                // Change to filled heart
                heartIcon.classList.remove('far'); 
                heartIcon.classList.add('fas');
            }
            
            // Send the AJAX request
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
    
    // Function to show notification message
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
});



// Community Voting - Completely Standalone Implementation
document.addEventListener('DOMContentLoaded', function() {
    // Find community voting elements
    const scoreElement = document.querySelector('.score');
    const goodDealBtn = document.querySelector('.good-deal');
    const badDealBtn = document.querySelector('.bad-deal');

    // Only proceed if all elements exist
    if (scoreElement && goodDealBtn && badDealBtn) {
        // Get the product ID for server updates
        const productId = document.querySelector('.voting-section')?.getAttribute('data-product-id');
        
        // Initialize voting state
        let voteScore = parseInt(scoreElement.textContent.replace('+', '')) || 0;
        let hasVoted = goodDealBtn.classList.contains('voted') ? 'up' : 
                       badDealBtn.classList.contains('voted') ? 'down' : null;

        // Handle "Good Deal" button click
        goodDealBtn.addEventListener('click', () => {
            if (hasVoted === 'up') {
                // Remove up vote
                voteScore--;
                hasVoted = null;
                goodDealBtn.classList.remove('voted');
            } else {
                if (hasVoted === 'down') {
                    // Change from down to up vote
                    voteScore += 2;
                    badDealBtn.classList.remove('voted');
                } else {
                    // Add up vote
                    voteScore++;
                }
                hasVoted = 'up';
                goodDealBtn.classList.add('voted');
            }
            
            // Update the score display
            updateScoreDisplay();
            
            // Notify server about the vote if product ID is available
            if (productId) {
                updateServerVote();
            }
        });

        // Handle "Bad Deal" button click
        badDealBtn.addEventListener('click', () => {
            if (hasVoted === 'down') {
                // Remove down vote
                voteScore++;
                hasVoted = null;
                badDealBtn.classList.remove('voted');
            } else {
                if (hasVoted === 'up') {
                    // Change from up to down vote
                    voteScore -= 2;
                    goodDealBtn.classList.remove('voted');
                } else {
                    // Add down vote
                    voteScore--;
                }
                hasVoted = 'down';
                badDealBtn.classList.add('voted');
            }
            
            // Update the score display
            updateScoreDisplay();
            
            // Notify server about the vote if product ID is available
            if (productId) {
                updateServerVote();
            }
        });
        
        // Function to update score display
        function updateScoreDisplay() {
            scoreElement.textContent = voteScore >= 0 ? `+${voteScore}` : voteScore;
        }
        
        // Function to update server about vote
        function updateServerVote() {
            fetch(`/community-vote/${productId}/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    vote: hasVoted,
                    score: voteScore
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to update vote on server');
                }
                return response.json();
            })
            .then(data => {
                // Optionally update score from server if it differs
                if (data.score !== undefined && data.score !== voteScore) {
                    voteScore = data.score;
                    updateScoreDisplay();
                }
                
                // Show notification
                if (hasVoted === 'up') {
                    showNotification('You voted this as a good deal!');
                } else if (hasVoted === 'down') {
                    showNotification('You voted this as a bad deal!');
                } else {
                    showNotification('You removed your vote.');
                }
            })
            .catch(error => {
                console.error('Error updating vote:', error);
                showNotification('Error updating your vote. Please try again.', 'error');
            });
        }
    }
    
    
    // Function to show notification message
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
    
    // --- COMMUNITY VOTING FUNCTIONALITY ---
    const scoreElement = document.querySelector('.score');
    const goodDealBtn = document.querySelector('.good-deal');
    const badDealBtn = document.querySelector('.bad-deal');

    // Only proceed if all elements exist
    if (scoreElement && goodDealBtn && badDealBtn) {
        // Get the product ID for server updates
        const productId = document.querySelector('.voting-section')?.getAttribute('data-product-id');
        
        // Initialize voting state
        let voteScore = parseInt(scoreElement.textContent.replace('+', '')) || 0;
        let hasVoted = goodDealBtn.classList.contains('voted') ? 'up' : 
                       badDealBtn.classList.contains('voted') ? 'down' : null;

        // Handle "Good Deal" button click
        goodDealBtn.addEventListener('click', () => {
            if (hasVoted === 'up') {
                // Remove up vote
                voteScore--;
                hasVoted = null;
                goodDealBtn.classList.remove('voted');
            } else {
                if (hasVoted === 'down') {
                    // Change from down to up vote
                    voteScore += 2;
                    badDealBtn.classList.remove('voted');
                } else {
                    // Add up vote
                    voteScore++;
                }
                hasVoted = 'up';
                goodDealBtn.classList.add('voted');
            }
            
            // Update the score display
            updateCommunityScoreDisplay();
            
            // Notify server about the vote if product ID is available
            if (productId) {
                updateCommunityServerVote();
            }
        });

        // Handle "Bad Deal" button click
        badDealBtn.addEventListener('click', () => {
            if (hasVoted === 'down') {
                // Remove down vote
                voteScore++;
                hasVoted = null;
                badDealBtn.classList.remove('voted');
            } else {
                if (hasVoted === 'up') {
                    // Change from up to down vote
                    voteScore -= 2;
                    goodDealBtn.classList.remove('voted');
                } else {
                    // Add down vote
                    voteScore--;
                }
                hasVoted = 'down';
                badDealBtn.classList.add('voted');
            }
            
            // Update the score display
            updateCommunityScoreDisplay();
            
            // Notify server about the vote if product ID is available
            if (productId) {
                updateCommunityServerVote();
            }
        });
        
        // Function to update score display
        function updateCommunityScoreDisplay() {
            scoreElement.textContent = voteScore >= 0 ? `+${voteScore}` : voteScore;
        }
        
        // Function to update server about vote
        function updateCommunityServerVote() {
            fetch(`/community-vote/${productId}/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    vote: hasVoted,
                    score: voteScore
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to update vote on server');
                }
                return response.json();
            })
            .then(data => {
                // Optionally update score from server if it differs
                if (data.score !== undefined && data.score !== voteScore) {
                    voteScore = data.score;
                    updateCommunityScoreDisplay();
                }
                
                // Show notification
                if (hasVoted === 'up') {
                    showNotification('You voted this as a good deal!');
                } else if (hasVoted === 'down') {
                    showNotification('You voted this as a bad deal!');
                } else {
                    showNotification('You removed your vote.');
                }
            })
            .catch(error => {
                console.error('Error updating vote:', error);
                showNotification('Error updating your vote. Please try again.', 'error');
            });
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
            const formData = new FormData(reportForm);
            const reason = formData.get('reason');
            const message = formData.get('message');
            
            reportModal.style.display = 'none';
            reportForm.reset();
            showNotification('Thank you for your report!');
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

function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

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