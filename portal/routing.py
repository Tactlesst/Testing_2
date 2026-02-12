from django.urls import path

from frontend.lds.consumers import LdsTrainingNotificationsConsumer

websocket_urlpatterns = [
    path('ws/lds/notifications/', LdsTrainingNotificationsConsumer.as_asgi()),
]
