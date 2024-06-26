from django.shortcuts import render
from django.contrib.auth import get_user_model, login, logout, authenticate
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserRegistrationSerializer, UserSerializer, UpdateUserSerializer, FriendRequestSerializer, FriendSerializer, MatchSerializer
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
from django.template.loader import render_to_string

from rest_framework.filters import SearchFilter
from django.db.models import OuterRef, Subquery, Q
from django.conf import settings
import random, requests
from rest_framework.decorators import api_view
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail

import secrets
from django.core.cache import cache
# Create your views here.

User = get_user_model()
class LanguagePreference(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        if request.method == 'POST':
            user = request.user
            language = request.data.get('language')
            if language:
                user.languagePreference = language
                user.save()
                return JsonResponse({'status': 'success', 'message': 'Dil tercihi güncellendi.'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Dil tercihi güncellenemedi.'})
        return JsonResponse({'status': 'error', 'message': 'Geçersiz istek.'})
    def get(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated:
            language_preference = user.languagePreference if user.languagePreference else 'default'
            return JsonResponse({'language': language_preference})
        else:
            return JsonResponse({'error': 'Kullanıcı giriş yapmamış.'}, status=401)


def get_image(request, image_name):
    # Resmin dosya yolu
    image_path = os.path.join(settings.BASE_DIR, 'static/images', image_name)
    # Resmi HTTP yanıtı olarak gönder
    return FileResponse(open(image_path, 'rb'), content_type='image/jpeg')

class SendOTPView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        if (request.method == "POST" and request.data.get('type') == 'send'):
            auth_header = request.headers.get('Authorization')
            if auth_header:
                # Authorization: Bearer your_token_here
                token = auth_header.split(' ')[1]  # Bearer kelimesinden sonra gelen token'ı al, 0->Bearer 1->JWT Token
            else:
                return Response({'message': 'Your token is not received'}, status=status.HTTP_400_NOT_FOUND)
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = decoded_token.get("user_id")
            # current_user = request.user
            current_user = User.objects.get(id=user_id)
            try:
                otp = ''.join([str(random.randint(0, 9)) for _ in range(4)])
                current_user.otp = otp
                current_user.save()
                html_message = render_to_string('send_mail.html', {'otp': otp})
                send_mail(
                    'Ping Pong Game \'e Hosgeldiniz!',
                    None,
                    # f'Giris yapmak icin kodunuz: {otp}',
                    'transcendenceecole42@gmail.com',
                    [current_user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                return Response({'message': 'OTP sent to your email'}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        elif (request.method == "POST" and request.data.get('type') == 'verify'):
            current_user = request.user
            code_to_verify = request.data.get('code')
            if(current_user.otp == code_to_verify):
                current_user.otp = ''  # Doğrulama kodunu sıfırla
                current_user.save()
                return Response({'status': 'Success!'}, status=status.HTTP_200_OK)
            else:
                return Response({'status': 'Failure!'}, status=status.HTTP_400_BAD_REQUEST)

class Profile(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    # Kullanicin profil bilgilerine erismesi icin kullanilir
    def get(self, request, *args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if auth_header:
            # Authorization: Bearer your_token_here
            token = auth_header.split(' ')[1]  # Bearer kelimesinden sonra gelen token'ı al, 0->Bearer 1->JWT Token
        else:
            return Response({'message': 'Your token is not received'}, status=status.HTTP_400_NOT_FOUND)
        decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = decoded_token.get("user_id")
        # current_user = request.user
        current_user = User.objects.get(id=user_id)
        
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
            return Response(UserSerializer(instance=current_user).data, status=status.HTTP_200_OK)
            # return Response("Profile updated successfully", status=status.HTTP_200_OK)
            # Niran guncelleme yapildiktan sonra kullanici bilgilerinin dondurulmesini istedigi icin degistirildi
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserDetailView(APIView):
    def get(self, request, username, *args, **kwargs):
        try:
            user = User.objects.get(username=username)
            serializer = UserSerializer(user)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

class ListUsersView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, *args, **kwargs):
        user = request.user
        username = request.query_params.get('searchTerm', '')
        # Gönderilen ve alınan arkadaşlık istekleri için kullanıcıların username'lerini al
        sent_friend_requests = FriendRequest.objects.filter(sender=user).values_list('receiver__username', flat=True)
        received_friend_requests = FriendRequest.objects.filter(receiver=user).values_list('sender__username', flat=True)
        # Gönderilen ve alınan isteklerdeki tüm unique kullanıcı username'lerini birleştir
        users_to_exclude = set(list(sent_friend_requests) + list(received_friend_requests))
        # Kullanıcıları filtrele
        if username:
            # Eğer arama terimi varsa, bu terime göre filtrele
            users = User.objects.filter(username__icontains=username)
        else:
            # Eğer arama terimi yoksa, tüm kullanıcıları al
            users = User.objects.all()
        # Mevcut kullanıcı ve arkadaşlık isteği ilişkili kullanıcıları dışla
        users = users.exclude(username__in=users_to_exclude).exclude(username=user.username)
        # Serileştir ve yanıtla
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

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
        if current_user is not None and current_user.is_authenticated and not current_user.has_logged_in:
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
            return Response(token, status=status.HTTP_200_OK)
        # Kullanici dogrulanamamis ise
        else:
            return Response({'error': 'Geçersiz kimlik bilgileri'}, status=status.HTTP_400_BAD_REQUEST)

class UserLogoutView(APIView):
    def post(self, request, *args, **kwargs):
        current_user = request.user
        if current_user.is_authenticated:
            # if not current_user.has_logged_in:
            #     return Response({"message": "Zaten oturum açmış değilsiniz."}, status=status.HTTP_400_BAD_REQUEST)
            logout(request)
            current_user.has_logged_in = False
            current_user.save()
            return Response({"message": "Başarılı çıkış."}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "Authenticate olmayan kullanıcı çıkış yapamaz"}, status=status.HTTP_400_BAD_REQUEST)

class Friends(APIView):
    def get(self, request, *args, **kwargs):
        username = request.query_params.get('searchTerm')
        current_user = request.user
        current_friends = request.user.friends 
        if current_user.is_authenticated:
            if(username):
                current_friends = current_user.friends.filter(username__icontains=username)
            return Response(FriendSerializer(current_friends, many=True).data, status=status.HTTP_200_OK)
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
                        friend_request.delete() # Arkadaşlık isteğini sil
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
                    FriendRequest.objects.filter(sender=current_user, receiver=friend).delete()
                    payload ['response'] = friend.username + " removed from your friend list"
            else:
                payload ['response'] = "You must be authenticated to accept a friend request."
        return HttpResponse(json.dumps(payload), content_type="application/json")

class ViewFriendRequest(APIView):
    # Get the requests
    def get(self, request, *args, **kwargs):
        payload = {}
        user = request.user
        searchTerm = request.query_params.get('searchTerm')
        if user.is_authenticated:
            # Q nesnelerini kullanarak karmaşık sorguyu oluştur
            query = Q(sender=user, status='pending') | Q(sender=user, status='rejected') | \
                    Q(receiver=user, status='pending') | Q(receiver=user, status='rejected')
            
            # Eğer bir arama terimi varsa, sorguya ek filtreleme kriterleri ekle
            if searchTerm:
                query &= (Q(sender__username__icontains=searchTerm) | Q(receiver__username__icontains=searchTerm))

            friend_requests = FriendRequest.objects.filter(query).distinct()
            # Serializer'ı kullanarak JSON'a dönüştür
            serializer = FriendRequestSerializer(friend_requests, many=True, context={'request': request})
            payload['friend_requests'] = serializer.data
        else:
            payload['response'] = "You must be Authenticated to view"
        
        return HttpResponse(json.dumps(payload), content_type="application/json")

class MatchView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        current_user = request.user
        matches = current_user.matches.all()
        serializer = MatchSerializer(matches, many=True)
        return Response(serializer.data)
    def post(self, request):
        current_user = request.user
        serializer = MatchSerializer(data=request.data)
        if serializer.is_valid():
            # Maçı kaydetmeden önce kullanıcının maç geçmişine ekleyin
            match = serializer.save()
            current_user.matches.add(match)
            return Response(serializer.data, status=status.HTTP_201_CREATED)    
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def get_or_create_user(user_data):
    # Bu kısım projenizin User modeline bağlı olarak değişebilir.
    user, _ = User.objects.get_or_create(
        username=user_data['login'],
        defaults={
            'email': user_data['email'],
            'first_name': user_data['first_name'],
            'last_name': user_data['last_name'],
            'intra_avatar': user_data['image']['link'],
        }
    )
    return user

def exchange_code_for_token(code):
    token_url = 'https://api.intra.42.fr/oauth/token'
    token_data = {
        'grant_type': 'authorization_code',
        'client_id': settings.CLIENT_ID_42,
        'client_secret': settings.SECRET_42_ID,
        'code': code,
        'redirect_uri': settings.REDIRECT_URI_42
    }
    token_response = requests.post(token_url, data=token_data)
    token_response.raise_for_status()  # Hata varsa exception fırlatır.
    return token_response.json()

def get_user_info(access_token):
    user_info_url = 'https://api.intra.42.fr/v2/me'
    headers = {'Authorization': f'Bearer {access_token}'}
    user_response = requests.get(user_info_url, headers=headers)
    user_response.raise_for_status()  # Hata varsa exception fırlatır.
    return user_response.json()

@api_view(['POST'])
def account42(request):
    if request.method == 'POST':
        data = request.data
        authorization_code = data.get('code')

        if not authorization_code:
            return Response({'error': 'No authorization code provided'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token_info = exchange_code_for_token(authorization_code)
            user_info = get_user_info(token_info['access_token'])
            user = get_or_create_user(user_info)
            #Jwt token creation
            tokens = get_tokens_for_user(user)
            token = {
                # 'refresh': tokens['refresh'],
                'accessToken': tokens['access'],
            }
            user.has_logged_in = True
            user.save()
            return Response(token, status=status.HTTP_200_OK)
        except requests.RequestException as e:
            return Response({'error': 'Failed to authenticate with 42 API'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response({'error': 'Invalid request method'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
