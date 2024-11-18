import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.core.cache import cache
import json
from ..models import Match
from django.contrib.auth import get_user_model
import random

User = get_user_model()

class GameAIConsumer(AsyncWebsocketConsumer):

    ACCELERATION_FACTOR = 1.05

    PADDLE_SPEED = 8

    BALL_SPEED = 6

    HEIGHT = 400
    WIDTH = 600

    DISTANCE_BETWEEN_WALL_PADDLE = 30

    BALL_X = 295
    BALL_Y = 195

    BALL_HEIGHT = 5
    BALL_WIDTH = 5

    PADDLE_HEIGHT = 80
    PADDLE_WIDTH = 10

    PADDLE_MAX_HEIGHT = 400 - PADDLE_HEIGHT
    PADDLE_MIN_HEIGHT = 0

    async def connect(self):
        self.game_id = self.scope['url_route']['kwargs']['id']
        self.user = self.scope['user']
        self.room_group_name = f"game_{self.game_id}_ai"

        disconnect_key = f"player_disconnected_{self.game_id}"
        was_disconnected = cache.get(disconnect_key) == self.user.username

        if not cache.get(f"game_{self.game_id}_ai_state"):
            cache.set(f"game_{self.game_id}_ai_state", {
                'player1PaddleY': self.HEIGHT / 2 - self.PADDLE_HEIGHT / 2,
                'player2PaddleY': self.HEIGHT / 2 - self.PADDLE_HEIGHT / 2,
                'ball_x': self.BALL_X,
                'ball_y': self.BALL_Y,
                'ball_dx': self.BALL_SPEED if random.choice([True, False]) else -self.BALL_SPEED,
                'ball_dy': self.BALL_SPEED if random.choice([True, False]) else -self.BALL_SPEED,
                'paused': False,
            })

        cache.delete(disconnect_key)

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        if was_disconnected:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "send_info",
                    "message": f"Player {self.user.username} has reconnected."
                }
            )

            # Resume the game
            game_state = cache.get(f"game_{self.game_id}_ai_state")
            if game_state:
                game_state['paused'] = False
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "player_movement",
                        "player": self.user.username,
                        "player1PaddleY": game_state['player1PaddleY'],
                        "player2PaddleY": game_state['player2PaddleY'],
                    }
                )
                cache.set(f"game_{self.game_id}_ai_state", game_state)

        try:
            self.match = await sync_to_async(Match.objects.get)(id=self.game_id)
        
            self.player1 = await sync_to_async(lambda: self.match.user1 if self.match.user1 else "Player1")()
            self.player2 = await sync_to_async(lambda: self.match.user2 if self.match.user2 else "Player2")()
            
            await self.accept()

        except Match.DoesNotExist:
            await self.close()

        game_process_key = f"game_{self.game_id}_process_started"
        if not cache.get(game_process_key):
            cache.set(game_process_key, True)
            asyncio.create_task(self.AIProcess())
            asyncio.create_task(self.gameProcess())
        else:
            await self.send_score_update()

    async def AIProcess(self):
        while await self.check_win() == 0:
            game_state = cache.get(f"game_{self.game_id}_ai_state")
            
            if not game_state:
                print(f"No game state found for game {self.game_id}")
                continue

            ball_x = game_state['ball_x']
            ball_y = game_state['ball_y']
            ball_dx = game_state['ball_dx']
            ball_dy = game_state['ball_dy']
            paddle2_y = game_state['player2PaddleY']
            paddle2_x = self.WIDTH - 30 - self.PADDLE_WIDTH  # Fixed x-position for paddle2 from CSS
            paddle1_x = 30 + self.PADDLE_WIDTH  # Fixed x-position for paddle1 from CSS

            #! take start time to know when it can refresh (after 1 sec)
            start_time = asyncio.get_event_loop().time()

            #* emulate ball trajectory until it is reachable by the AI
            while (ball_x < paddle2_x):
                # Update ball position
                ball_x += ball_dx
                ball_y += ball_dy

                # Handle collision with top and bottom walls
                if ball_y <= 0 or ball_y >= self.HEIGHT - self.BALL_HEIGHT:
                    ball_dy *= -1

                #* assume ennemy player is perfectly placed (otherwhise game is won anyways)
                #! Handle collision with ennemy paddle
                if ball_x <= paddle1_x:
                    ball_dx = -ball_dx * self.ACCELERATION_FACTOR
                    ball_dy *= self.ACCELERATION_FACTOR

            move_distance = self.PADDLE_SPEED

            direction = None
            while not game_state.get('paused') and await self.check_win() == 0 and asyncio.get_event_loop().time() - start_time < 1:
                game_state = cache.get(f"game_{self.game_id}_ai_state")
                if game_state.get('paused'):
                    await asyncio.sleep(0.1)
                    continue
                paddle2_y = game_state['player2PaddleY']
                #* Decide direction of action
                if ball_y > paddle2_y and ball_y < paddle2_y + self.PADDLE_HEIGHT:
                    direction = None 
                elif ball_y < paddle2_y + self.PADDLE_HEIGHT / 2:
                    direction = "up"
                else:
                    direction = "down"
                if (direction ):
                    game_state['player2PaddleY'] += move_distance if direction == "down" else -move_distance
                    game_state['player2PaddleY'] = max (min(game_state['player2PaddleY'], self.HEIGHT - self.PADDLE_HEIGHT), 0)
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "player_movement",
                            "player": "AI",
                            "player1PaddleY": game_state['player1PaddleY'],
                            "player2PaddleY": game_state['player2PaddleY'],
                        }
                    )
                cache.set(f"game_{self.game_id}_ai_state", game_state)
                await asyncio.sleep(0.02) #? 20 ms like player

    async def countdown(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "send_countdown",
                "message": "First at 5 win the game"
            }
        )
        await asyncio.sleep(1)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "send_countdown",
                "message": "Party start in 3"
            }
        )
        await asyncio.sleep(1)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "send_countdown",
                "message": "Party start in 2"
            }
        )
        await asyncio.sleep(1)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "send_countdown",
                "message": "Party start in 1"
            }
        )
        await asyncio.sleep(1)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "send_countdown",
                "message": "GO"
            }
        )
        await asyncio.sleep(0.4)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "send_countdown",
                "message": ""
            }
        )

    async def gameProcess(self):
        await self.countdown()
        while True:
            game_state = cache.get(f"game_{self.game_id}_ai_state")
            if not game_state:
                break

            if game_state.get('paused'):
                await asyncio.sleep(0.1)
                continue

            ball_x = game_state['ball_x']
            ball_y = game_state['ball_y']
            ball_dx = game_state['ball_dx']
            ball_dy = game_state['ball_dy']

            # Update ball position
            ball_x += ball_dx
            ball_y += ball_dy

            # Handle collision with top and bottom walls
            if ball_y <= 0 or ball_y >= self.HEIGHT - self.BALL_HEIGHT:
                ball_dy *= -1

            # Get paddle positions
            paddle1_x = 30  # Fixed x-position for paddle1 from CSS
            paddle2_x = self.WIDTH - 30 - self.PADDLE_WIDTH  # Fixed x-position for paddle2 from CSS
            paddle1_y = game_state['player1PaddleY']
            paddle2_y = game_state['player2PaddleY']


            #! Handle collision with paddles
            if ball_dx < 0:
                # Ball moving left towards Player 1's paddle
                if ball_x <= paddle1_x + self.PADDLE_WIDTH:
                    # Collision detected with Player 1's paddle
                    if paddle1_y <= ball_y + self.BALL_HEIGHT and ball_y <= paddle1_y + self.PADDLE_HEIGHT and ball_x >= self.DISTANCE_BETWEEN_WALL_PADDLE - 10:
                        ball_dx *= -self.ACCELERATION_FACTOR
                        ball_dy *= self.ACCELERATION_FACTOR + random.uniform(-0.1, 0.1)
            elif ball_dx > 0:
                # Ball moving right towards Player 2's paddle
                if ball_x + self.BALL_WIDTH >= paddle2_x:
                    # Collision detected with Player 2's paddle
                    if paddle2_y <= ball_y + self.BALL_HEIGHT and ball_y <= paddle2_y + self.PADDLE_HEIGHT and ball_x <= self.WIDTH - self.DISTANCE_BETWEEN_WALL_PADDLE + 10:
                        ball_dx *= -self.ACCELERATION_FACTOR
                        ball_dy *= self.ACCELERATION_FACTOR + random.uniform(-0.1, 0.1)

            #! Handle goal
            if ball_x <= 0:
                await self.add_point_to(2)

                await self.send_score_update()

                winner = await self.check_win()
                if winner:
                    await self.set_win_to(winner)
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "redirect_remaining_player",
                        }
                    )
                    break
                ball_x = self.BALL_X
                ball_y = self.BALL_Y

                ball_dx = -self.BALL_SPEED
                ball_dy = self.BALL_SPEED if random.choice([True, False]) else -self.BALL_SPEED

            elif ball_x + self.BALL_WIDTH >= self.WIDTH:
                await self.add_point_to(1)

                await self.send_score_update()

                winner = await self.check_win()
                if winner:
                    await self.set_win_to(winner)
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "redirect_remaining_player",
                        }
                    )
                    break
                ball_x = self.BALL_X
                ball_y = self.BALL_Y

                ball_dx = self.BALL_SPEED
                ball_dy = self.BALL_SPEED if random.choice([True, False]) else -self.BALL_SPEED

            # Update game state
            game_state['ball_x'] = ball_x
            game_state['ball_y'] = ball_y
            game_state['ball_dx'] = ball_dx
            game_state['ball_dy'] = ball_dy

            cache.set(f"game_{self.game_id}_ai_state", game_state)

            # Send updated ball position to clients
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'update_ball_position',
                    'ball_x': ball_x,
                    'ball_y': ball_y,
                }
            )

            await asyncio.sleep(0.02)

    async def update_ball_position(self, event):
        await self.send(text_data=json.dumps({
            'type': 'update_ball_position',
            'ball_x': event['ball_x'],
            'ball_y': event['ball_y'],
        }))

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data["type"] == "movement" and data["direction"] in ('up', 'down'):
            direction = data["direction"]

            game_state = cache.get(f"game_{self.game_id}_ai_state")

            now = asyncio.get_event_loop().time()
            last_move_time = game_state.get(f'last_move_time_{self.user.username}', 0)
            time_since_last_move = now - last_move_time

            min_time_between_moves = 0.01  # 20 ms like in js

            if time_since_last_move >= min_time_between_moves:
                move_distance = self.PADDLE_SPEED

                game_state['player1PaddleY'] += move_distance if direction == "down" else -move_distance
                game_state['player1PaddleY'] = max(self.PADDLE_MIN_HEIGHT, min(self.PADDLE_MAX_HEIGHT, game_state['player1PaddleY']))

                game_state[f'last_move_time_{self.user.username}'] = now

                cache.set(f"game_{self.game_id}_ai_state", game_state)

                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "player_movement",
                        "player": self.user.username,
                        "player1PaddleY": game_state['player1PaddleY'],
                        "player2PaddleY": game_state['player2PaddleY'],
                    }
                )
            else:
                pass

    async def player_movement(self, event):
        # Send the movement data to client
        await self.send(text_data=json.dumps({
            "type": "player_movement",
            "player": event["player"],
            "player1PaddleY": event["player1PaddleY"],
            "player2PaddleY": event["player2PaddleY"],
        }))

    async def disconnect(self, close_code):
        points_awarded_key = f"points_awarded_{self.game_id}"
        points_awarded = cache.get(points_awarded_key)

        if not points_awarded and hasattr(self, 'match'):
            disconnect_key = f"player_disconnected_{self.game_id}"
            cache.set(disconnect_key, self.user.username, timeout=20)

            # Set the game to paused
            game_state = cache.get(f"game_{self.game_id}_ai_state")
            if game_state:
                game_state['paused'] = True
                cache.set(f"game_{self.game_id}_ai_state", game_state)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "send_info",
                    "message": f"Player {self.user.username} has disconnected. He have 15 seconds to reconnect."
                }
            )

            asyncio.create_task(self.wait_for_reconnection(disconnect_key, points_awarded_key))

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def wait_for_reconnection(self, disconnect_key, points_awarded_key):
        await asyncio.sleep(15)

        #? Protection if the match is finish
        if await self.check_win() == 0:
            if cache.get(disconnect_key) == self.user.username:
                if self.match.user1 == self.user:
                    await self.set_points_to(2, 5)
                    await self.set_win_to(2)
                elif self.match.user2 == self.user:
                    await self.set_points_to(1, 5)
                    await self.set_win_to(1)

                cache.set(points_awarded_key, True, timeout=None)

                await self.channel_layer.group_send(
                    self.room_group_name,
                        {
                            "type": "redirect_remaining_player",
                        }
                )

    @sync_to_async
    def add_point_to(self, player):
        if player == 1:
            self.match.user1_score += 1
        elif player == 2:
            self.match.user2_score += 1
        self.match.save()

    @sync_to_async
    def set_points_to(self, player, points):
        if player == 1: 
            self.match.user1_score = points
        elif player == 2: 
            self.match.user2_score = points
        self.match.save()

    @sync_to_async
    def check_win(self):
        if self.match.user1_score >= 5:
            return 1
        elif self.match.user2_score >= 5:
            return 2
        return 0

    @sync_to_async
    def set_win_to(self, player):
        if player == 1:
            self.match.user1.elo += 50
            self.match.user2.elo -= 25
            if self.match.user2.elo < 0: self.match.user2.elo = 0
        elif player == 2:
            self.match.user2.elo += 50
            self.match.user1.elo -= 25
            if self.match.user1.elo < 0: self.match.user1.elo = 0
        self.match.user1.save()
        self.match.user2.save()

    async def redirect_remaining_player(self, event):
        await self.send(text_data=json.dumps({
            "type": "redirect"
        }))

    async def send_info(self, event):
        await self.send(text_data=json.dumps({
            "type": "info",
            "info": event["message"]
        }))

    async def send_countdown(self, event):
        await self.send(text_data=json.dumps({
            "type": "countdown",
            "message": event["message"]
        }))

    async def send_score_update(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "update_score",
                "player1_score": self.match.user1_score,
                "player2_score": self.match.user2_score,
            }
        )

    async def update_score(self, event):
        await self.send(text_data=json.dumps({
            "type": "update_score",
            "player1_score": event["player1_score"],
            "player2_score": event["player2_score"],
        }))