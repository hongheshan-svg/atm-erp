"""Keep Django's password checks while providing stable Chinese messages."""

from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import override


def validate_password(password, user=None):
    messages = {
        'password_too_short': '密码至少需要 %(min_length)d 个字符。',
        'password_too_common': '这个密码太常见了，请换一个密码。',
        'password_entirely_numeric': '密码不能只包含数字。',
        'password_too_similar': '密码不能与用户名、姓名等个人信息过于相似。',
    }
    with override('zh-hans'):
        try:
            django_validate_password(password, user)
        except ValidationError as exc:
            raise ValidationError(
                [
                    ValidationError(messages.get(error.code, error.message), code=error.code, params=error.params)
                    for error in exc.error_list
                ]
            ) from exc
