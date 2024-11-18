from channels.generic.websocket import AsyncWebsocketConsumer
import json
from django.utils import timezone
from asgiref.sync import sync_to_async
from django.db.models import Q
from srcs.community.models import Friend
from ..models import Match, Matchs, Tournament
from django.contrib.auth import get_user_model

User = get_user_model()

class WaitingConsumer(AsyncWebsocketConsumer):
    rooms = {}

    async def connect(self):
        websocket_url = self.scope['path']
        self.GAME = websocket_url.split('/')[-3]
        self.MODE = websocket_url.split('/')[-2]
        self.user = self.scope['user']
        # print(f'waiting_{self.GAME}_{self.MODE}') #* DEBUG

        if self.GAME == 'private':
            friend = await self.get_friendship()
            if friend is None:
                self.close()
                return
            self.LEN_NEEDED = 2
        elif self.MODE == '1v1':
            self.LEN_NEEDED = 2
        elif self.MODE == '2v2':
            self.LEN_NEEDED = 4
        elif self.MODE == 'AI':
            self.LEN_NEEDED = 1
        elif self.MODE == 'tournament':
            self.LEN_NEEDED = 4

        self.room_group_name = f'waiting_{self.GAME}_{self.MODE}'

        if self.user.is_authenticated:
            #? Create the room
            if self.room_group_name not in WaitingConsumer.rooms:
                WaitingConsumer.rooms[self.room_group_name] = set()

            #? Add user to the room
            WaitingConsumer.rooms[self.room_group_name].add(self.user.username)

            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            await self.accept()

            #? MAJ of the player list
            await self.send_player_list_to_all()

            # print(f"Number of connected players in {self.room_group_name}: {len(WaitingConsumer.rooms[self.room_group_name])}") #*DEBUG
            if len(WaitingConsumer.rooms[self.room_group_name]) == self.LEN_NEEDED:
                await self.redirect_all_players()

        else:
            await self.close()

    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            if hasattr(self, 'room_group_name') and self.room_group_name in WaitingConsumer.rooms:
                WaitingConsumer.rooms[self.room_group_name].discard(self.user.username)
                if not WaitingConsumer.rooms[self.room_group_name]:
                    del WaitingConsumer.rooms[self.room_group_name]

                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )

                # Update player list
                await self.send_player_list_to_all()


    async def send_player_list_to_all(self):
        '''
            Send player list of the room
        '''
        player_list = list(WaitingConsumer.rooms.get(self.room_group_name, set()))
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_player_list",
                "players": player_list,
            }
        )

    async def broadcast_player_list(self, event):
        await self.send(text_data=json.dumps({
            "type": "player_list",
            "players": event["players"]
        }))

    async def redirect_all_players(self):
        '''
            Redirect players in their game room
        '''
        print(f'Redirecting players in {self.room_group_name}')

        player_usernames = list(WaitingConsumer.rooms.get(self.room_group_name, []))
        
        if self.GAME == 'private':
            self.GAME = 'pong'
            self.MODE = '1v1'
            user1 = await sync_to_async(User.objects.get)(username=player_usernames[0])
            user2 = await sync_to_async(User.objects.get)(username=player_usernames[1])
            match = await sync_to_async(Match.objects.create)(game="private_1v1", user1=user1, user2=user2, created_at=timezone.now())

        if self.GAME == 'pong':
            if self.MODE == '1v1':
                user1 = await sync_to_async(User.objects.get)(username=player_usernames[0])
                user2 = await sync_to_async(User.objects.get)(username=player_usernames[1])
                match = await sync_to_async(Match.objects.create)(game="pong_1v1", user1=user1, user2=user2, created_at=timezone.now())
            elif self.MODE == '2v2':
                user1 = await sync_to_async(User.objects.get)(username=player_usernames[0])
                user2 = await sync_to_async(User.objects.get)(username=player_usernames[1])
                user3 = await sync_to_async(User.objects.get)(username=player_usernames[2])
                user4 = await sync_to_async(User.objects.get)(username=player_usernames[3])
                match = await sync_to_async(Matchs.objects.create)(game="pong_2v2", user1=user1, user2=user2, user3=user3, user4=user4, created_at=timezone.now())
            elif self.MODE == 'AI':
                user1 = await sync_to_async(User.objects.get)(username=player_usernames[0])
                ai = await sync_to_async(User.objects.get)(username="AI.")
                match = await sync_to_async(Match.objects.create)(game="pong_ai", user1=user1, user2=ai, created_at=timezone.now())
            if self.MODE == 'tournament':
                user1 = await sync_to_async(User.objects.get)(username=player_usernames[0])
                user2 = await sync_to_async(User.objects.get)(username=player_usernames[1])
                user3 = await sync_to_async(User.objects.get)(username=player_usernames[2])
                user4 = await sync_to_async(User.objects.get)(username=player_usernames[3])
                match = await sync_to_async(Tournament.objects.create)(user1=user1, user2=user2, user3=user3, user4=user4, created_at=timezone.now())

        elif self.GAME == 'puissance4':
            if self.MODE == '1v1':
                user1 = await sync_to_async(User.objects.get)(username=player_usernames[0])
                user2 = await sync_to_async(User.objects.get)(username=player_usernames[1])
                match = await sync_to_async(Match.objects.create)(game="puissance4_1v1", user1=user1, user2=user2, created_at=timezone.now())

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_redirect",
                "game": self.GAME,
                "mode": self.MODE,
                "id": match.id
            }
        )

    async def broadcast_redirect(self, event):
        '''
            Redirection broadcast message
        '''
        await self.send(text_data=json.dumps({
            "type": "redirect",
            "game": event["game"],
            "mode": event["mode"],
            "id": event["id"]
        }))

    @sync_to_async
    def get_friendship(self):
        return Friend.objects.filter(
            (Q(user1=self.user.id) | Q(user2=self.user.id)),
            id=self.MODE,
            status=True
        ).first()