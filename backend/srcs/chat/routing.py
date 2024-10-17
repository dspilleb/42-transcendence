from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/global/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/chat/private/(?P<friendship_id>\d+)/$', consumers.PrivateChatConsumer.as_asgi()),
]