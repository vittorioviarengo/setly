/**
 * Centralized Image Management Utility
 * 
 * Handles all author/artist image path resolution with:
 * - Tenant-specific paths with fallback to shared directory
 * - External URL support (http/https)
 * - Automatic error handling with fallback image
 * 
 * Usage:
 *   const imageSrc = getAuthorImageUrl(song.image, tenantSlug);
 *   
 *   // Or create an image element directly:
 *   const imgElement = createAuthorImage(song.image, song.author, tenantSlug);
 */

/**
 * Get the correct URL for an author/artist image
 * @param {string} imageFilename - The image filename from database (can be URL or filename)
 * @param {string} tenantSlug - The tenant's slug (optional, extracted from window if not provided)
 * @returns {string} The full URL path to the image
 */
function getAuthorImageUrl(imageFilename, tenantSlug = null) {
    // If it's already a full URL (http:// or https://), return as-is
    if (imageFilename && (imageFilename.startsWith('http://') || imageFilename.startsWith('https://'))) {
        return imageFilename;
    }
    
    // If no image filename provided, return fallback
    if (!imageFilename) {
        return '/static/img/music-music-note-2.svg';
    }
    
    // If it already starts with a path (legacy data), return as-is with /static/ prefix if needed
    if (imageFilename.includes('/')) {
        if (imageFilename.startsWith('static/') || imageFilename.startsWith('/static/')) {
            return imageFilename.startsWith('/') ? imageFilename : '/' + imageFilename;
        }
        // Handle legacy format like "tenants/vittorio/author_images/filename.jpg"
        if (imageFilename.startsWith('tenants/')) {
            return '/static/' + imageFilename;
        }
        // Handle relative paths starting with author_images
        if (imageFilename.startsWith('author_images/')) {
            return '/static/' + imageFilename;
        }
    }
    
    // If no tenant slug provided, try to extract from global variable or URL
    if (!tenantSlug) {
        // Try to get from global variable (set in template)
        if (typeof window.tenantSlug !== 'undefined') {
            tenantSlug = window.tenantSlug;
        }
        // Otherwise try to extract from URL path
        else {
            const pathParts = window.location.pathname.split('/');
            // Assume first part after domain is tenant slug if it's not a known route
            const knownRoutes = ['search', 'queue', 'admin', 'songs', 'help', 'login', 'static'];
            if (pathParts.length > 1 && pathParts[1] && !knownRoutes.includes(pathParts[1])) {
                tenantSlug = pathParts[1];
            }
        }
    }
    
    // Build the path based on tenant (for new format with just filename)
    if (tenantSlug) {
        return `/static/tenants/${tenantSlug}/author_images/${imageFilename}`;
    } else {
        return `/static/author_images/${imageFilename}`;
    }
}

/**
 * Create an img element for an author/artist with proper error handling
 * @param {string} imageFilename - The image filename from database
 * @param {string} altText - Alt text for the image (usually artist name)
 * @param {string} tenantSlug - The tenant's slug (optional)
 * @param {string} cssClass - CSS class to apply to the image (optional)
 * @returns {HTMLImageElement} The configured img element
 */
function createAuthorImage(imageFilename, altText, tenantSlug = null, cssClass = 'author-image') {
    const img = document.createElement('img');
    img.src = getAuthorImageUrl(imageFilename, tenantSlug);
    img.alt = altText || 'Artist Image';
    
    if (cssClass) {
        img.classList.add(cssClass);
    }
    
    // Add error handler for fallback
    // Use a flag to prevent infinite loops if fallback image also fails
    img.dataset.fallbackAttempted = 'false';
    img.onerror = function() {
        // Only set fallback if we haven't tried already
        if (this.dataset.fallbackAttempted === 'false') {
            this.dataset.fallbackAttempted = 'true';
            // Check if this is already the fallback image
            const currentSrc = this.src;
            const fallbackSrc = '/static/img/music-music-note-2.svg';
            const absoluteFallback = window.location.origin + fallbackSrc;
            
            // If not already showing fallback, set it
            if (!currentSrc.includes('music-music-note-2.svg')) {
                this.src = fallbackSrc;
            }
        } else {
            // If fallback also failed, prevent further attempts
            this.onerror = null;
        }
    };
    
    return img;
}

/**
 * Set the tenant slug globally so it can be used by all image utilities
 * Call this once in your page header with the tenant slug from Flask
 * @param {string} slug - The tenant slug
 */
function setTenantSlug(slug) {
    window.tenantSlug = slug;
}

/**
 * Add global error handler for all images in the page
 * This ensures that any image with an author_images path that fails to load
 * will automatically fallback to the default image
 */
function setupGlobalImageErrorHandler() {
    // Only set up once
    if (window.imageErrorHandlerSetup) {
        return;
    }
    window.imageErrorHandlerSetup = true;
    
    // Default image path
    const defaultImagePath = '/static/img/music-music-note-2.svg';
    
    // Use window error handler to catch image load errors
    window.addEventListener('error', function(e) {
        const target = e.target;
        // Check if this is an image element
        if (target && target.tagName === 'IMG') {
            // Check if this is an author/artist image (has author_images in path or author-image class)
            const src = target.src || '';
            const isAuthorImage = (src.includes('author_images') || 
                                  src.includes('/tenants/') ||
                                  target.classList.contains('author-image')) &&
                                 !src.includes('music-music-note-2.svg'); // Not already the default
            
            if (isAuthorImage) {
                // Check if we haven't already tried to set the fallback
                if (target.dataset.fallbackAttempted !== 'true') {
                    target.dataset.fallbackAttempted = 'true';
                    target.src = defaultImagePath;
                    e.preventDefault(); // Prevent default error handling
                }
            }
        }
    }, true); // Use capture phase to catch errors early
    
    // Also use MutationObserver to add error handlers to dynamically added images
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                // Check if the added node is an img element
                if (node.tagName === 'IMG') {
                    addErrorHandlerToImage(node);
                }
                // Check for img elements inside the added node
                if (node.querySelectorAll) {
                    const images = node.querySelectorAll('img');
                    images.forEach(addErrorHandlerToImage);
                }
            });
        });
    });
    
    // Start observing
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // Helper function to add error handler to an image
    function addErrorHandlerToImage(img) {
        // Skip if already has handler or is not an author image
        if (img.dataset.errorHandlerAdded === 'true') {
            return;
        }
        
        const src = img.src || img.getAttribute('src') || '';
        const isAuthorImage = src.includes('author_images') || 
                             src.includes('/tenants/') ||
                             img.classList.contains('author-image');
        
        if (isAuthorImage) {
            img.dataset.errorHandlerAdded = 'true';
            // Add onerror handler using both addEventListener and onerror property
            // This ensures it works even if the image fails to load immediately
            const errorHandler = function() {
                if (this.dataset.fallbackAttempted !== 'true' && 
                    !this.src.includes('music-music-note-2.svg')) {
                    this.dataset.fallbackAttempted = 'true';
                    this.src = defaultImagePath;
                    // Prevent the error from showing in console by stopping propagation
                    if (window.event) {
                        window.event.stopPropagation();
                    }
                }
            };
            
            // Use both methods to ensure it works
            img.addEventListener('error', errorHandler, true);
            img.onerror = errorHandler;
            
            // Also check if image is already broken (src set but not loaded)
            if (img.complete && img.naturalWidth === 0 && !src.includes('music-music-note-2.svg')) {
                // Image failed to load, trigger fallback immediately
                errorHandler.call(img);
            }
        }
    }
    
    // Add handlers to existing images
    document.querySelectorAll('img').forEach(addErrorHandlerToImage);
}

// Set up the handler when the DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupGlobalImageErrorHandler);
} else {
    // DOM is already ready
    setupGlobalImageErrorHandler();
}

// Export for use in modules (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getAuthorImageUrl,
        createAuthorImage,
        setTenantSlug,
        setupGlobalImageErrorHandler
    };
}




