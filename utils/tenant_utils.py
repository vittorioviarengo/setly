import os

def get_tenant_dir(app, tenant_slug, subdir=None):
    """Get the directory path for a tenant's files.
    Args:
        app: Flask app instance
        tenant_slug: The tenant's URL slug
        subdir: Optional subdirectory (e.g., 'logos', 'images', 'uploads')
    """
    tenant_dir = os.path.join(app.config['TENANTS_BASE_DIR'], tenant_slug)
    if subdir:
        tenant_dir = os.path.join(tenant_dir, subdir)
    # Create directory if it doesn't exist
    if not os.path.exists(tenant_dir):
        os.makedirs(tenant_dir)
    return tenant_dir


def get_author_image_path(image_filename, tenant_slug=None, return_url=False, app=None):
    """
    Get the correct path for an author/artist image.
    Handles tenant-specific paths with fallback to shared directory.
    
    Args:
        image_filename: The image filename from database (can be URL or filename)
        tenant_slug: The tenant's slug (optional)
        return_url: If True, returns web URL path; if False, returns filesystem path
        app: Flask app instance (required if return_url=False for filesystem paths)
    
    Returns:
        str: URL path (e.g., '/static/tenants/vittorio/author_images/image.jpg')
             or filesystem path (e.g., '/path/to/static/tenants/vittorio/author_images/image.jpg')
    """
    # If it's already a full URL (http:// or https://), return as-is
    if image_filename and (image_filename.startswith('http://') or image_filename.startswith('https://')):
        return image_filename
    
    # If no image filename provided, return None
    if not image_filename:
        return None
    
    # Build the path based on tenant
    if tenant_slug:
        if return_url:
            # Return URL path for frontend
            path = f'/static/tenants/{tenant_slug}/author_images/{image_filename}'
        else:
            # Return filesystem path for backend
            if not app:
                raise ValueError("app instance required for filesystem paths")
            base_dir = os.path.dirname(os.path.dirname(__file__))  # Get project root
            path = os.path.join(base_dir, 'static', 'tenants', tenant_slug, 'author_images', image_filename)
            
            # Fallback to shared directory if file doesn't exist in tenant directory
            if not os.path.exists(path):
                fallback_path = os.path.join(base_dir, 'static', 'author_images', image_filename)
                if os.path.exists(fallback_path):
                    path = fallback_path
    else:
        # No tenant specified, use shared directory
        if return_url:
            path = f'/static/author_images/{image_filename}'
        else:
            if not app:
                raise ValueError("app instance required for filesystem paths")
            base_dir = os.path.dirname(os.path.dirname(__file__))
            path = os.path.join(base_dir, 'static', 'author_images', image_filename)
    
    return path





