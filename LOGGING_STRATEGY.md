# 📊 Logging Strategy for Setly/Musium

## Overview
This document outlines a comprehensive logging strategy to track user and tenant activities, enable debugging, and generate valuable statistics.

## Logging Architecture

### Two-Tier Logging System

1. **Application Logs (app.log)** - Technical/debugging logs
   - Errors, warnings, debug messages
   - System events, API calls
   - Performance metrics
   - File-based logging

2. **Audit Logs (audit_logs table)** - Business/activity logs
   - User actions
   - Tenant activities
   - Data changes
   - Statistics-ready structured data
   - Database-stored for querying

---

## Events to Log

### 🎯 User Activity (End Users/Requesters)

#### Session Events
- **`user_session_start`** - When user scans QR and starts session
  - `user_session_id`, `tenant_id`, `user_name`, `ip_address`, `user_agent`, `referrer`
  - **Stats**: Active users per tenant, session duration, peak usage times

- **`user_session_end`** - When user logs out or session expires
  - `user_session_id`, `tenant_id`, `user_name`, `session_duration_seconds`
  - **Stats**: Average session length, bounce rate

#### Search & Discovery
- **`search_performed`** - User searches for songs
  - `tenant_id`, `user_session_id`, `user_name`, `search_query`, `language`, `results_count`, `duration_ms`
  - **Stats**: Most searched songs/authors, search patterns, language preferences

- **`search_results_viewed`** - User views search results
  - `tenant_id`, `user_session_id`, `results_count`, `filters_applied`
  - **Stats**: Search effectiveness, filter usage

#### Song Requests
- **`song_requested`** - User requests a song
  - `tenant_id`, `user_session_id`, `user_name`, `song_id`, `song_title`, `song_author`, `request_position_in_queue`
  - **Stats**: Most requested songs, request patterns, peak request times

- **`song_request_failed`** - Request failed (limit reached, error, etc.)
  - `tenant_id`, `user_session_id`, `user_name`, `song_id`, `failure_reason` (max_requests, error, etc.)
  - **Stats**: Request failure rate, common failure reasons

- **`song_request_cancelled`** - User cancels their own request
  - `tenant_id`, `user_session_id`, `user_name`, `request_id`, `song_id`
  - **Stats**: Cancellation rate, user behavior

#### Page Views
- **`page_view`** - User views a page
  - `tenant_id`, `user_session_id`, `page_path`, `page_title`, `referrer`
  - **Stats**: Page popularity, navigation paths, bounce rates

- **`qr_code_scanned`** - User scans QR code
  - `tenant_id`, `user_session_id`, `qr_code_type` (print_qr, scan_qr), `referrer`
  - **Stats**: QR code effectiveness, entry points

---

### 👨‍💼 Tenant Admin Activity

#### Authentication
- **`tenant_login`** - Tenant admin logs in
  - `tenant_id`, `tenant_slug`, `login_method` (password, token), `ip_address`, `user_agent`, `success`
  - **Stats**: Login frequency, failed login attempts, security monitoring

- **`tenant_login_failed`** - Failed login attempt
  - `tenant_id` (if known), `tenant_slug`, `email_attempted`, `ip_address`, `failure_reason`
  - **Stats**: Security patterns, brute force detection

- **`tenant_logout`** - Tenant admin logs out
  - `tenant_id`, `session_duration_seconds`

#### Password Management
- **`password_reset_requested`** - Password reset requested
  - `tenant_id`, `email`, `ip_address`
  
- **`password_reset_completed`** - Password successfully reset
  - `tenant_id`, `ip_address`

- **`password_changed`** - Password changed via admin panel
  - `tenant_id`, `ip_address`

#### Song Management
- **`song_added`** - New song added
  - `tenant_id`, `song_id`, `song_title`, `song_author`, `method` (manual, csv_upload, spotify)
  - **Stats**: Songs added per tenant, popular authors, growth rate

- **`song_updated`** - Song details updated
  - `tenant_id`, `song_id`, `changes` (JSON: `{title: old→new, author: old→new, etc.}`)
  - **Stats**: Update frequency, what gets updated most

- **`song_deleted`** - Song removed
  - `tenant_id`, `song_id`, `song_title`, `song_author`, `total_requests_removed`
  - **Stats**: Deletion patterns, cleanup behavior

- **`bulk_songs_uploaded`** - CSV upload
  - `tenant_id`, `songs_count`, `success_count`, `failed_count`, `file_size_bytes`, `duration_ms`
  - **Stats**: Upload frequency, success rate, file sizes

- **`songs_deleted_bulk`** - Bulk deletion (all songs, duplicates, etc.)
  - `tenant_id`, `songs_deleted_count`, `method` (delete_all, remove_duplicates)

#### Request Management (Admin)
- **`request_marked_fulfilled`** - Admin marks request as played
  - `tenant_id`, `request_id`, `song_id`, `song_title`, `requester`, `queue_position`, `time_in_queue_seconds`
  - **Stats**: Average fulfillment time, queue throughput, most played songs

- **`request_deleted`** - Admin removes request from queue
  - `tenant_id`, `request_id`, `song_id`, `requester`, `reason` (if available)
  - **Stats**: Deletion rate, moderation patterns

- **`queue_cleared`** - Entire queue cleared
  - `tenant_id`, `requests_cleared_count`

#### Settings & Configuration
- **`tenant_settings_updated`** - Tenant settings changed
  - `tenant_id`, `setting_key`, `old_value`, `new_value`
  - **Stats**: Most changed settings, configuration patterns

- **`tenant_logo_updated`** - Logo changed
  - `tenant_id`, `image_size_bytes`, `image_format`

- **`tenant_banner_updated`** - Banner image changed
  - `tenant_id`, `image_size_bytes`, `image_format`

- **`tenant_profile_updated`** - Profile info changed (bio, website, events link)
  - `tenant_id`, `fields_changed` (JSON array)

- **`max_requests_setting_updated`** - Max requests per user changed
  - `tenant_id`, `old_value`, `new_value`
  - **Stats**: Configuration patterns

- **`language_preference_updated`** - Tenant language changed
  - `tenant_id`, `old_language`, `new_language`

#### Spotify Integration
- **`spotify_fetch_initiated`** - Bulk fetch started
  - `tenant_id`, `job_id`, `songs_to_process_count`, `fetch_type` (images, genres, languages, all)
  
- **`spotify_fetch_completed`** - Bulk fetch finished
  - `tenant_id`, `job_id`, `success_count`, `failed_count`, `duration_seconds`, `rate_limits_hit`

- **`spotify_image_downloaded`** - Individual image downloaded
  - `tenant_id`, `song_id`, `artist_name`, `image_url`, `image_size_bytes`, `success`

- **`spotify_api_error`** - Spotify API error
  - `tenant_id`, `artist_name`, `error_type`, `error_message`

#### Wizard & Onboarding
- **`wizard_started`** - Setup wizard started
  - `tenant_id`, `step`

- **`wizard_step_completed`** - Wizard step completed
  - `tenant_id`, `step_number`, `step_name`, `data_collected` (summary)

- **`wizard_completed`** - Full wizard finished
  - `tenant_id`, `total_duration_seconds`, `steps_completed`

#### Analytics & Insights
- **`insights_viewed`** - Tenant views insights page
  - `tenant_id`, `date_range`, `sections_viewed`

- **`csv_exported`** - Tenant downloads CSV
  - `tenant_id`, `songs_count`, `file_size_bytes`

- **`pdf_generated`** - PDF repertorio generated
  - `tenant_id`, `songs_count`, `file_size_bytes`, `duration_ms`, `includes_qr_code`

#### Sample Data
- **`sample_songs_added`** - Sample songs populated
  - `tenant_id`, `songs_count`

- **`sample_songs_deleted`** - Sample songs removed
  - `tenant_id`, `songs_deleted_count`

---

### 🔧 Superadmin Activity

#### Tenant Management
- **`tenant_created`** - New tenant created
  - `tenant_id`, `tenant_slug`, `tenant_name`, `tenant_email`, `created_by_superadmin_id`, `invitation_sent`
  - **Stats**: Tenant growth, onboarding success

- **`tenant_updated`** - Tenant details modified
  - `tenant_id`, `changes` (JSON), `updated_by_superadmin_id`
  
- **`tenant_deactivated`** - Tenant disabled
  - `tenant_id`, `reason` (optional), `deactivated_by_superadmin_id`

- **`tenant_activated`** - Tenant re-enabled
  - `tenant_id`, `activated_by_superadmin_id`

- **`tenant_deleted`** - Tenant removed
  - `tenant_id`, `tenant_slug`, `deleted_by_superadmin_id`, `data_retention_info`

#### System Operations
- **`superadmin_login`** - Superadmin logs in
  - `superadmin_id`, `ip_address`, `user_agent`

- **`superadmin_logout`** - Superadmin logs out
  - `superadmin_id`, `session_duration_seconds`

- **`database_backup_created`** - Backup generated
  - `backup_filename`, `backup_size_bytes`, `created_by_superadmin_id`

- **`system_setting_updated`** - System-wide setting changed
  - `setting_key`, `old_value`, `new_value`, `updated_by_superadmin_id`

---

### 🎤 Tenant Signup & Referral

- **`signup_initiated`** - User starts signup process
  - `referral_code` (if any), `referrer_tenant_id`, `email`, `ip_address`

- **`signup_completed`** - New tenant account created
  - `tenant_id`, `tenant_slug`, `email`, `referral_code`, `referred_by_tenant_id`
  - **Stats**: Signup conversion rate, referral effectiveness

- **`invitation_sent`** - Tenant invitation email sent
  - `tenant_id`, `tenant_email`, `invitation_token`, `expires_at`, `language`
  - **Stats**: Invitation success rate

- **`invitation_accepted`** - Tenant accepts invitation and sets password
  - `tenant_id`, `invitation_token`, `time_since_sent_hours`

---

## Log Structure

### Audit Logs Table Schema (Enhanced)

```sql
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Event Classification
    action TEXT NOT NULL,              -- e.g., 'song_requested', 'tenant_login'
    entity_type TEXT NOT NULL,         -- e.g., 'song', 'request', 'tenant', 'user_session'
    entity_id INTEGER,                 -- ID of the entity (song_id, request_id, etc.)
    
    -- Context
    tenant_id INTEGER,                 -- Always include tenant_id when applicable
    user_id INTEGER,                   -- For tenant admins/superadmins
    user_type TEXT,                    -- 'end_user', 'tenant_admin', 'superadmin'
    user_name TEXT,                    -- End user name (from session)
    user_session_id TEXT,              -- User session identifier
    
    -- Additional Data
    details TEXT,                      -- JSON string with event-specific data
    ip_address TEXT,                   -- Client IP
    user_agent TEXT,                   -- Browser/device info
    referrer TEXT,                     -- HTTP referrer
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for performance
    FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);

-- Indexes for common queries
CREATE INDEX idx_audit_tenant_action ON audit_logs(tenant_id, action);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at);
CREATE INDEX idx_audit_user_session ON audit_logs(user_session_id);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
```

### Details JSON Schema Examples

**Song Requested:**
```json
{
  "song_id": 123,
  "song_title": "Hotel California",
  "song_author": "Eagles",
  "request_position_in_queue": 5,
  "user_current_requests_count": 2,
  "max_requests_allowed": 3
}
```

**Song Added:**
```json
{
  "song_id": 456,
  "song_title": "Bohemian Rhapsody",
  "song_author": "Queen",
  "method": "csv_upload",
  "batch_id": "csv_20250115_143022"
}
```

**Tenant Settings Updated:**
```json
{
  "setting_key": "max_requests",
  "old_value": 3,
  "new_value": 5,
  "updated_fields": ["max_requests"]
}
```

---

## Statistics & Analytics

### Key Metrics to Track

#### Per-Tenant Metrics
- **Request Statistics**
  - Total requests, requests per day/week/month
  - Average requests per user
  - Peak request times (hour of day, day of week)
  - Most requested songs/authors
  - Request fulfillment rate and time

- **User Engagement**
  - Active users per day/week/month
  - Average session duration
  - Pages per session
  - Bounce rate
  - Return user rate

- **Content Statistics**
  - Total songs, growth rate
  - Songs added/updated/deleted frequency
  - CSV upload frequency and success rate
  - Spotify integration usage

- **Admin Activity**
  - Login frequency
  - Settings changed
  - Queue management actions

#### Platform-Wide Metrics
- **Tenant Growth**
  - New tenants per month
  - Active tenants (logged in within last 30 days)
  - Tenant retention rate
  - Referral effectiveness

- **System Usage**
  - Total requests across all tenants
  - Peak usage times
  - API usage (Spotify)
  - Error rates

- **Feature Adoption**
  - QR code usage
  - PDF generation usage
  - CSV upload usage
  - Spotify bulk fetch usage

---

## Implementation Recommendations

### 1. Logging Utility Module (✅ IMPLEMENTATO)

Il modulo `utils/audit_logger.py` è già stato creato e implementa:

#### 🔄 **Sistema Asincrono**
- **Coda thread-safe**: I log vengono inseriti in una coda (`queue.Queue`) invece di essere scritti direttamente nel database
- **Worker thread in background**: Un thread dedicato processa la coda e scrive nel database in batch
- **Non-blocking**: Le funzioni di logging ritornano immediatamente, senza bloccare le richieste HTTP
- **Batch processing**: I log vengono scritti in batch (50 alla volta) per migliorare le performance
- **Auto-flush**: I batch vengono flushati ogni 2 secondi anche se non pieni, per garantire che i log non si perdano

#### Funzioni Disponibili:

```python
from utils.audit_logger import (
    log_event,              # Funzione generica
    log_user_action,        # Per azioni utenti finali
    log_tenant_admin_action, # Per azioni tenant admin
    log_superadmin_action    # Per azioni superadmin
)
```

#### Caratteristiche:
- ✅ **Asincrono**: Non blocca mai le richieste HTTP
- ✅ **Auto-configurazione**: Crea automaticamente la tabella e gli indici se non esistono
- ✅ **Gestione errori**: Se la coda è piena o ci sono errori, non interrompe l'applicazione
- ✅ **Context-aware**: Estrae automaticamente tenant_id, user_session_id, IP, user agent dalla sessione/request Flask
- ✅ **Thread-safe**: Sicuro da usare in ambiente multi-thread

### 2. Add Logging to Key Routes

Esempi di implementazione con il sistema asincrono:

**Song Request (Asincrono - non blocca):**
```python
@app.route('/request_song/<int:song_id>', methods=['POST'])
def request_song(song_id):
    # ... existing code ...
    
    if success:
        from utils.audit_logger import log_user_action
        
        # Get song info for logging
        song = get_song(song_id)
        queue_position = get_queue_position(tenant_id, song_id)
        
        # ✅ Non-blocking: questa chiamata ritorna immediatamente
        log_user_action(
            action='song_requested',
            entity_type='request',
            entity_id=request_id,
            song_id=song_id,
            song_title=song['title'],
            song_author=song['author'],
            request_position_in_queue=queue_position,
            user_current_requests_count=user_requests_count,
            max_requests_allowed=max_requests
        )
        # Il log viene scritto nel database in background
    
    return jsonify(...)
```

**Song Added (Asincrono):**
```python
@app.route('/<tenant_slug>/upload', methods=['POST'])
def tenant_upload(tenant_slug):
    # ... existing code ...
    
    from utils.audit_logger import log_tenant_admin_action
    
    # ✅ Non-blocking: ritorna subito, scrive in background
    log_tenant_admin_action(
        action='song_added',
        entity_type='song',
        entity_id=song_id,
        song_title=title,
        song_author=author,
        method='manual'  # or 'csv_upload'
    )
```

#### ⚡ Vantaggi del Sistema Asincrono:
- **Zero impatto sulle performance**: Le richieste HTTP non vengono rallentate
- **Scalabilità**: Gestisce migliaia di log al secondo senza problemi
- **Affidabilità**: Se il database è lento, i log si accumulano nella coda e vengono processati quando possibile
- **Batch writing**: Scrive 50 log alla volta, riducendo il numero di operazioni sul database

### 3. Log File Configuration

Enhance existing logging configuration:

```python
import logging
from logging.handlers import RotatingFileHandler

# Configure file logging with rotation
log_filename = os.path.join(os.path.dirname(__file__), 'app.log')
handler = RotatingFileHandler(
    log_filename, 
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
handler.setFormatter(formatter)
app.logger.addHandler(handler)
```

### 4. Privacy Considerations

- **PII in Logs**: Only log necessary identifiers (user_name is okay, but avoid logging full email addresses in details)
- **Data Retention**: Consider archiving/cleaning old audit logs (e.g., keep last 2 years)
- **GDPR Compliance**: If needed, allow tenants to export/delete their audit logs

---

## Query Examples for Statistics

### Most Requested Songs (per tenant)
```sql
SELECT 
    entity_id as song_id,
    COUNT(*) as request_count,
    JSON_EXTRACT(details, '$.song_title') as song_title
FROM audit_logs
WHERE action = 'song_requested' 
  AND tenant_id = ?
  AND created_at >= datetime('now', '-30 days')
GROUP BY entity_id
ORDER BY request_count DESC
LIMIT 10;
```

### Daily Active Users
```sql
SELECT 
    DATE(created_at) as date,
    COUNT(DISTINCT user_session_id) as active_users
FROM audit_logs
WHERE tenant_id = ?
  AND action IN ('user_session_start', 'song_requested', 'search_performed')
  AND created_at >= datetime('now', '-30 days')
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

### Tenant Admin Activity
```sql
SELECT 
    action,
    COUNT(*) as count,
    DATE(created_at) as date
FROM audit_logs
WHERE tenant_id = ?
  AND user_type = 'tenant_admin'
  AND created_at >= datetime('now', '-7 days')
GROUP BY action, DATE(created_at)
ORDER BY date DESC, count DESC;
```

---

## Next Steps

1. ✅ Review and approve logging strategy
2. ⬜ Enhance `audit_logs` table schema (add indexes)
3. ⬜ Create `utils/audit_logger.py` utility module
4. ⬜ Add logging to high-priority routes (song requests, tenant actions)
5. ⬜ Create dashboard/queries for key statistics
6. ⬜ Test logging and verify data quality
7. ⬜ Document how to query logs for statistics

---

## Priority Implementation Order

### Phase 1: Critical Events (Week 1)
- Song requested/fulfilled
- Tenant login/logout
- Song added/updated/deleted
- User session start/end

### Phase 2: Important Events (Week 2)
- Search performed
- Settings updated
- CSV uploads
- Spotify integration

### Phase 3: Nice-to-Have (Week 3)
- Page views
- Wizard steps
- PDF generation
- Detailed error tracking

---

**Note**: Start with Phase 1 events as they provide the most value for debugging and statistics. You can expand logging incrementally as needed.
