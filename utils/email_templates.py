"""
Multilingual email templates for the Setly app
"""

EMAIL_TEMPLATES = {
    'en': {
        'subject': 'Welcome to Setly - Set Up Your Account!',
        'greeting': 'Welcome to Setly, {name}!',
        'intro': 'Your personalized music request platform has been created and is ready to use.',
        'cta_intro': 'To get started, please set up your password by clicking the button below:',
        'button_text': 'Set Up My Account',
        'expiry': 'This link will expire in 24 hours.',
        'account_details': 'Your Account Details:',
        'login_email': 'Login Email',
        'platform_url': 'Platform URL',
        'platform_url_note': "You'll receive this after setting your password",
        'getting_started': 'Getting Started:',
        'step1': 'Log in to your admin panel at the URL above',
        'step2': 'Upload your song library',
        'step3': 'Customize your welcome page with images and branding',
        'step4': 'Share your unique URL with your audience',
        'footer': 'If you have any questions or need assistance, please don\'t hesitate to reach out.',
        'signature': 'Best regards,<br>The Setly Team'
    },
    'it': {
        'subject': 'Benvenuto su Setly - Configura il Tuo Account!',
        'greeting': 'Benvenuto su Setly, {name}!',
        'intro': 'La tua piattaforma personalizzata per le richieste musicali è stata creata ed è pronta per l\'uso.',
        'cta_intro': 'Per iniziare, configura la tua password cliccando il pulsante qui sotto:',
        'button_text': 'Configura il Mio Account',
        'expiry': 'Questo link scadrà tra 24 ore.',
        'account_details': 'Dettagli del Tuo Account:',
        'login_email': 'Email di Accesso',
        'platform_url': 'URL della Piattaforma',
        'platform_url_note': 'Lo riceverai dopo aver impostato la password',
        'getting_started': 'Per Iniziare:',
        'step1': 'Accedi al tuo pannello di amministrazione all\'URL sopra',
        'step2': 'Carica la tua libreria musicale',
        'step3': 'Personalizza la tua pagina di benvenuto con immagini e branding',
        'step4': 'Condividi il tuo URL unico con il tuo pubblico',
        'footer': 'Se hai domande o hai bisogno di assistenza, non esitare a contattarci.',
        'signature': 'Cordiali saluti,<br>Il Team Setly'
    },
    'es': {
        'subject': 'Bienvenido a Setly - ¡Configura Tu Cuenta!',
        'greeting': '¡Bienvenido a Setly, {name}!',
        'intro': 'Tu plataforma personalizada de solicitudes musicales ha sido creada y está lista para usar.',
        'cta_intro': 'Para comenzar, configura tu contraseña haciendo clic en el botón a continuación:',
        'button_text': 'Configurar Mi Cuenta',
        'expiry': 'Este enlace caducará en 24 horas.',
        'account_details': 'Detalles de Tu Cuenta:',
        'login_email': 'Correo de Inicio de Sesión',
        'platform_url': 'URL de la Plataforma',
        'platform_url_note': 'Lo recibirás después de configurar tu contraseña',
        'getting_started': 'Para Comenzar:',
        'step1': 'Inicia sesión en tu panel de administración en la URL de arriba',
        'step2': 'Sube tu biblioteca musical',
        'step3': 'Personaliza tu página de bienvenida con imágenes y marca',
        'step4': 'Comparte tu URL única con tu audiencia',
        'footer': 'Si tienes alguna pregunta o necesitas ayuda, no dudes en contactarnos.',
        'signature': 'Saludos cordiales,<br>El Equipo Setly'
    },
    'de': {
        'subject': 'Willkommen bei Setly - Richten Sie Ihr Konto ein!',
        'greeting': 'Willkommen bei Setly, {name}!',
        'intro': 'Ihre personalisierte Musikwunsch-Plattform wurde erstellt und ist einsatzbereit.',
        'cta_intro': 'Um zu beginnen, richten Sie bitte Ihr Passwort ein, indem Sie auf die Schaltfläche unten klicken:',
        'button_text': 'Mein Konto Einrichten',
        'expiry': 'Dieser Link läuft in 24 Stunden ab.',
        'account_details': 'Ihre Kontodetails:',
        'login_email': 'Anmelde-E-Mail',
        'platform_url': 'Plattform-URL',
        'platform_url_note': 'Sie erhalten diese nach dem Festlegen Ihres Passworts',
        'getting_started': 'Erste Schritte:',
        'step1': 'Melden Sie sich unter der obigen URL in Ihrem Admin-Panel an',
        'step2': 'Laden Sie Ihre Musikbibliothek hoch',
        'step3': 'Passen Sie Ihre Willkommensseite mit Bildern und Branding an',
        'step4': 'Teilen Sie Ihre eindeutige URL mit Ihrem Publikum',
        'footer': 'Wenn Sie Fragen haben oder Unterstützung benötigen, zögern Sie bitte nicht, uns zu kontaktieren.',
        'signature': 'Mit freundlichen Grüßen,<br>Das Setly-Team'
    },
    'fr': {
        'subject': 'Bienvenue sur Setly - Configurez Votre Compte!',
        'greeting': 'Bienvenue sur Setly, {name}!',
        'intro': 'Votre plateforme personnalisée de demandes musicales a été créée et est prête à l\'emploi.',
        'cta_intro': 'Pour commencer, veuillez configurer votre mot de passe en cliquant sur le bouton ci-dessous:',
        'button_text': 'Configurer Mon Compte',
        'expiry': 'Ce lien expirera dans 24 heures.',
        'account_details': 'Détails de Votre Compte:',
        'login_email': 'Email de Connexion',
        'platform_url': 'URL de la Plateforme',
        'platform_url_note': 'Vous le recevrez après avoir configuré votre mot de passe',
        'getting_started': 'Pour Commencer:',
        'step1': 'Connectez-vous à votre panneau d\'administration à l\'URL ci-dessus',
        'step2': 'Téléchargez votre bibliothèque musicale',
        'step3': 'Personnalisez votre page d\'accueil avec des images et votre marque',
        'step4': 'Partagez votre URL unique avec votre public',
        'footer': 'Si vous avez des questions ou besoin d\'aide, n\'hésitez pas à nous contacter.',
        'signature': 'Cordialement,<br>L\'équipe Setly'
    }
}

def get_invitation_email(language, tenant_name, tenant_email, setup_url):
    """
    Generate invitation email in the specified language.
    
    Args:
        language (str): Language code ('en', 'it', 'es', 'de', 'fr')
        tenant_name (str): Name of the tenant
        tenant_email (str): Email of the tenant
        setup_url (str): URL for password setup
    
    Returns:
        tuple: (subject, html_body, text_body)
    """
    # Default to English if language not supported
    lang = language if language in EMAIL_TEMPLATES else 'en'
    t = EMAIL_TEMPLATES[lang]
    
    # HTML version
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #2c3e50;">{t['greeting'].format(name=tenant_name)}</h2>
        <p>{t['intro']}</p>
        
        <p>{t['cta_intro']}</p>
        
        <p style="margin: 30px 0;">
            <a href="{setup_url}" style="background-color: #27ae60; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">{t['button_text']}</a>
        </p>
        
        <p style="color: #7f8c8d; font-size: 14px;">{t['expiry']}</p>
        
        <h3>{t['account_details']}</h3>
        <ul>
            <li><strong>{t['login_email']}:</strong> {tenant_email}</li>
            <li><strong>{t['platform_url']}:</strong> {t['platform_url_note']}</li>
        </ul>
        
        <h3>{t['getting_started']}</h3>
        <ol>
            <li>{t['step1']}</li>
            <li>{t['step2']}</li>
            <li>{t['step3']}</li>
            <li>{t['step4']}</li>
        </ol>
        
        <p>{t['footer']}</p>
        
        <p>{t['signature']}</p>
    </body>
    </html>
    """
    
    # Plain text version
    # Fix: Can't use backslash in f-string expression, so prepare signature first
    signature_text = t['signature'].replace('<br>', '\n')
    
    text_body = f"""{t['greeting'].format(name=tenant_name)}

{t['intro']}

{t['cta_intro']}
{setup_url}

{t['expiry']}

{t['account_details']}
- {t['login_email']}: {tenant_email}
- {t['platform_url']}: {t['platform_url_note']}

{t['getting_started']}
1. {t['step1']}
2. {t['step2']}
3. {t['step3']}
4. {t['step4']}

{t['footer']}

{signature_text}
"""
    
    return (t['subject'], html_body, text_body)






