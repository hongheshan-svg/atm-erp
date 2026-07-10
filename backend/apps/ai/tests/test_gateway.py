"""AI 网关基础脚手架测试。

覆盖:NullProvider 默认关闭语义、网关 provider 解析与回落、RAG 空查询短路、
以及 /api/ai/chat/ 的系统管理员门槛与消息落库。所有用例在 NullProvider 下通过,
不发起任何外部网络调用,亦不依赖 anthropic SDK。
"""

from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.ai.gateway import AnthropicProvider, LLMGateway, NullProvider
from apps.ai.models import AIConversation, AIMessage
from apps.ai.rag import retrieve
from apps.ai.views import AIChatView


class NullProviderTest(SimpleTestCase):
    def test_null_provider_reports_not_configured(self):
        provider = NullProvider(model='x')
        self.assertFalse(provider.configured)
        result = provider.chat([{'role': 'user', 'content': 'hi'}])
        self.assertFalse(result['configured'])
        self.assertEqual(result['provider'], 'null')
        self.assertIn('未配置', result['content'])
        self.assertEqual(result['usage']['total_tokens'], 0)


@override_settings(AI_PROVIDER='', AI_API_KEY='', AI_MODEL='claude-opus-4-8')
class LLMGatewayResolutionTest(SimpleTestCase):
    def test_empty_provider_falls_back_to_null(self):
        gateway = LLMGateway()
        self.assertIsInstance(gateway.provider, NullProvider)
        self.assertFalse(gateway.configured)
        result = gateway.chat([{'role': 'user', 'content': 'hello'}])
        self.assertFalse(result['configured'])

    def test_unknown_provider_falls_back_to_null(self):
        gateway = LLMGateway(provider='does-not-exist', api_key='k')
        self.assertIsInstance(gateway.provider, NullProvider)

    def test_anthropic_without_key_is_null(self):
        # 已知 provider 但缺密钥 -> 回落 NullProvider,不触发任何 SDK 导入/调用。
        gateway = LLMGateway(provider='anthropic', api_key='')
        self.assertIsInstance(gateway.provider, NullProvider)

    def test_anthropic_provider_registered_with_key(self):
        gateway = LLMGateway(provider='anthropic', api_key='sk-test', model='claude-opus-4-8')
        self.assertIsInstance(gateway.provider, AnthropicProvider)
        self.assertTrue(gateway.provider.configured)


class RagRetrieveTest(SimpleTestCase):
    def test_empty_query_returns_empty(self):
        self.assertEqual(retrieve(''), [])
        self.assertEqual(retrieve('   '), [])


@override_settings(ELASTICSEARCH_DSL={'default': {'hosts': ''}})
class RagDbFallbackTest(TestCase):
    def test_db_fallback_returns_list_without_es(self):
        # 无 ES 主机 -> 直接走数据库 icontains(空表返回空列表,不抛异常)。
        self.assertEqual(retrieve('不存在的关键字'), [])


class AIChatViewTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @override_settings(AI_PROVIDER='', AI_API_KEY='')
    def test_superuser_chat_persists_and_returns_null_response(self):
        admin = User.objects.create(username='ai_admin', employee_id='AI1', is_staff=True, is_superuser=True)
        request = self.factory.post('/api/ai/chat/', {'message': '你好'}, format='json')
        force_authenticate(request, user=admin)
        response = AIChatView.as_view()(request)

        self.assertEqual(response.status_code, 200, getattr(response, 'data', None))
        self.assertEqual(response.data['provider'], 'null')
        self.assertFalse(response.data['configured'])
        self.assertIn('未配置', response.data['content'])

        # 会话与消息已落库(1 会话,用户 + 助手 2 条消息)。
        self.assertEqual(AIConversation.objects.count(), 1)
        self.assertEqual(AIMessage.objects.filter(role='user').count(), 1)
        self.assertEqual(AIMessage.objects.filter(role='assistant').count(), 1)

    def test_anonymous_is_forbidden(self):
        request = self.factory.post('/api/ai/chat/', {'message': 'hi'}, format='json')
        response = AIChatView.as_view()(request)
        self.assertIn(response.status_code, (401, 403))
