"""ASGI config for portal project.

It exposes the ASGI callable as a module-level variable named ``application``.

This file is required for Django Channels / WebSocket support.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

import portal.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portal.settings')

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(portal.routing.websocket_urlpatterns)
    ),
})
