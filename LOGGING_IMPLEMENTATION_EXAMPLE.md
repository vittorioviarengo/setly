# 📝 Esempio di Implementazione Logging Asincrono

Questo documento mostra esempi pratici di come integrare il logging asincrono negli endpoint esistenti.

## 🎯 Esempio 1: Song Request (Critico)

### Endpoint: `/request_song/<int:song_id>`

**Prima (senza logging):**
```python
@app.route('/request_song/<int:song_id>', methods=['POST'])
@limiter.limit("10 per minute")
def request_song(song_id):
    # ... codice esistente ...
    
    # Add the song to the queue
    cursor.execute(
        'INSERT INTO requests (song_id, requester, tenant_id, session_id, status, tip_amount) VALUES (?, ?, ?, ?, ?, ?)', 
        (song_id, user_name, tenant_id, user_session_id, 'pending', 0.0)
    )
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': _('Song request successful')}), 200
```

**Dopo (con logging asincrono):**
```python
@app.route('/request_song/<int:song_id>', methods=['POST'])
@limiter.limit("10 per minute")
def request_song(song_id):
    # ... codice esistente fino al commit ...
    
    # Get song info for logging (prima di chiudere la connessione)
    cursor.execute('SELECT title, author, requests FROM songs WHERE id = ? AND tenant_id = ?', (song_id, tenant_id))
    song_info = cursor.fetchone()
    
    # Get queue position
    cursor.execute('''
        SELECT COUNT(*) as position FROM requests 
        WHERE tenant_id = ? AND status = 'pending' 
        AND request_time <= (SELECT request_time FROM requests WHERE song_id = ? AND requester = ? AND tenant_id = ? ORDER BY request_time DESC LIMIT 1)
    ''', (tenant_id, song_id, user_name, tenant_id))
    queue_position_result = cursor.fetchone()
    queue_position = queue_position_result['position'] if queue_position_result else None
    
    # Get request_id (l'ultimo inserito)
    request_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    # ✅ LOGGING ASINCRONO - Non blocca la risposta HTTP
    from utils.audit_logger import log_user_action
    
    log_user_action(
        action='song_requested',
        entity_type='request',
        entity_id=request_id,
        song_id=song_id,
        song_title=song_info['title'] if song_info else None,
        song_author=song_info['author'] if song_info else None,
        request_position_in_queue=queue_position,
        user_current_requests_count=user_requests,
        max_requests_allowed=max_requests,
        total_song_requests=song_info['requests'] if song_info else None
    )
    
    return jsonify({'success': True, 'message': _('Song request successful')}), 200
```

### Gestione Errori (Logging dei Fallimenti)

```python
@app.route('/request_song/<int:song_id>', methods=['POST'])
@limiter.limit("10 per minute")
def request_song(song_id):
    from utils.audit_logger import log_user_action
    
    if not is_session_valid():
        return jsonify({'redirect': url_for('scan_qr')})
    
    try:
        # ... codice esistente ...
        
        if user_requests >= max_requests:
            # ✅ Log fallimento - limite raggiunto
            log_user_action(
                action='song_request_failed',
                entity_type='request',
                song_id=song_id,
                failure_reason='max_requests_reached',
                user_current_requests_count=user_requests,
                max_requests_allowed=max_requests
            )
            return jsonify({'error': _('Maximum Request Reached')}), 400
        
        # Check if already requested
        if user_requested_song['count'] > 0:
            # ✅ Log fallimento - già richiesta
            log_user_action(
                action='song_request_failed',
                entity_type='request',
                song_id=song_id,
                failure_reason='already_requested'
            )
            return jsonify({'error': _('Song Already Requested')}), 400
        
        # ... success case con logging come sopra ...
        
    except Exception as e:
        # ✅ Log errore generico
        log_user_action(
            action='song_request_failed',
            entity_type='request',
            song_id=song_id,
            failure_reason='error',
            error_message=str(e)
        )
        app.logger.error(f"Error incrementing request: {e}")
        return jsonify({'error': _('Song Request Error')}), 500
```

---

## 🎯 Esempio 2: Tenant Login

### Endpoint: `/<tenant_slug>/login`

```python
@app.route('/<tenant_slug>/login', methods=['GET', 'POST'])
@limiter.limit("5 per 15 minutes", methods=['POST'])
def tenant_login(tenant_slug):
    from utils.audit_logger import log_event
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tenants WHERE slug = ?', (tenant_slug,))
        tenant = cursor.fetchone()
        
        if tenant and check_password_hash(tenant['password'], password):
            # ✅ Log login riuscito
            log_event(
                action='tenant_login',
                entity_type='tenant',
                entity_id=tenant['id'],
                tenant_id=tenant['id'],
                user_type='tenant_admin',
                details={
                    'tenant_slug': tenant_slug,
                    'login_method': 'password',
                    'success': True
                }
            )
            
            # ... resto del codice login ...
            
        else:
            # ✅ Log tentativo fallito
            log_event(
                action='tenant_login_failed',
                entity_type='tenant',
                tenant_id=tenant['id'] if tenant else None,
                user_type='tenant_admin',
                details={
                    'tenant_slug': tenant_slug,
                    'email_attempted': email,
                    'failure_reason': 'invalid_credentials'
                }
            )
            flash('Invalid email or password')
        
        conn.close()
    
    return render_template('login.html', tenant=tenant)
```

---

## 🎯 Esempio 3: Song Added (Tenant Admin)

### Endpoint: `/<tenant_slug>/upload` o manual add

```python
@app.route('/<tenant_slug>/upload', methods=['POST'])
def tenant_upload(tenant_slug):
    from utils.audit_logger import log_tenant_admin_action
    
    # ... codice esistente per processare CSV ...
    
    for song in songs:
        # Insert song
        cursor.execute(
            'INSERT INTO songs (title, author, language, image, tenant_id) VALUES (?, ?, ?, ?, ?)',
            (song['title'], song['author'], song['language'], song.get('image', ''), tenant_id)
        )
        song_id = cursor.lastrowid
        
        # ✅ LOGGING ASINCRONO per ogni canzone aggiunta
        log_tenant_admin_action(
            action='song_added',
            entity_type='song',
            entity_id=song_id,
            song_title=song['title'],
            song_author=song['author'],
            language=song['language'],
            method='csv_upload',
            batch_id=batch_id  # ID del batch per raggruppare i log
        )
    
    conn.commit()
    conn.close()
    
    # ✅ Log riepilogativo del batch
    log_tenant_admin_action(
        action='bulk_songs_uploaded',
        entity_type='batch',
        details={
            'songs_count': len(songs),
            'success_count': success_count,
            'failed_count': failed_count,
            'file_size_bytes': file_size
        }
    )
    
    return jsonify({'success': True, 'message': f'{len(songs)} songs uploaded'})
```

---

## 🎯 Esempio 4: Request Marked as Fulfilled

### Endpoint: `/api/mark_request_fulfilled/<int:request_id>`

```python
@app.route('/api/mark_request_fulfilled/<int:request_id>', methods=['POST'])
def mark_request_fulfilled(request_id):
    from utils.audit_logger import log_tenant_admin_action
    
    tenant_id = session.get('tenant_id')
    
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get request and song info
    cursor.execute('''
        SELECT r.*, s.title, s.author, s.id as song_id
        FROM requests r
        JOIN songs s ON r.song_id = s.id
        WHERE r.id = ? AND r.tenant_id = ?
    ''', (request_id, tenant_id))
    
    request_data = cursor.fetchone()
    
    if not request_data:
        return jsonify({'error': 'Request not found'}), 404
    
    # Calculate time in queue
    request_time = datetime.fromisoformat(request_data['request_time'].replace('Z', '+00:00'))
    time_in_queue = (datetime.now(timezone.utc) - request_time).total_seconds()
    
    # Get queue position before marking as fulfilled
    cursor.execute('''
        SELECT COUNT(*) as position FROM requests
        WHERE tenant_id = ? AND status = 'pending' 
        AND request_time <= ?
    ''', (tenant_id, request_data['request_time']))
    queue_position = cursor.fetchone()['position']
    
    # Mark as fulfilled
    cursor.execute('''
        UPDATE requests 
        SET status = 'fulfilled', played_at = CURRENT_TIMESTAMP 
        WHERE id = ? AND tenant_id = ?
    ''', (request_id, tenant_id))
    
    conn.commit()
    conn.close()
    
    # ✅ LOGGING ASINCRONO
    log_tenant_admin_action(
        action='request_marked_fulfilled',
        entity_type='request',
        entity_id=request_id,
        song_id=request_data['song_id'],
        song_title=request_data['title'],
        song_author=request_data['author'],
        requester=request_data['requester'],
        queue_position=queue_position,
        time_in_queue_seconds=int(time_in_queue)
    )
    
    return jsonify({'success': True})
```

---

## 🎯 Esempio 5: User Session Start

### Endpoint: `/<tenant_slug>/`

```python
@app.route('/<tenant_slug>/')
def tenant_home(tenant_slug):
    from utils.audit_logger import log_event
    
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    conn.close()
    
    if not tenant:
        flash('Tenant not found or inactive')
        return redirect(url_for('index'))
    
    # Store tenant info in session
    session['tenant_slug'] = tenant_slug
    session['tenant_id'] = tenant['id']
    session['tenant_name'] = tenant['name']
    
    # Generate unique session_id
    if 'user_session_id' not in session:
        import secrets
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_suffix = secrets.token_hex(4)
        session['user_session_id'] = f"{tenant['id']}-{timestamp}-{random_suffix}"
        
        # ✅ LOG SESSION START (solo se nuova sessione)
        log_event(
            action='user_session_start',
            entity_type='session',
            tenant_id=tenant['id'],
            user_type='end_user',
            user_session_id=session['user_session_id'],
            details={
                'tenant_slug': tenant_slug,
                'entry_point': 'home'
            }
        )
    
    user_name = request.args.get('user', '')
    return render_template('index.html', user_name=user_name, tenant=tenant)
```

---

## 🎯 Esempio 6: Search Performed

### Endpoint: `/<tenant_slug>/search`

```python
@app.route('/<tenant_slug>/search', methods=['GET', 'POST'])
def tenant_search(tenant_slug):
    from utils.audit_logger import log_user_action
    import time
    
    start_time = time.time()
    
    # ... codice esistente ...
    
    search_query = request.args.get('s', '')
    language = request.form.get('lang', request.args.get('lang', session.get('language', 'en')))
    
    # Fetch songs
    songs = fetch_songs('all', search_query, language, tenant_id=tenant['id'], user_name=user_name)
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # ✅ LOG SEARCH (solo se c'è una query di ricerca)
    if search_query:
        log_user_action(
            action='search_performed',
            entity_type='search',
            search_query=search_query,
            language=language,
            results_count=len(songs),
            duration_ms=duration_ms
        )
    
    return render_template('search.html', user_name=user_name, language=language, songs=songs, ...)
```

---

## 📊 Vantaggi del Sistema Asincrono

### Performance
- ⚡ **Zero latenza**: Le richieste HTTP ritornano immediatamente
- 🚀 **Scalabile**: Gestisce migliaia di log al secondo
- 📦 **Batch writing**: Scrive 50 log alla volta (riduce operazioni DB)

### Affidabilità
- 🛡️ **Non blocca**: Se il DB è lento, i log si accumulano nella coda
- 🔄 **Auto-recovery**: Il worker thread continua a processare anche dopo errori
- 💾 **Buffer**: Coda di 10.000 log (può essere aumentata)

### Debugging
- 🔍 **Tracciamento completo**: Ogni azione importante viene loggata
- 📈 **Statistics-ready**: Dati strutturati pronti per query SQL
- 🕐 **Timestamps precisi**: Ogni log ha timestamp automatico

---

## 🚀 Prossimi Passi

1. ✅ Implementare logging nei endpoint critici (Phase 1)
2. ⬜ Aggiungere logging ai fallimenti (error cases)
3. ⬜ Creare dashboard per visualizzare statistiche
4. ⬜ Query SQL per report automatici
5. ⬜ Monitoring e alerting su eventi critici
