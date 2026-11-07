import os
from flask import Flask, render_template
from flask_login import current_user
from config import Config
from extensions import db, login_manager, socketio
from models import HospitalSetting, Notification

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)

    # Register Blueprints
    from routes import main_bp, auth_bp, patient_bp, staff_bp, admin_bp, api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    # Context Processor: Inject live database settings and notifications into every template
    @app.context_processor
    def inject_global_data():
        try:
            h_name = HospitalSetting.get_value('hospital_name', Config.HOSPITAL_NAME)
            a_name = HospitalSetting.get_value('app_name', Config.APP_NAME)
            adm_name = HospitalSetting.get_value('admin_display_name', Config.ADMIN_DISPLAY_NAME)
            phone = HospitalSetting.get_value('contact_phone', '+1 (555) 019-2834')
            email = HospitalSetting.get_value('contact_email', 'helpdesk@mediqueue.org')
            unread_count = 0
            if current_user.is_authenticated:
                unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        except Exception:
            h_name = Config.HOSPITAL_NAME
            a_name = Config.APP_NAME
            adm_name = Config.ADMIN_DISPLAY_NAME
            phone = "+1 (555) 019-2834"
            email = "helpdesk@mediqueue.org"
            unread_count = 0

        return dict(
            hospital_name=h_name,
            app_name=a_name,
            admin_display_name=adm_name,
            contact_phone=phone,
            contact_email=email,
            unread_notifications_count=unread_count
        )

    # Error Handlers
    @app.errorhandler(400)
    def bad_request_error(e):
        return render_template('errors/400.html', error=e), 400

    @app.errorhandler(403)
    def forbidden_error(e):
        return render_template('errors/403.html', error=e), 403

    @app.errorhandler(404)
    def not_found_error(e):
        return render_template('errors/404.html', error=e), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html', error=e), 500

    # SocketIO Event Listeners
    @socketio.on('connect')
    def handle_connect():
        pass

    @socketio.on('disconnect')
    def handle_disconnect():
        pass

    return app

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='127.0.0.1', port=5000, debug=True, allow_unsafe_werkzeug=True)
