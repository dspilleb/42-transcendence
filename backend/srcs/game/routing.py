from django.urls import path

from . import waitingConsumers
from . import game1v1Consumer
from . import gameAIConsumers
from . import puissance4Consumers

websocket_urlpatterns = [
    path("ws/waiting/<str:game_mode>/<str:queue_type>/", waitingConsumers.WaitingConsumer.as_asgi()),
    path("ws/game/pong/1v1/<int:id>/", game1v1Consumer.Game1v1Consumer.as_asgi()),
    path("ws/game/pong/AI/<int:id>/", gameAIConsumers.GameAIConsumer.as_asgi()),
    # path("ws/game/pong/2v2/<int:id>/", gameConsumers.GameConsumer.as_asgi()),
    path("ws/game/puissance4/1v1/<int:id>/", puissance4Consumers.Puissance4Consumer.as_asgi()),
]
