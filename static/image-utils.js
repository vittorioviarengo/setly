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
    img.onerror = function() {
        // Only set fallback if it's not already the fallback
        if (this.src !== window.location.origin + '/static/img/music-music-note-2.svg') {
            this.src = '/static/img/music-music-note-2.svg';
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

// Export for use in modules (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getAuthorImageUrl,
        createAuthorImage,
        setTenantSlug
    };
}




