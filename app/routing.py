from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/project/(?P<project_id>\w+)/timeline/$', consumers.ProjectTimelineConsumer.as_asgi()),
]