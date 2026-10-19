"""Chinese presentation for validation errors, without changing keys or error codes."""

import re

from django.utils.translation import override
from rest_framework.exceptions import ErrorDetail

MESSAGES = {
    'required': '此项为必填项。',
    'blank': '此项不能为空。',
    'null': '此项不能为空。',
    'invalid': '填写格式不正确，请检查后重试。',
    'invalid_choice': '请选择列表中的有效选项。',
    'unique': '此值已存在，请核对是否重复录入。',
    'unique_together': '这些字段的组合已存在，请核对是否重复录入。',
    'does_not_exist': '关联记录不存在，请重新选择。',
    'incorrect_type': '填写的数据类型不正确，请重新选择或填写。',
    'not_found': '记录不存在或无权访问，请刷新后重试。',
    'permission_denied': '没有执行该操作的权限。',
    'not_authenticated': '请先登录后再操作。',
    'authentication_failed': '身份验证失败，请重新登录。',
    'no_active_account': '用户名或密码不正确，或账号已停用。',
    'token_not_valid': '登录凭据已失效，请重新登录。',
    'token_expired': '登录凭据已过期，请重新登录。',
    'password_changed': '密码已修改，请重新登录。',
    'bad_authorization_header': '登录凭据格式不正确，请重新登录。',
    'parse_error': '提交内容格式不正确，请检查后重新提交。',
    'method_not_allowed': '不支持此操作方式，请刷新页面后重试。',
    'not_acceptable': '不支持此响应格式，请刷新页面后重试。',
    'unsupported_media_type': '不支持此提交格式，请按页面要求重新提交。',
    'throttled': '操作过于频繁，请稍后再试。',
}


def chinese_error(value):
    code = getattr(value, 'code', None)
    text = str(value)
    # Framework parser details and invalid choices may embed English implementation names.
    if code in {'parse_error', 'invalid_choice', 'unique', 'unique_together'}:
        text = MESSAGES[code]
    elif re.search(r'[A-Za-z]', text) and not re.search(r'[\u4e00-\u9fff]', text):
        text = MESSAGES.get(code, '填写内容不符合要求，请检查后重试。')
    return ErrorDetail(text, code=code) if isinstance(value, ErrorDetail) else text


def localize_detail(detail):
    if isinstance(detail, dict):
        return {
            key: value
            if key in {'row', 'token_class', 'token_type', 'actions'}
            or (key == 'code' and isinstance(value, str) and re.fullmatch(r'[a-z_]+', value))
            else localize_detail(value)
            for key, value in detail.items()
        }
    if isinstance(detail, (list, tuple)):
        return [localize_detail(value) for value in detail]
    return chinese_error(detail) if isinstance(detail, str) else detail


def validation_detail(exc):
    def render(error):
        code = error.code
        if code in {'unique', 'unique_together', 'invalid_choice'}:
            text = MESSAGES[code]
        elif code == 'invalid' and error.params and {'model', 'field'} <= error.params.keys():
            text = '关联记录不存在，请重新选择。'
        elif re.match(r'^(Constraint .+ is violated|违反了约束)', str(error.message)):
            text = '数据不符合业务校验规则，请核对填写内容。'
        else:
            with override('zh-hans'):
                text = next(iter(error))
        return chinese_error(ErrorDetail(text, code=code))

    if hasattr(exc, 'error_dict'):
        return {key: [render(error) for error in errors] for key, errors in exc.error_dict.items()}
    return [render(error) for error in exc.error_list]
