from django.contrib.sessions.models import Session
from datetime import datetime
from django.utils.timezone import now
from django.contrib.auth import logout
from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from django.urls import reverse
from django.utils import timezone




class OneSessionPerUser:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current_session_key = request.user.logged_in_user.session_key

            if current_session_key and current_session_key != request.session.session_key:
                Session.objects.filter(session_key=current_session_key).delete()

            request.user.logged_in_user.session_key = request.session.session_key
            request.user.logged_in_user.save()

        response = self.get_response(request)
        return response
    
    
class InactivityLogoutMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            last_activity = request.session.get('last_activity')
            pending_logout = request.session.get('pending_logout', False)

            if last_activity:
                last_activity = datetime.fromisoformat(last_activity)
                elapsed_time = (timezone.now() - last_activity).total_seconds()

                if elapsed_time > settings.INACTIVITY_TIMEOUT:
                    request.session['pending_logout'] = True
                else:
                    request.session['pending_logout'] = False

            request.session['last_activity'] = timezone.now().isoformat()

