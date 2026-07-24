"""AI 网关 API:POST /api/ai/chat/(仅系统管理员)。

调用 LLMGateway 完成一次对话,并将会话与消息落库(AIConversation/AIMessage)。
默认 provider 关闭时返回 NullProvider 的“未配置”响应(HTTP 200),不发起外部调用。
可选 use_rag=true 时先经 rag.retrieve 拼接检索上下文(RAG 基础脚手架)。
"""

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsSystemAdmin

from .gateway import LLMGateway
from .models import AIConversation, AIMessage
from .rag import retrieve


class ChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['system', 'user', 'assistant'], default='user')
    content = serializers.CharField(allow_blank=True)


class ChatRequestSerializer(serializers.Serializer):
    """请求体:提供 messages 列表,或单条 message 文本。"""

    messages = ChatMessageSerializer(many=True, required=False)
    message = serializers.CharField(required=False, allow_blank=True)
    conversation_id = serializers.IntegerField(required=False)
    use_rag = serializers.BooleanField(default=False)
    scene = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        if not attrs.get('messages') and not attrs.get('message'):
            raise serializers.ValidationError('必须提供 messages 或 message 之一。')
        return attrs


class AIChatView(APIView):
    """AI 对话入口。仅系统管理员可访问(硬门槛,独立于菜单兜底授权)。"""

    permission_classes = [IsSystemAdmin]

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # 归一化为 messages 列表。
        messages = list(data.get('messages') or [])
        if not messages and data.get('message'):
            messages = [{'role': 'user', 'content': data['message']}]

        # 可选 RAG:将检索片段作为 system 上下文前置注入。
        rag_hits = []
        if data.get('use_rag'):
            last_user = next((m['content'] for m in reversed(messages) if m.get('role') == 'user'), '')
            rag_hits = retrieve(last_user)
            if rag_hits:
                context = '\n'.join(f'- [{h["source"]}] {h["title"]}: {h["text"]}' for h in rag_hits)
                messages = [{'role': 'system', 'content': f'参考资料:\n{context}'}] + messages

        gateway = LLMGateway()
        result = gateway.chat(messages)

        # 落库:会话 + 消息(用户消息 + 助手回复)。
        conversation = self._get_or_create_conversation(request, data, gateway)
        self._persist_messages(request, conversation, messages, result)

        return Response(
            {
                'conversation_id': conversation.id,
                'provider': result.get('provider'),
                'model': result.get('model'),
                'configured': result.get('configured'),
                'content': result.get('content'),
                'usage': result.get('usage', {}),
                'rag_hits': rag_hits,
            },
            status=status.HTTP_200_OK,
        )

    def _get_or_create_conversation(self, request, data, gateway):
        conversation_id = data.get('conversation_id')
        if conversation_id:
            conversation = AIConversation.objects.filter(id=conversation_id).first()
            if conversation:
                return conversation
        return AIConversation.objects.create(
            user=request.user if request.user.is_authenticated else None,
            provider=gateway.provider.name,
            model=gateway.model or '',
            scene=data.get('scene', ''),
            created_by=request.user if request.user.is_authenticated else None,
        )

    def _persist_messages(self, request, conversation, messages, result):
        user = request.user if request.user.is_authenticated else None
        # 记录本次请求的最后一条用户消息与助手回复(基础审计)。
        last_user = next((m for m in reversed(messages) if m.get('role') == 'user'), None)
        if last_user:
            AIMessage.objects.create(
                conversation=conversation,
                role='user',
                content=last_user.get('content', ''),
                created_by=user,
            )
        AIMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=result.get('content', ''),
            tokens=result.get('usage', {}).get('total_tokens', 0),
            created_by=user,
        )
