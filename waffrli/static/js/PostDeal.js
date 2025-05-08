
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('deal-form');
    const fields = Array.from(form.querySelectorAll('input:not([type="file"]):not([type="radio"]), select, textarea'));
    const requiredFields = fields.filter(field => field.hasAttribute('required'));
    const archiveButton = document.getElementById('archive-btn');
    const postButton = document.getElementById('post-btn');
    const fileInput = document.getElementById('image');
    const fileName = document.getElementById('file-name');
    const progressFill = document.getElementById('progress-fill');
    const progressPercentage = document.getElementById('progress-percentage');
    
    // Create hidden input for action if it doesn't exist
    let actionInput = document.getElementById('action-input');
    if (!actionInput) {
        actionInput = document.createElement('input');
        actionInput.type = 'hidden';
        actionInput.id = 'action-input';
        actionInput.name = 'action';
        form.appendChild(actionInput);
    }
    
    // Add hidden city field if it doesn't exist
    let cityField = document.getElementById('city-field');
    if (!cityField) {
        cityField = document.createElement('input');
        cityField.type = 'hidden';
        cityField.id = 'city-field';
        cityField.name = 'city';
        form.appendChild(cityField);
    }
    
    // Add hidden location field if it doesn't exist (this is what the server expects)
    let locationField = document.getElementById('location-field');
    if (!locationField) {
        locationField = document.createElement('input');
        locationField.type = 'hidden';
        locationField.id = 'location-field';
        locationField.name = 'location'; // Match the name the Django view expects
        form.appendChild(locationField);
    }
    
    // Store type elements
    const onlineStore = document.getElementById('online-store');
    const physicalStore = document.getElementById('physical-store');
    const locationMapContainer = document.getElementById('location-map-container');
    const onlineLocationContainer = document.getElementById('online-location-container');
    const locationSelect = document.getElementById('location');

    // Expiration date elements
    const defaultExpiration = document.getElementById('default-expiration');
    const customExpiration = document.getElementById('custom-expiration');
    const customDateContainer = document.getElementById('custom-date-container');
    const expirationDateInput = document.getElementById('expiration-date');

    // Check if we're in edit mode
    const pageHeader = document.querySelector('.page-header h1');
    const isEditMode = pageHeader ? pageHeader.textContent.includes('Edit') : false;
    
    // Set expiration date constraints (if elements exist)
    if (expirationDateInput) {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        expirationDateInput.min = tomorrow.toISOString().split('T')[0];

        const maxDate = new Date();
        maxDate.setDate(maxDate.getDate() + 30);
        expirationDateInput.max = maxDate.toISOString().split('T')[0];
    }
    
    // File upload display
    if (fileInput) {
        fileInput.addEventListener('change', function () {
            fileName.textContent = this.files && this.files[0] ? this.files[0].name : 'No file chosen';
            updateProgressBar();
        });
    }
    
    // Function to extract city and update both city and location fields
    const updateCityAndLocationFields = (address) => {
        if (!address) return false;
        
        const addressParts = address.split(',');
        let cityValue = "Amman"; // Default
        
        if (addressParts.length >= 2) {
            // Typically city is the second part in most address formats
            cityValue = addressParts[1].trim();
        } else if (addressParts.length === 1) {
            // Fallback to the first part if we can't extract a city part
            cityValue = addressParts[0].trim();
        }
        
        // Update both fields with the same value
        cityField.value = cityValue;
        locationField.value = cityValue;
        
        return true;
    };
    
    // Enhanced function to update city field based on store type
    const updateCityField = () => {
        if (onlineStore && onlineStore.checked && locationSelect) {
            // For online stores, copy the selected city value to both fields
            cityField.value = locationSelect.value;
            locationField.value = locationSelect.value;
            return true;
        } else if (physicalStore && physicalStore.checked) {
            // For physical stores, validate and extract city from formatted address
            const formattedAddress = document.getElementById('formatted_address');
            const latitude = document.getElementById('latitude');
            const longitude = document.getElementById('longitude');
            
            // Check if we have valid location data
            if (!formattedAddress.value || !latitude.value || !longitude.value) {
                return false;
            }
            
            if (formattedAddress.value) {
                return updateCityAndLocationFields(formattedAddress.value);
            }
        }
        
        return false;
    };
    
    // Store type handlers
    if (onlineStore) {
        onlineStore.addEventListener('change', function () {
            if (this.checked) {
                locationMapContainer.style.display = 'none';
                onlineLocationContainer.style.display = 'block';
                locationSelect.required = true;
                document.getElementById('latitude').value = '';
                document.getElementById('longitude').value = '';
                document.getElementById('formatted_address').value = '';
                
                // Update both city and location fields from dropdown when type changes
                if (locationSelect.value) {
                    cityField.value = locationSelect.value;
                    locationField.value = locationSelect.value;
                }
            }
            updateProgressBar();
        });
    }

    if (physicalStore) {
        physicalStore.addEventListener('change', function () {
            if (this.checked) {
                locationMapContainer.style.display = 'block';
                onlineLocationContainer.style.display = 'none';
                locationSelect.required = false;
                if (typeof map === 'undefined') {
                    loadGoogleMapsScript();
                }
                
                // Clear both fields - will be updated when map location is selected
                cityField.value = '';
                locationField.value = '';
            }
            updateProgressBar();
        });
    }

    // Listen for location dropdown changes - update both fields
    if (locationSelect) {
        locationSelect.addEventListener('change', function() {
            if (onlineStore && onlineStore.checked) {
                cityField.value = this.value;
                locationField.value = this.value;
            }
        });
    }

    // Expiration date handlers
    if (defaultExpiration && customExpiration) {
        defaultExpiration.addEventListener('change', function () {
            if (this.checked) {
                customDateContainer.style.display = 'none';
                expirationDateInput.required = false;
            }
            updateProgressBar();
        });

        customExpiration.addEventListener('change', function () {
            if (this.checked) {
                customDateContainer.style.display = 'block';
                expirationDateInput.required = true;
            }
            updateProgressBar();
        });
    }
    
    // Function to show notification messages
    const showNotification = (message, type = 'success') => {
        const notificationContainer = document.getElementById('notification-container');
        if (!notificationContainer) return;
        
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notificationContainer.appendChild(notification);

        setTimeout(() => {
            notification.classList.add('show');
        }, 10);

        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                notification.remove();
            }, 500);
        }, 3000);
    };
    
    // Function to update progress bar
    const updateProgressBar = () => {
        if (!progressFill || !progressPercentage) return;
        
        let filledFields = fields.filter(field => field.value.trim() !== '').length;

        // Count expiration option if selected
        if ((defaultExpiration && defaultExpiration.checked) || 
            (customExpiration && customExpiration.checked)) {
            filledFields++;
        }

        // Count image field if there's an uploaded file or we're in edit mode with an existing image
        if ((fileInput && fileInput.files && fileInput.files[0]) || 
            (isEditMode && fileName && fileName.textContent.includes('Current image'))) {
            filledFields++;
        }

        const totalFields = fields.length + 1; // +1 for image
        const percent = Math.round((filledFields / totalFields) * 100);

        progressFill.style.width = `${percent}%`;
        progressPercentage.textContent = `${percent}%`;
    };
    
    // Form validation
    const showErrorMessage = (field, messageId) => {
        const errorMessage = document.getElementById(messageId);
        if (errorMessage) {
            errorMessage.style.display = (!field.checkValidity() && field.value.trim() !== '') ? 'block' : 'none';
        }
    };

    // Form input validation
    if (form) {
        form.addEventListener('input', (event) => {
            const target = event.target;
            target.classList.toggle('invalid', !target.checkValidity() && target.value.trim() !== '');

            const fieldErrorMap = {
                'deal-url': 'url-error',
                'deal-title': 'title-error',
                'sale-price': 'sale-price-error',
                'list-price': 'list-price-error',
                'location': 'location-error',
                'description': 'description-error',
                'category': 'category-error',
                'store': 'store-error',
                'brand': 'brand-error',
                'expiration-date': 'date-error'
            };

            if (fieldErrorMap[target.id]) {
                showErrorMessage(target, fieldErrorMap[target.id]);
            }

            updateProgressBar();
        });
    }
    
    // Archive button handler
    if (archiveButton) {
        archiveButton.addEventListener('click', (e) => {
            // Prevent default behavior
            e.preventDefault();
            
            const message = isEditMode 
                ? 'Save this deal as a draft to complete later?' 
                : 'Archive this deal to save and complete later?';
                
            if (confirm(message)) {
                // Set the action value to 'archive'
                actionInput.value = 'archive';
                
                // Try to update city and location fields - but don't prevent submission if it fails
                updateCityField();
                
                // Remove required attribute from fields to allow incomplete submissions
                requiredFields.forEach(field => {
                    field.setAttribute('data-was-required', field.hasAttribute('required'));
                    field.removeAttribute('required');
                });
                
                // Submit the form
                form.submit();
            }
        });
    }

    // Post button handler with improved fixes
    if (postButton) {
        postButton.addEventListener('click', (e) => {
            // Prevent default form submission
            e.preventDefault();
            
            // Set action to post
            actionInput.value = 'post';
            
            // Handle different store types
            if (physicalStore && physicalStore.checked) {
                // Get map values
                const formattedAddress = document.getElementById('formatted_address');
                const latitude = document.getElementById('latitude');
                const longitude = document.getElementById('longitude');
                
                // If map has been used, check that we have all required values
                if (!formattedAddress.value || !latitude.value || !longitude.value) {
                    // Show error if map location is missing
                    showNotification('Please select a location on the map for the physical store.', 'error');
                    return;
                }
                
                // For physical stores, update both city and location fields from formatted address
                const addressParts = formattedAddress.value.split(',');
                if (addressParts.length >= 2) {
                    cityField.value = addressParts[1].trim();
                    locationField.value = addressParts[1].trim(); // Set location field to same value as city
                } else {
                    // Use Amman as default city for both fields
                    cityField.value = "Amman";
                    locationField.value = "Amman";
                }
                
            } else if (onlineStore && onlineStore.checked) {
                // For online stores, make sure city is selected from dropdown
                if (locationSelect && locationSelect.value) {
                    // Set both fields to the selected city value
                    cityField.value = locationSelect.value;
                    locationField.value = locationSelect.value;
                    
                } else {
                    showNotification('Please select a location for the online store.', 'error');
                    return;
                }
            }
            
            // Submit the form now that we have ensured both fields are populated
            form.submit();
        });
    }
    
    // Form submission handler
    if (form) {
        form.addEventListener('submit', function(e) {
            // Only validate if we're NOT archiving
            if (actionInput.value !== 'archive') {
                let allValid = true;
                
                // Check all required fields
                requiredFields.forEach(field => {
                    if (!field.checkValidity() || field.value.trim() === '') {
                        field.classList.add('invalid');
                        const errorId = field.id + '-error';
                        const errorElement = document.getElementById(errorId);
                        if (errorElement) {
                            errorElement.style.display = 'block';
                        }
                        allValid = false;
                    } else {
                        field.classList.remove('invalid');
                    }
                });
                
                // Make sure city and location fields have values
                if (!cityField.value || !locationField.value) {
                    allValid = false;
                    showNotification('Please provide a city location.', 'error');
                }
                
                // Special check for physical store
                if (physicalStore && physicalStore.checked) {
                    const latitude = document.getElementById('latitude');
                    const longitude = document.getElementById('longitude');
                    const formattedAddress = document.getElementById('formatted_address');
                    
                    if (!latitude.value || !longitude.value || !formattedAddress.value) {
                        allValid = false;
                        showNotification('Please select a location on the map for the physical store.', 'error');
                    }
                }
                
                // In edit mode, we don't require a new image if one already exists
                if (!isEditMode && fileInput && (!fileInput.files || !fileInput.files[0])) {
                    allValid = false;
                    showNotification('Please upload an image.', 'error');
                }
                
                if (!allValid) {
                    e.preventDefault();
                    showNotification('Please fill out all required fields correctly.', 'error');
                    window.scrollTo(0, 0); // Scroll to top to see error message
                }
            }
        });
    }
    
    // Initialize progress bar
    updateProgressBar();
    
    // If we're in edit mode and it's a physical store, load the map
    if (isEditMode && physicalStore && physicalStore.checked) {
        loadGoogleMapsScript();
    }
    
    // Initialize both city and location fields if needed
    if (onlineStore && onlineStore.checked && locationSelect && locationSelect.value) {
        cityField.value = locationSelect.value;
        locationField.value = locationSelect.value;
    }
});

// Initialize variables for Google Maps
let map;
let marker;
let geocoder;
let autocomplete;

// Add this function to check if location is in Jordan
function isLocationInJordan(addressComponents) {
    if (!addressComponents || !Array.isArray(addressComponents)) {
        return false;
    }

    // Look for Jordan as the country
    const countryComponent = addressComponents.find(
        component => component.types.includes("country")
    );

    if (!countryComponent) {
        return false;
    }

    // Check if the country is Jordan (both short and long names)
    return countryComponent.short_name === "JO" ||
        countryComponent.long_name.toLowerCase().includes("jordan");
}

// Extract city from address components
function extractCityFromAddressComponents(addressComponents) {
    if (!addressComponents || !Array.isArray(addressComponents)) {
        return null;
    }
    
    // Try to find locality (city) component
    const cityComponent = addressComponents.find(
        component => component.types.includes("locality") || 
                    component.types.includes("administrative_area_level_1")
    );
    
    if (cityComponent) {
        return cityComponent.long_name;
    }
    
    return null;
}

// Define the initMap function first
function initMap() {
    // Default location (center of Jordan)
    const defaultLocation = { lat: 31.9539, lng: 35.9106 };

    // Initialize map
    map = new google.maps.Map(document.getElementById("map"), {
        center: defaultLocation,
        zoom: 13,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
    });

    // Initialize geocoder for address lookup
    geocoder = new google.maps.Geocoder();

    // Create marker - using AdvancedMarkerElement to avoid deprecation warning
    try {
        // Try to use the new AdvancedMarkerElement if available
        marker = new google.maps.marker.AdvancedMarkerElement({
            position: defaultLocation,
            map: map,
            draggable: true,
        });

        // Add click event to the map
        map.addListener("click", (event) => {
            marker.position = event.latLng;
            updateLocationFields(event.latLng);
        });

        // Update fields when marker is dragged
        marker.addListener("dragend", () => {
            updateLocationFields(marker.position);
            map.panTo(marker.position);
        });
    } catch (e) {
        // Fall back to the old Marker if AdvancedMarkerElement is not available
        marker = new google.maps.Marker({
            position: defaultLocation,
            map: map,
            draggable: true,
            animation: google.maps.Animation.DROP,
        });

        // Update fields when marker is dragged
        marker.addListener("dragend", () => {
            const position = marker.getPosition();
            updateLocationFields(position);
            map.panTo(position);
        });

        // Add click event to the map
        map.addListener("click", (event) => {
            marker.setPosition(event.latLng);
            updateLocationFields(event.latLng);
        });
    }

    // Set up address autocomplete
    const addressInput = document.getElementById("address");
    autocomplete = new google.maps.places.Autocomplete(addressInput);
    autocomplete.setFields([
        "geometry",
        "formatted_address",
        "address_components",
    ]);

    // When a place is selected, update map and fields
    autocomplete.addListener("place_changed", () => {
        const place = autocomplete.getPlace();



        // Check if location is in Jordan
        if (!isLocationInJordan(place.address_components)) {
            alert("Sorry, our service is only available in Jordan at this time.");
            // Clear the address field
            document.getElementById("address").value = "";
            document.getElementById("formatted_address").value = "";
            document.getElementById("city-field").value = "";
            document.getElementById("location-field").value = ""; // Clear location field too
            return;
        }

        // Update map view
        map.setCenter(place.geometry.location);

        // Update marker position based on which marker type we're using
        if (marker.setPosition) {
            marker.setPosition(place.geometry.location);
        } else {
            marker.position = place.geometry.location;
        }

        map.setZoom(15);

        // Update fields
        updateLocationFields(place.geometry.location);
        document.getElementById("formatted_address").value = place.formatted_address;
        
        // Extract city and update city field
        const city = extractCityFromAddressComponents(place.address_components);
        if (city) {
            document.getElementById("city-field").value = city;
            document.getElementById("location-field").value = city; // Update location field too
        } else {
            // Fallback: use locality part of the formatted address
            const addressParts = place.formatted_address.split(',');
            if (addressParts.length >= 2) {
                document.getElementById("city-field").value = addressParts[1].trim();
                document.getElementById("location-field").value = addressParts[1].trim(); // Update location field too
            }
        }
    });
}

function updateLocationFields(location) {
    // Update hidden form fields
    document.getElementById("latitude").value = location.lat();
    document.getElementById("longitude").value = location.lng();

    // Get address from coordinates
    geocoder.geocode(
        { location: { lat: location.lat(), lng: location.lng() } },
        (results, status) => {
            if (status === "OK" && results[0]) {
                // Check if location is in Jordan
                if (!isLocationInJordan(results[0].address_components)) {
                    alert("Sorry, our service is only available in Jordan at this time.");
                    // Clear the form fields
                    document.getElementById("address").value = "";
                    document.getElementById("formatted_address").value = "";
                    document.getElementById("city-field").value = "";
                    document.getElementById("location-field").value = ""; // Clear location field too
                    return;
                }

                const address = results[0].formatted_address;
                document.getElementById("formatted_address").value = address;

                // Extract city and update both city and location fields
                const city = extractCityFromAddressComponents(results[0].address_components);
                if (city) {
                    document.getElementById("city-field").value = city;
                    document.getElementById("location-field").value = city; // Update location field too
                } else {
                    // Fallback: use locality part of the formatted address
                    const addressParts = address.split(',');
                    if (addressParts.length >= 2) {
                        document.getElementById("city-field").value = addressParts[1].trim();
                        document.getElementById("location-field").value = addressParts[1].trim(); // Update location field too
                    }
                }

                // Don't update the address input if the user is currently typing
                const addressInput = document.getElementById("address");
                if (!addressInput.matches(":focus")) {
                    addressInput.value = address;
                }
            }
        }
    );
}

// Load Google Maps API lazily - only when physical store is selected
function loadGoogleMapsScript() {
    if (document.getElementById('physical-store').checked && !window.googleMapsLoaded) {
        const script = document.createElement("script");
        script.src =
            "https://maps.googleapis.com/maps/api/js?key=AIzaSyDtfNpTlfiR1P3oEqtVWhtVWN8RSeu4xaY&libraries=places&callback=initMap";
        script.async = true;
        script.defer = true;
        document.head.appendChild(script);
        window.googleMapsLoaded = true;
    }
}