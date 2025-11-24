"""
Asynchronous Audit Logging Module

This module provides async logging functionality that writes audit logs
to the database in a background thread, preventing logging from blocking
HTTP requests.
"""

import json
import sqlite3
import threading
import queue
import os
import time
from datetime import datetime
from flask import request, session, has_request_context
import logging

# Thread-safe queue for log entries
_log_queue = queue.Queue(maxsize=10000)  # Max 10k pending logs
_log_worker_thread = None
_log_worker_running = False
_log_lock = threading.Lock()

# Logger for this module (logs errors in the logging system itself)
_logger = logging.getLogger(__name__)


def create_connection():
    """Create a database connection to the SQLite database."""
    database_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'songs.db')
    try:
        conn = sqlite3.connect(database_path, timeout=5.0)  # 5 second timeout
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        _logger.error(f"Error connecting to database for audit logging: {e}")
        return None


def _ensure_audit_logs_table():
    """Ensure the audit_logs table exists with all required columns."""
    conn = create_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='audit_logs'
        """)
        
        if not cursor.fetchone():
            # Create table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id INTEGER,
                    tenant_id INTEGER,
                    user_id INTEGER,
                    user_type TEXT,
                    user_name TEXT,
                    user_session_id TEXT,
                    details TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    referrer TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_tenant_action 
                ON audit_logs(tenant_id, action)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_created_at 
                ON audit_logs(created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_user_session 
                ON audit_logs(user_session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_entity 
                ON audit_logs(entity_type, entity_id)
            """)
            
            conn.commit()
            _logger.info("Created audit_logs table with indexes")
        else:
            # Table exists, check for missing columns and add them
            cursor.execute("PRAGMA table_info(audit_logs)")
            columns = {row[1] for row in cursor.fetchall()}
            
            required_columns = {
                'user_name': 'TEXT',
                'ip_address': 'TEXT',
                'user_agent': 'TEXT',
                'referrer': 'TEXT',
                'user_session_id': 'TEXT'
            }
            
            for col_name, col_type in required_columns.items():
                if col_name not in columns:
                    try:
                        cursor.execute(f"ALTER TABLE audit_logs ADD COLUMN {col_name} {col_type}")
                        _logger.info(f"Added column {col_name} to audit_logs table")
                    except sqlite3.OperationalError as e:
                        _logger.warning(f"Could not add column {col_name}: {e}")
            
            conn.commit()
        
        conn.close()
        return True
    except Exception as e:
        _logger.error(f"Error ensuring audit_logs table exists: {e}")
        if conn:
            conn.close()
        return False


def _log_worker():
    """
    Background worker thread that processes log entries from the queue
    and writes them to the database.
    """
    global _log_worker_running
    
    # Ensure table exists
    _ensure_audit_logs_table()
    
    _log_worker_running = True
    _logger.info("Audit log worker thread started")
    
    batch = []
    batch_size = 50  # Process logs in batches for better performance
    last_flush = time.time()
    flush_interval = 2.0  # Flush batch every 2 seconds even if not full
    
    while _log_worker_running:
        try:
            # Get log entry from queue with timeout
            try:
                log_entry = _log_queue.get(timeout=1.0)
            except queue.Empty:
                # Queue empty, flush batch if there are pending logs and enough time has passed
                if batch and (time.time() - last_flush) > flush_interval:
                    _flush_log_batch(batch)
                    batch = []
                    last_flush = time.time()
                continue
            
            batch.append(log_entry)
            
            # Flush batch if it's full
            if len(batch) >= batch_size:
                _flush_log_batch(batch)
                batch = []
                last_flush = time.time()
            
            _log_queue.task_done()
            
        except Exception as e:
            _logger.error(f"Error in audit log worker: {e}", exc_info=True)
            # Clear batch on error to prevent memory leak
            if batch:
                batch = []
    
    # Flush any remaining logs before shutdown
    if batch:
        _flush_log_batch(batch)
    
    _logger.info("Audit log worker thread stopped")


def _flush_log_batch(batch):
    """Write a batch of log entries to the database."""
    if not batch:
        return
    
    conn = create_connection()
    if not conn:
        _logger.error("Could not create database connection for audit logs")
        return
    
    try:
        cursor = conn.cursor()
        
        for log_entry in batch:
            try:
                cursor.execute("""
                    INSERT INTO audit_logs 
                    (action, entity_type, entity_id, tenant_id, user_id, user_type,
                     user_name, user_session_id, details, ip_address, user_agent, referrer)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_entry.get('action'),
                    log_entry.get('entity_type'),
                    log_entry.get('entity_id'),
                    log_entry.get('tenant_id'),
                    log_entry.get('user_id'),
                    log_entry.get('user_type'),
                    log_entry.get('user_name'),
                    log_entry.get('user_session_id'),
                    log_entry.get('details'),
                    log_entry.get('ip_address'),
                    log_entry.get('user_agent'),
                    log_entry.get('referrer')
                ))
            except Exception as e:
                _logger.error(f"Error inserting audit log entry: {e}, entry: {log_entry}")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        _logger.error(f"Error flushing audit log batch: {e}", exc_info=True)
        if conn:
            conn.close()


def _start_log_worker():
    """Start the background worker thread for processing logs."""
    global _log_worker_thread, _log_worker_running
    
    with _log_lock:
        if _log_worker_thread is None or not _log_worker_thread.is_alive():
            _log_worker_running = True
            _log_worker_thread = threading.Thread(
                target=_log_worker,
                name="AuditLogWorker",
                daemon=True  # Daemon thread - will be killed when main thread exits
            )
            _log_worker_thread.start()
            _logger.info("Started audit log worker thread")


def _stop_log_worker():
    """Stop the background worker thread (for testing/shutdown)."""
    global _log_worker_running
    
    _log_worker_running = False
    # Wait for queue to be processed (with timeout)
    try:
        _log_queue.join(timeout=5.0)
    except:
        pass


def log_event(action, entity_type, entity_id=None, details=None, tenant_id=None,
              user_id=None, user_type=None, user_name=None, user_session_id=None,
              ip_address=None, user_agent=None, referrer=None):
    """
    Log an event to the audit_logs table asynchronously.
    
    Args:
        action: Action name (e.g., 'song_requested', 'tenant_login')
        entity_type: Type of entity (e.g., 'song', 'request', 'tenant')
        entity_id: ID of the entity
        details: Dictionary with additional event data (will be JSON-serialized)
        tenant_id: Tenant ID
        user_id: User ID (for admins)
        user_type: 'end_user', 'tenant_admin', or 'superadmin'
        user_name: End user name (from session)
        user_session_id: User session identifier
        ip_address: Client IP address
        user_agent: Browser user agent
        referrer: HTTP referrer
    
    This function is non-blocking - it adds the log entry to a queue
    and returns immediately. The actual database write happens in a
    background thread.
    """
    # Start worker if not already running
    _start_log_worker()
    
    # Get context from Flask request/session if available
    if has_request_context():
        if ip_address is None:
            ip_address = request.remote_addr if request else None
        if user_agent is None:
            user_agent = request.headers.get('User-Agent') if request else None
        if referrer is None:
            referrer = request.headers.get('Referer') if request else None
        
        # Get tenant_id from session if not provided
        if not tenant_id and session:
            tenant_id = session.get('tenant_id')
        
        # Get user_session_id from session if not provided
        if not user_session_id and session:
            user_session_id = session.get('user_session_id')
        
        # Get user_name from session if not provided
        if not user_name and session:
            user_name = session.get('user_name')
    
    # Serialize details to JSON
    details_json = None
    if details:
        try:
            details_json = json.dumps(details) if isinstance(details, dict) else str(details)
        except (TypeError, ValueError) as e:
            _logger.warning(f"Could not serialize log details: {e}")
            details_json = str(details)
    
    # Create log entry
    log_entry = {
        'action': str(action),
        'entity_type': str(entity_type),
        'entity_id': entity_id,
        'tenant_id': tenant_id,
        'user_id': user_id,
        'user_type': user_type,
        'user_name': user_name,
        'user_session_id': user_session_id,
        'details': details_json,
        'ip_address': ip_address,
        'user_agent': user_agent,
        'referrer': referrer
    }
    
    # Add to queue (non-blocking with timeout to prevent hanging)
    try:
        _log_queue.put(log_entry, timeout=0.1, block=False)
    except queue.Full:
        # Queue is full - log warning but don't block
        _logger.warning("Audit log queue is full, dropping log entry. Consider increasing queue size.")
    except Exception as e:
        _logger.error(f"Error adding log entry to queue: {e}")


def log_user_action(action, entity_type, entity_id=None, **details):
    """
    Convenience function for logging end-user actions.
    
    Usage:
        log_user_action('song_requested', 'request', request_id, 
                       song_id=123, song_title='Hotel California')
    """
    log_event(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details if details else None,
        user_type='end_user',
        user_name=session.get('user_name') if has_request_context() else None,
        user_session_id=session.get('user_session_id') if has_request_context() else None
    )


def log_tenant_admin_action(action, entity_type, entity_id=None, **details):
    """
    Convenience function for logging tenant admin actions.
    
    Usage:
        log_tenant_admin_action('song_added', 'song', song_id,
                               song_title='Bohemian Rhapsody', method='manual')
    """
    tenant_id = None
    if has_request_context() and session:
        tenant_id = session.get('tenant_id')
        user_id = session.get('tenant_id')  # Using tenant_id as user_id for tenant admins
    
    log_event(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details if details else None,
        user_type='tenant_admin',
        user_id=tenant_id if has_request_context() and session else None,
        tenant_id=tenant_id
    )


def log_superadmin_action(action, entity_type, entity_id=None, **details):
    """
    Convenience function for logging superadmin actions.
    
    Usage:
        log_superadmin_action('tenant_created', 'tenant', tenant_id,
                             tenant_slug='john-doe')
    """
    user_id = None
    if has_request_context() and session:
        user_id = session.get('superadmin_id')
    
    log_event(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details if details else None,
        user_type='superadmin',
        user_id=user_id
    )


# Initialize on import
_start_log_worker()
