from rest_framework.response import Response
from rest_framework.generics import ListAPIView, RetrieveAPIView

from django.core.cache import cache
from django.shortcuts import get_object_or_404

from chats.models import Chat
from chats.serializers import (
    ChatSerializer,
    MessageSerializer,
    NewChatMessageSerializer,
)


class ChatEndpoint(RetrieveAPIView):
    queryset = Chat.objects.select_related("turker").all()
    serializer_class = ChatSerializer
    lookup_url_kwarg = "chat_id"

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["user"] = self.request.user
        return context


class ListChatMessagesEndpoint(ListAPIView):
    serializer_class = MessageSerializer

    @property
    def chat_cache_key(self):
        return f'chat-{self.kwargs["chat_id"]}-messages'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["user"] = self.request.user
        return context

    def get_queryset(self):
        messages = cache.get(self.chat_cache_key)

        if not messages:
            chat = get_object_or_404(Chat, id=self.kwargs["chat_id"])
            messages = chat.messages.select_related("sender", "reply_to").all()
            cache.set(self.chat_cache_key, messages)

        return messages

    def post(self, request, chat_id):
        data = {
            "content": request.data.get("content", "").strip(),
            "reply_to": str(request.data.get("reply_to", "")).strip(),
            "sender": request.user.id,
            "chat": get_object_or_404(Chat, id=self.kwargs["chat_id"]).id,
        }

        input_serializer = NewChatMessageSerializer(data=data)
        input_serializer.is_valid(raise_exception=True)

        new_msg = input_serializer.save()
        cache.delete(self.chat_cache_key)
        return Response(self.get_serializer(instance=new_msg).data, status=201)


class UserAvailableChatsEndpoint(ListAPIView):
    serializer_class = ChatSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_regular:
            return Chat.objects.select_related("turker").all()
        elif user.is_turker:
            return [
                Chat.objects.get_collective_chat(),
                Chat.objects.get_turker_chat(user.id),
            ]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["user"] = self.request.user
        return context
