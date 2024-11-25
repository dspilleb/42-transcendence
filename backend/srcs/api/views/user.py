from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.files.images import get_image_dimensions
from django.contrib.auth import logout as auth_logout, authenticate, login as auth_login
from srcs.user.models import CustomUser as User
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from srcs.community.models import Friend, Blocked
from django.db.models import Q
from srcs.api.serializers.settings import SettingsSerializer
import os

API_KEY = os.getenv('API_KEY', '')

@api_view(['GET'])
def is_authenticated(request):
    """
    A api function who check if the user is authenticated or not.

    Returns:
        Response: is authentificated (true/false)
    """
    is_authenticated = request.user.is_authenticated
    return Response({'is_authenticated': is_authenticated}, status=status.HTTP_200_OK)

@api_view(['POST'])
def logout(request):
    """
    A api function who logout the user if the user is authenticated

    Returns:
        Response: logout (true/false), message (error, success)
    """
    if request.user.is_authenticated:
        auth_logout(request)
        return Response({'logout': True, "success_message": "Logout successfull."}, status=status.HTTP_200_OK)
    return Response({"logout": True, "error_message": "Already logout."}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def login(request):
    """
    A api function who login the user if the user is not authenticated

    Returns:
        Response: login (true/false), message (error, success)
    """
    if request.user.is_authenticated:
        return Response({
            'login': False,
            'error_message': 'You are already logged in. Please logout first.'
        }, status=status.HTTP_400_BAD_REQUEST)

    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({
            'login': False,
            'error_message': 'Username and password are required.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user = authenticate(request, username=username, password=password)
    if user is not None:
        auth_login(request, user)
        return Response({
            'login': True,
            'success_message': 'Login successful.'
        }, status=status.HTTP_200_OK)

    return Response({
        'login': False,
        'error_message': 'Invalid username or password.'
    }, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
def register(request):
    """
    API function to register a new user and log them in if successful.
    """
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')
    confirm_password = request.data.get('confirm_password')

    if len(username) < 5 or len(username) > 20:
        return Response({
            'register': False,
            'error_message': 'Username is too short (< 5) or too long (> 20).'
        }, status=status.HTTP_400_BAD_REQUEST)

    if len(password) < 5 or len(password) > 32:
        return Response({
            'register': False,
            'error_message': 'Password is too short (< 5) or too long (> 32).'
        }, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({
            'register': False,
            'error_message': 'Username already exists.'
        }, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email=email).exists():
        return Response({
            'register': False,
            'error_message': 'Email already in use.'
        }, status=status.HTTP_400_BAD_REQUEST)

    if password != confirm_password:
        return Response({
            'register': False,
            'error_message': 'Passwords do not match.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()
        auth_login(request, user)
        return Response({
            'register': True,
            'success_message': 'Registration successful. You are now logged in.'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'register': False,
            'error_message': f'An error occurred: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def settings(request):
    serializer = SettingsSerializer(data=request.data)

    if serializer.is_valid():
        action = serializer.validated_data['action']
        value = serializer.validated_data.get('value')
        avatar = serializer.validated_data.get('avatar')
        user = request.user

        # Handle avatar update
        if action == 'avatar' and avatar:

            # Delete old avatar
            if user.avatar.name != 'avatars/profile.png':
                old_avatar_path = os.path.join('/frontend/media', user.avatar.name)
                if os.path.isfile(old_avatar_path):
                    os.remove(old_avatar_path)

            user.avatar = avatar
            user.save()
            return Response({'success_message': 'Avatar updated successfully.'})

        # Handle username update
        elif action == 'username' and value:
            if User.objects.filter(username=value).exclude(id=user.id).exists():
                return Response({'error_message': 'Username already taken.'}, status=status.HTTP_400_BAD_REQUEST)
            elif user.username == value:
                return Response({'error_message': 'You need to use your keyboard to change your username.'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                user.username = value
                user.save()
                return Response({'success_message': f'Username updated successfully to {value}'})

        # Handle email update
        elif action == 'email' and value:
            if User.objects.filter(email=value).exclude(id=user.id).exists():
                return Response({'error_message': 'Email already taken.'}, status=status.HTTP_400_BAD_REQUEST)
            elif user.email == value:
                return Response({'error_message': 'You need to use your keyboard to change your email.'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                user.email = value
                user.save()
                return Response({'success_message': f'Email updated successfully to {value}'})

        # Handle language update
        elif action == 'language' and value:
            if user.language == value:
                return Response({'error_message': 'You need to use your mouse to change your language.'}, status=status.HTTP_400_BAD_REQUEST)
            elif value in ['EN', 'FR', 'DE']:
                user.language = value
                user.save()
                return Response({'success_message': 'Language updated successfully.'})
            else:
                return Response({'error_message': 'Invalid language selection.'}, status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response({'error_message': 'Invalid action or missing value.'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        error_messages = [f"{', '.join(errors)}" for field, errors in serializer.errors.items()]
        return Response({'error_message': error_messages}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def friend(request):
    profile = request.data.get('profile')
    action = request.data.get('type')

    if not profile or not action:
        return Response({'error_message': 'Profile and type are required.'}, status=status.HTTP_400_BAD_REQUEST)

    user_instance = User.objects.filter(username=profile).first()
    if not user_instance:
        return Response({'error_message': f'User {profile} does not exist. Maybee reload the profile page.'}, status=status.HTTP_404_NOT_FOUND)

    if user_instance == request.user:
        return Response({'error_message': 'You cannot perform this action on yourself.'}, status=status.HTTP_400_BAD_REQUEST)

    friend = Friend.objects.filter(Q(user1=request.user, user2=user_instance) | Q(user1=user_instance, user2=request.user)).first()
    block = Blocked.objects.filter(Q(user1=request.user, user2=user_instance) | Q(user1=user_instance, user2=request.user)).first()

    if action == 'add':
        if block:
            return Response({'error_message': f"You cannot send a friend request to {profile} due to a block."}, status=status.HTTP_403_FORBIDDEN)

        if friend:
            if friend.status:
                return Response({'error_message': f'You are already friends with {profile}.'}, status=status.HTTP_400_BAD_REQUEST)
            elif friend.user1 == request.user:
                return Response({'error_message': f'A friend request was already sent to {profile}.'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                friend.status = True
                friend.save()
                return Response({"profile": profile, 'success_message': f'You and {profile} are now friends!'}, status=status.HTTP_200_OK)
        else:
            Friend.objects.create(user1=request.user, user2=user_instance, status=False)
            return Response({"profile": profile, 'success_message': f'Friend request sent to {profile}.'}, status=status.HTTP_200_OK)

    elif action == 'remove':
        if not friend:
            return Response({'error_message': f"{profile} is not in your friend list."}, status=status.HTTP_400_BAD_REQUEST)

        if friend.status:
            friend.delete()
            return Response({"profile": profile, 'success_message': f"{profile} has been removed from your friends."}, status=status.HTTP_200_OK)
        elif friend.user1 == request.user:
            friend.delete()
            return Response({"profile": profile, 'success_message': f"{profile}'s friend request successfully canceled."}, status=status.HTTP_200_OK)
        else:
            return Response({'error_message': f"No pending friend request to {profile}."}, status=status.HTTP_400_BAD_REQUEST)

    else:
        return Response({'error_message': 'Invalid action. Must be "add" or "remove".'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def block(request):
    profile = request.data.get('profile')
    type = request.data.get('type')

    if not profile or not type:
        return Response({'error_message': 'Profile and type are required.'}, status=status.HTTP_400_BAD_REQUEST)

    user_instance = User.objects.filter(username=profile).first()
    if not user_instance:
        return Response({'error_message': f'User {profile} does not exist. Maybee reload the profile page.'}, status=status.HTTP_404_NOT_FOUND)

    if user_instance == request.user:
        return Response({'error_message': 'You cannot block yourself.'}, status=status.HTTP_400_BAD_REQUEST)

    if type == 'add':
        existing_block = Blocked.objects.filter(user1=request.user, user2=user_instance).first()
        if existing_block:
            return Response({'error_message': f'{profile} is already blocked.'}, status=status.HTTP_400_BAD_REQUEST)

        Blocked.objects.create(user1=request.user, user2=user_instance)

        Friend.objects.filter(Q(user1=request.user, user2=user_instance) | Q(user1=user_instance, user2=request.user)).delete()

        return Response({"profile": profile, 'success_message': f'Successfully blocked {profile}.'}, status=status.HTTP_200_OK)

    elif type == 'remove':
        existing_block = Blocked.objects.filter(user1=request.user, user2=user_instance).first()
        if not existing_block:
            return Response({'error_message': f'{profile} is not blocked.'}, status=status.HTTP_400_BAD_REQUEST)
        existing_block.delete()
        return Response({"profile": profile, 'success_message': f'{profile} is no longer blocked.'}, status=status.HTTP_200_OK)

    else:
        return Response({'error_message': 'Invalid type. Must be "add" or "remove".'}, status=status.HTTP_400_BAD_REQUEST)