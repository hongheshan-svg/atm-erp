package oa

import (
	"database/sql/driver"
	"encoding/json"
	"errors"
	"fmt"
)

// JSONList 映射 Django models.JSONField(default=list),在 PostgreSQL 落到 jsonb。
// 用于 attachments / keywords / passenger_names 等“列表型” JSON 列。
type JSONList []any

// Value 实现 driver.Valuer:nil/空切片写入 "[]",保持与 Django 默认值一致。
func (l JSONList) Value() (driver.Value, error) {
	if l == nil {
		return "[]", nil
	}
	b, err := json.Marshal(l)
	if err != nil {
		return nil, err
	}
	return string(b), nil
}

// Scan 实现 sql.Scanner:兼容 []byte / string 两种驱动返回。
func (l *JSONList) Scan(src any) error {
	if src == nil {
		*l = JSONList{}
		return nil
	}
	var b []byte
	switch v := src.(type) {
	case []byte:
		b = v
	case string:
		b = []byte(v)
	default:
		return fmt.Errorf("oa: 无法将 %T 扫描为 JSONList", src)
	}
	if len(b) == 0 {
		*l = JSONList{}
		return nil
	}
	return errors.Join(json.Unmarshal(b, l))
}
