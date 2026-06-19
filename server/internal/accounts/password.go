package accounts

import (
	"crypto/pbkdf2"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"fmt"
	"strconv"
	"strings"
)

// Django 默认 PBKDF2PasswordHasher 编码格式:
//
//	pbkdf2_sha256$<iterations>$<salt>$<base64(hash)>
//
// 这里复刻其编码/校验,保证与 Django 共库期密码互认(ADR 共库迁移)。
// TODO(verify): Django 当前版本的默认迭代次数随版本递增;落地前请与现网 Django settings
// / 实际库内密文确认 iterations,避免新建用户密文与现网 hasher 不一致。
const (
	pbkdf2Algorithm  = "pbkdf2_sha256"
	pbkdf2Iterations = 600000 // Django 4.2 默认值;需按现网核对。
	pbkdf2SaltLen    = 12
	pbkdf2KeyLen     = 32
)

// hashPassword 生成 Django 兼容的 PBKDF2 密文。
func hashPassword(raw string) (string, error) {
	salt, err := randomSalt(pbkdf2SaltLen)
	if err != nil {
		return "", err
	}
	dk, err := pbkdf2.Key(sha256.New, raw, []byte(salt), pbkdf2Iterations, pbkdf2KeyLen)
	if err != nil {
		return "", err
	}
	enc := base64.StdEncoding.EncodeToString(dk)
	return fmt.Sprintf("%s$%d$%s$%s", pbkdf2Algorithm, pbkdf2Iterations, salt, enc), nil
}

// checkPassword 校验明文是否匹配 Django PBKDF2 密文(仅支持 pbkdf2_sha256)。
// TODO(verify): 现网可能存在其它 hasher(argon2/bcrypt)的历史密文,需补充分支或迁移。
func checkPassword(raw, encoded string) bool {
	parts := strings.Split(encoded, "$")
	if len(parts) != 4 || parts[0] != pbkdf2Algorithm {
		return false
	}
	iter, err := strconv.Atoi(parts[1])
	if err != nil {
		return false
	}
	salt := parts[2]
	want, err := base64.StdEncoding.DecodeString(parts[3])
	if err != nil {
		return false
	}
	got, err := pbkdf2.Key(sha256.New, raw, []byte(salt), iter, len(want))
	if err != nil {
		return false
	}
	return subtle.ConstantTimeCompare(got, want) == 1
}

// randomSalt 生成 Django 风格的字母数字盐。
func randomSalt(n int) (string, error) {
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	for i := range b {
		b[i] = charset[int(b[i])%len(charset)]
	}
	return string(b), nil
}
