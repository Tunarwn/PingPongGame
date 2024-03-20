from django.shortcuts import render
from django.contrib.auth import get_user_model, login, logout, authenticate
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserRegistrationSerializer, UserSerializer, UpdateUserSerializer, FriendRequestSerializer, FriendSerializer
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from rest_framework.filters import OrderingFilter
from .filters import UserFilter
from rest_framework.permissions import IsAuthenticated
import django_filters
import jwt, datetime, json
from django.http import HttpResponse
from .models import FriendRequest
from django.db.models import Q
from rest_framework import generics
from rest_framework_simplejwt.tokens import RefreshToken

from django.views.decorators.csrf import csrf_exempt
# Create your views here.

User = get_user_model()

def get_image(request, image_name):
    # Resmin dosya yolu
    image_path = os.path.join(settings.BASE_DIR, 'static/images', image_name)

    # Resmi HTTP yanıtı olarak gönder
    return FileResponse(open(image_path, 'rb'), content_type='image/jpeg')
    
class Profile(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    # Kullanicin profil bilgilerine erismesi icin kullanilir
    def get(self, request, *args, **kwargs):
        current_user = request.user
        if current_user.is_authenticated:
            return Response(UserSerializer(instance=current_user).data, status=status.HTTP_200_OK)
        else:
            return Response("You must be authenticated to view your profile page.", status=status.HTTP_401_UNAUTHORIZED)
    # Kullanicin profil bilgilerini guncellemesi icin kullanilir
    def patch(self, request, *args, **kwargs):
        queryset = User.objects.all()
        permission_classes = (IsAuthenticated)
        current_user = request.user
        serializer = UpdateUserSerializer(instance=current_user, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response("Profile updated successfully", status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class FriendListAPIView(APIView):
    def get(self, request, *args, **kwargs):
        current_user = request.user
        if current_user.is_authenticated:
            return Response(FriendSerializer(current_user.friends.all(), many=True).data, status=status.HTTP_200_OK)
        else:
            return Response("You must be authenticated to view your friends.", status=status.HTTP_401_UNAUTHORIZED)

class ListUsersView(ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        # Giriş yapmış olan kullanıcının ID'sini al
        current_user_id = self.request.user.id
        return User.objects.exclude(id=current_user_id)
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [django_filters.rest_framework.DjangoFilterBackend, OrderingFilter]
    filterset_class = UserFilter

class UserRegistrationView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(user.id, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserLoginView(APIView):
    @csrf_exempt
    def post(self, request, *args, **kwargs):
        username = request.data.get('username')
        password = request.data.get('password')
        if not username or not password:
            return Response({'error': 'Kullanıcı adı ve şifre gerekli'}, status=status.HTTP_400_BAD_REQUEST)
        current_user = authenticate(username=username, password=password)
        # Kullanici dogrulandi ve oturum acmadi ise
        if current_user.is_authenticated and not current_user.has_logged_in:
            login(request, current_user)
            current_user.has_logged_in = True
            current_user.save()
            #Jwt token creation
            refresh = RefreshToken.for_user(current_user)
            token = {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
            return Response(token, status=status.HTTP_200_OK)
        # Kullanici dogrulandi ve oturum acmis ise
        elif current_user is not None and current_user.has_logged_in:
            login(request, current_user)
            current_user.has_logged_in = True
            current_user.save()
            
            refresh = RefreshToken.for_user(current_user)
            token = {
                'error': 'Kullanıcı zaten oturum açmış',
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
            return Response(token, status=status.HTTP_400_BAD_REQUEST)
        # Kullanici dogrulanamamis ise
        else:
            return Response({'error': 'Geçersiz kimlik bilgileri'}, status=status.HTTP_400_BAD_REQUEST)

class UserLogoutView(APIView):
    def post(self, request, *args, **kwargs):
        current_user = request.user
        if current_user.is_authenticated:
            if not current_user.has_logged_in:
                return Response({"message": "Zaten oturum açmış değilsiniz."}, status=status.HTTP_400_BAD_REQUEST)
            
            logout(request)
            current_user.has_logged_in = False
            current_user.save()
            return Response({"message": "Başarılı çıkış."}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "Authenticate olmayan kullanıcı çıkış yapamaz"}, status=status.HTTP_400_BAD_REQUEST)

# class UserUpdateView(APIView):
#     permission_classes = [IsAuthenticated]
#     def post(self, request, *args, **kwargs):
#         serializer = UpdateSerializer(data=request.data)
#         if serializer.is_valid():
#             username = serializer.validated_data.get('username')
#             password = serializer.validated_data.get('password')
#             # Assuming user is authenticated
#             user = request.user
#             if user:
#                 # Update user object
#                 user.username = username
#                 user.set_password(password)
#                 user.save()
#                 return Response({'message': 'User information updated successfully'}, status=status.HTTP_200_OK)
#             else:
#                 return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
#         else:
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class Friends(APIView):
    def get(self, request, *args, **kwargs):
        current_user = request.user
        if current_user.is_authenticated:
            return Response(FriendSerializer(current_user.friends.all(), many=True).data, status=status.HTTP_200_OK)
        else:
            return Response("You must be authenticated to view your friends.", status=status.HTTP_401_UNAUTHORIZED)
    def post(self, request, *args, **kwargs):
        current_user = request.user
        payload = {}
        if request.method == "POST" and current_user.is_authenticated and request.data.get('type') == "send":
            try:
                receiver = User.objects.get(username=request.data.get('username'))
            except Exception as e:
                payload['response'] = str(e)
                return HttpResponse(json.dumps(payload), content_type="application/json")
            if receiver:
                if receiver == current_user:
                    payload['response'] = "You can't send a friend request to yourself."
                    return HttpResponse(json.dumps(payload), content_type="application/json")
                try:
                    # Get any friend requests (active and not-active)
                    friend_requests_sent = FriendRequest.objects.filter(sender=current_user, status='pending')
                    friend_requests_received = FriendRequest.objects.filter(receiver=current_user, status='pending')
                    # find if any of them are active
                    try:
                        for request in friend_requests_sent | friend_requests_received:
                            if request.is_active:
                                if request.sender == current_user and request.receiver == receiver:
                                    raise Exception("You already sent them a friend request.")
                                elif request.receiver == current_user and request.sender == receiver:
                                    raise Exception("You already received a friend request from them.")
                        # If none are active, then create a new friend request
                        friend_request = FriendRequest(sender=current_user, receiver=receiver)
                        friend_request.save()
                        payload['response'] = "Friend request sent."
                    except Exception as e:
                        payload ['response'] = str(e)
                except FriendRequest.DoesNotExist:
                    # There are no friend requests so create one.
                    friend_request = FriendRequest(sender=current_user, receiver=receiver)
                    friend_request.save()
                    payload ['response'] = "Friend request sent."
                if payload['response'] == None:
                    payload['response'] = "Something went wrong."
            else:
                payload['response'] = "Unable to send a friend request"
        # if user is not authenticated§
        elif not current_user.is_authenticated:
            payload['response'] = "You must be Authenticated to send a friend request"
        elif request.data.get('type') == "reply" and request.data.get('status') == "accept":
            sender_username = request.data.get('username')
            if request.method == "POST" and current_user.is_authenticated and sender_username:
                sender = User.objects.get(username=sender_username)
                try:
                    friend_request = FriendRequest.objects.get(sender=sender, receiver=current_user, is_active=True)
                except Exception as e:
                    payload ['response'] = str(e)
                    return HttpResponse(json.dumps(payload), content_type="application/json")
                if friend_request:
                    # Arkadaşlık isteği bulundu. Şimdi kabul edelim.
                    friend_request.accept()
                    payload['response'] = "Friend request accepted"
                else:
                    payload['response'] = "Friend request not found"
            else:
                payload['response'] = "You must be authenticated and provide a valid sender username to accept a friend request."
        elif request.data.get('type') == "reply" and request.data.get('status') == "reject":
            sender = User.objects.get(username=request.data.get('username'))
            if request.method == "POST" and current_user.is_authenticated and sender:
                friend_request = FriendRequest.objects.get(sender=sender, receiver=current_user)
                # confirm that is the correct request
                if friend_request.receiver == current_user:
                    if friend_request:
                        # found the request. Not accept it.
                        friend_request.decline()
                        payload ['response'] = "Friend request declined"
                    else:
                        payload ['response'] = "Something went wrong"
                else:
                    payload ['response'] = "That is not your request to accept."
            else:
                payload ['response'] = "You must be authenticated to accept a friend request."
        elif request.data.get('type') == "remove":
            friend = User.objects.get(username=request.data.get('username'))
            if request.method == "POST" and current_user.is_authenticated and friend:
                if not current_user.is_friend(friend):
                    payload ['response'] = "He/She is not your friend"
                else:
                    current_user.remove_friend(friend)
                    payload ['response'] = friend.username + " removed from your friend list"
            else:
                payload ['response'] = "You must be authenticated to accept a friend request."
        elif request.data.get('type') == "unfriend":
            friend = User.objects.get(username=request.data.get('username'))
            if request.method == "POST" and current_user.is_authenticated and friend:
                if not current_user.is_friend(friend):
                    payload ['response'] = "He/She is not your friend"
                else:
                    current_user.unfriend(friend)
                    payload ['response'] = friend.username + " removed from your friend list"
            else:
                payload ['response'] = "You must be authenticated to accept a friend request."
        return HttpResponse(json.dumps(payload), content_type="application/json")

class ViewFriendRequest(APIView):
    # Get the requests
    def get(self, request, *args, **kwargs):
        payload = {}
        user = request.user
        if user.is_authenticated:
            current_user = User.objects.get(pk=user.id)
            if current_user == user:
                friend_requests_sent = FriendRequest.objects.filter(sender=user, status='pending')
                friend_requests_received = FriendRequest.objects.filter(receiver=user, status='pending')
                
                # Hem gönderilen hem de alınan istekleri birleştirin
                friend_requests = friend_requests_sent | friend_requests_received
                
                # Serializer kullanarak JSON'a dönüştürme
                serializer = FriendRequestSerializer(friend_requests, many=True)
                payload['friend_requests'] = serializer.data
            else:
                payload['response'] = "You can't view another users friend requests."
        else:
            payload['response'] = "You must be Authenticated to view"
        return HttpResponse(json.dumps(payload), content_type="application/json")
