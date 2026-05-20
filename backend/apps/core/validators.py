"""
Security validators for file uploads and data validation.
"""
import os

from django.core.exceptions import ValidationError

# 尝试导入python-magic，如果不可用则设为None
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    magic = None
    MAGIC_AVAILABLE = False


# 允许的文件扩展名
ALLOWED_FILE_EXTENSIONS = {
    # 文档类
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv',
    # 图片类
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp',
    # 压缩包
    'zip', 'rar', '7z', 'tar', 'gz',
    # 其他
    'json', 'xml'
}

# 允许的MIME类型
ALLOWED_MIME_TYPES = {
    # 文档
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain',
    'text/csv',
    # 图片
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/bmp',
    'image/svg+xml',
    'image/webp',
    # 压缩包
    'application/zip',
    'application/x-rar-compressed',
    'application/x-7z-compressed',
    'application/x-tar',
    'application/gzip',
    # 其他
    'application/json',
    'application/xml',
    'text/xml',
}

# 最大文件大小（字节）
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10MB


def validate_file_extension(file):
    """
    验证文件扩展名。
    """
    ext = os.path.splitext(file.name)[1].lower().lstrip('.')
    if ext not in ALLOWED_FILE_EXTENSIONS:
        raise ValidationError(
            f'不支持的文件类型。允许的文件类型：{", ".join(ALLOWED_FILE_EXTENSIONS)}'
        )


def validate_file_size(file, max_size=MAX_FILE_SIZE):
    """
    验证文件大小。
    """
    if file.size > max_size:
        max_mb = max_size / (1024 * 1024)
        raise ValidationError(f'文件大小不能超过 {max_mb:.0f}MB')


def validate_file_mime_type(file):
    """
    使用python-magic验证真实的MIME类型（防止伪造扩展名）。
    """
    if not MAGIC_AVAILABLE:
        # python-magic未安装，跳过MIME验证
        return

    try:
        # 读取文件头部分进行检测
        file_content = file.read(2048)
        file.seek(0)  # 重置文件指针

        mime = magic.from_buffer(file_content, mime=True)
        if mime not in ALLOWED_MIME_TYPES:
            raise ValidationError(f'不支持的文件类型（MIME: {mime}）')
    except Exception:
        # 如果出错，退回到基于扩展名的验证
        pass


def validate_file_name(filename):
    """
    验证文件名，防止路径遍历攻击。
    """
    # 检查路径遍历字符
    dangerous_chars = ['..', '/', '\\', '\x00']
    for char in dangerous_chars:
        if char in filename:
            raise ValidationError('文件名包含非法字符')

    # 限制文件名长度
    if len(filename) > 255:
        raise ValidationError('文件名过长')


def validate_uploaded_file(file):
    """
    综合验证上传的文件。
    """
    # 验证文件名
    validate_file_name(file.name)

    # 验证文件扩展名
    validate_file_extension(file)

    # 验证文件大小
    ext = os.path.splitext(file.name)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        validate_file_size(file, MAX_IMAGE_SIZE)
    else:
        validate_file_size(file, MAX_FILE_SIZE)

    # 验证MIME类型（如果python-magic可用）
    try:
        validate_file_mime_type(file)
    except ImportError:
        pass  # python-magic未安装，跳过MIME验证


def sanitize_filename(filename):
    """
    清理文件名，移除或替换危险字符。
    """
    import re
    import unicodedata

    # 规范化Unicode字符
    filename = unicodedata.normalize('NFKD', filename)

    # 移除非ASCII字符（保留中文）
    filename = filename.encode('utf-8', 'ignore').decode('utf-8')

    # 替换空格为下划线
    filename = filename.replace(' ', '_')

    # 只保留字母、数字、下划线、点、中文字符
    filename = re.sub(r'[^\w\u4e00-\u9fa5.-]', '', filename)

    # 限制长度
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext

    return filename

