
  document.addEventListener('DOMContentLoaded', function () {
    // Like button functionality
    document.querySelectorAll(".like-btn").forEach((button) => {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
  
        if (button.hasAttribute('disabled')) {
          return; // Don't process if button is disabled
        }
  
        // Get the product ID from the data attribute
        const productId = this.getAttribute("data-product-id");
        const likeIcon = this.querySelector("i");
        
        // Get the correct count element - make sure to target only the count within THIS button
        const likeCount = this.querySelector(".rating-count"); 
        
        // Get the CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
  
        // Make AJAX request to the like endpoint
        fetch(`/like/${productId}/`, {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
            "X-Requested-With": "XMLHttpRequest"
          },
        })
        .then(response => {
          if (!response.ok) {
            throw new Error('Network response was not ok');
          }
          return response.json();
        })
        .then((data) => {
          console.log("Like response:", data); // Debug: log the response
          
          // Update the heart icon
          if (data.liked) {
            likeIcon.classList.remove("far");
            likeIcon.classList.add("fas");
          } else {
            likeIcon.classList.remove("fas");
            likeIcon.classList.add("far");
          }
          
          // Update the like count
          if (likeCount) {
            likeCount.textContent = data.likes_count;
          } else {
            console.error("Like count element not found within button:", button);
          }
        })
        .catch(error => {
          console.error('Error toggling like:', error);
        });
      });
    });
      
    // Save button functionality
    document.querySelectorAll(".save-btn").forEach((button) => {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
  
        if (button.hasAttribute('disabled')) {
          return; // Don't process if button is disabled
        }
  
        // Get the product ID from the data attribute
        const productId = this.getAttribute("data-product-id");
        const saveIcon = this.querySelector("i");
        
        // Get the CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
  
        // Make AJAX request to the save endpoint
        fetch(`/toggle-save/${productId}/`, {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
            "X-Requested-With": "XMLHttpRequest"
          },
        })
        .then(response => {
          if (!response.ok) {
            throw new Error('Network response was not ok');
          }
          return response.json();
        })
        .then((data) => {
          // Update the bookmark icon
          if (data.is_saved) {
            saveIcon.classList.remove("fa-regular");
            saveIcon.classList.add("fa-solid");
          } else {
            saveIcon.classList.remove("fa-solid");
            saveIcon.classList.add("fa-regular");
          }
        })
        .catch(error => {
          console.error('Error toggling save:', error);
        });
      });
    });
  
    // Comment button functionality - scroll to comment section
    document.querySelectorAll(".comment-btn").forEach((button) => {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
  
        if (button.hasAttribute('disabled')) {
          return; // Don't process if button is disabled
        }
  
        const productId = this.getAttribute("data-product-id");
        window.location.href = `/product/${productId}/#comment-section`;
      });
    });
  
  
    // Nearby deals 
    const productGrid = document.querySelector('.product-grid');
    const products = productGrid.querySelectorAll('.product-card');
    const prevBtn = document.querySelector('.prev-grid-btn');
    const nextBtn = document.querySelector('.next-grid-btn');
    let productsPerPage = 6;
    let currentPage = 0;
    let totalPages = Math.ceil(products.length / productsPerPage);

    // Responsive products per page
    function updateProductsPerPage() {
      if (window.innerWidth <= 576) {
        productsPerPage = 2;
      } else if (window.innerWidth <= 768) {
        productsPerPage = 3;
      } else if (window.innerWidth <= 992) {
        productsPerPage = 4;
      } else if (window.innerWidth <= 1400) {
        productsPerPage = 6;
      } else {
        productsPerPage = 8; 
      }
      totalPages = Math.ceil(products.length / productsPerPage);
      currentPage = Math.min(currentPage, totalPages - 1);
      showProducts(currentPage);
    }
  
    function showProducts(page) {
      const start = page * productsPerPage;
      const end = start + productsPerPage;
  
      products.forEach((product, index) => {
        if (index >= start && index < end) {
          product.style.display = 'block';
          product.style.animation = 'fadeIn 0.5s ease-in-out';
        } else {
          product.style.display = 'none';
        }
      });
    }
  
    prevBtn.addEventListener('click', () => {
      if (currentPage > 0) {
        currentPage--;
        showProducts(currentPage);
      }
    });
  
    nextBtn.addEventListener('click', () => {
      if (currentPage < totalPages - 1) {
        currentPage++;
        showProducts(currentPage);
      }
    });

    // Update on window resize
    window.addEventListener('resize', updateProductsPerPage);
  
    // Initialize first page
    updateProductsPerPage();
  
    // Hot deals
    const container = document.querySelector('.mini-products-container');
    const hotProducts = container.querySelectorAll('.mini-product');
    const hotPrevBtn = document.querySelector('.prev-btn');
    const hotNextBtn = document.querySelector('.next-btn');
    let hotCurrentIndex = 0;
    const hotProductsPerSlide = 3;
    const hotTotalSlides = Math.ceil(hotProducts.length / hotProductsPerSlide);
  
    function updateHotSlider() {
      const translateX = -hotCurrentIndex * (100 / hotProductsPerSlide);
      container.style.transform = `translateX(${translateX}%)`;
    }
  
    hotPrevBtn.addEventListener('click', () => {
      if (hotCurrentIndex > 0) {
        hotCurrentIndex--;
        updateHotSlider();
      }
    });
  
    hotNextBtn.addEventListener('click', () => {
      if (hotCurrentIndex < hotTotalSlides - 1) {
        hotCurrentIndex++;
        updateHotSlider();
      }
    });
  
  
  
    // Popular deals 
    const popularContainer = document.querySelector('.popular-products-container');
    const popularProducts = popularContainer.querySelectorAll('.mini-product');
    const popularPrevBtn = document.querySelector('.popular-prev-btn');
    const popularNextBtn = document.querySelector('.popular-next-btn');
    let popularCurrentIndex = 0;
    const productsPerSlide = 3;
    const totalSlides = Math.ceil(popularProducts.length / productsPerSlide);
  
    function updatePopularSlider() {
      const translateX = -popularCurrentIndex * (100 / productsPerSlide);
      popularContainer.style.transform = `translateX(${translateX}%)`;
    }
  
    popularPrevBtn.addEventListener('click', () => {
      if (popularCurrentIndex > 0) {
        popularCurrentIndex--;
        updatePopularSlider();
      }
    });
  
    popularNextBtn.addEventListener('click', () => {
      if (popularCurrentIndex < totalSlides - 1) {
        popularCurrentIndex++;
        updatePopularSlider();
      }
    });
  
    // Category sections navigation
    const columns = document.querySelectorAll('.category-selling-column, .Categoy-selling-column');
  
    columns.forEach(column => {
      const products = column.querySelectorAll('.mini-product-item');
      const prevBtn = column.querySelector('.prev-btn');
      const nextBtn = column.querySelector('.next-btn');
      let currentIndex = 0;
      const productsPerView = 2;
  
      // Initially show first two products
      products.forEach((product, index) => {
        if (index < productsPerView) {
          product.style.display = 'block';
          product.style.opacity = '1';
        } else {
          product.style.display = 'none';
          product.style.opacity = '0';
        }
      });
  
      function showProducts(startIndex) {
        products.forEach(product => {
          product.style.display = 'none';
          product.style.opacity = '0';
        });
  
        for (let i = 0; i < productsPerView; i++) {
          const index = (startIndex + i) % products.length;
          products[index].style.display = 'block';
          setTimeout(() => {
            products[index].style.opacity = '1';
          }, 50);
        }
      }
  
      prevBtn.addEventListener('click', () => {
        currentIndex = (currentIndex - productsPerView + products.length) % products.length;
        showProducts(currentIndex);
      });
  
      nextBtn.addEventListener('click', () => {
        currentIndex = (currentIndex + productsPerView) % products.length;
        showProducts(currentIndex);
      });
    });
  
    // Animations for scroll reveal
    const animateOnScroll = function () {
      const elements = document.querySelectorAll('.fade-in, .slide-up, .scale-in');
  
      elements.forEach(element => {
        const elementPosition = element.getBoundingClientRect().top;
        const windowHeight = window.innerHeight;
  
        if (elementPosition < windowHeight - 50) {
          element.style.opacity = "1";
          element.style.transform = element.classList.contains('slide-up') ? 'translateY(0)' :
            element.classList.contains('scale-in') ? 'scale(1)' : 'none';
        }
      });
    };
  
    // Run animation check on load and scroll
    window.addEventListener('load', animateOnScroll);
    window.addEventListener('scroll', animateOnScroll);
  
    // Featured Deals Slider functionality
    const featuredContainer = document.querySelector('.featured-deals-container');
    const featuredSlides = document.querySelectorAll('.featured-deal');
    const featuredPrevBtn = document.querySelector('.featured-deals-slider .prev-btn');
    const featuredNextBtn = document.querySelector('.featured-deals-slider .next-btn');
    let featuredCurrentIndex = 0;
  
    // Function to update slider position
    function updateFeaturedSlider() {
      featuredContainer.style.transform = `translateX(-${featuredCurrentIndex * 100}%)`;
    }
  
    // Previous button click handler
    featuredPrevBtn.addEventListener('click', () => {
      featuredCurrentIndex = (featuredCurrentIndex - 1 + featuredSlides.length) % featuredSlides.length;
      updateFeaturedSlider();
    });
  
    // Next button click handler
    featuredNextBtn.addEventListener('click', () => {
      featuredCurrentIndex = (featuredCurrentIndex + 1) % featuredSlides.length;
      updateFeaturedSlider();
    });
  
    // Auto-slide every 5 seconds
    setInterval(() => {
      featuredCurrentIndex = (featuredCurrentIndex + 1) % featuredSlides.length;
      updateFeaturedSlider();
    }, 5000);
  });