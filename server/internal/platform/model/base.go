// Package model 提供 BaseModel,复刻 Django apps.core.models.BaseModel:
// 时间戳 + 操作人 + 软删除,并保证与 Django 共库期软删除互认(ADR-006)。
package model

import (
	"context"
	"time"

	"gorm.io/gorm"
)

type ctxKey string

const userIDKey ctxKey = "erp_user_id"

// WithUserID 把当前操作人写入 ctx,供 GORM 钩子注入 created_by/updated_by。
func WithUserID(ctx context.Context, id uint64) context.Context {
	return context.WithValue(ctx, userIDKey, id)
}

func UserIDFrom(ctx context.Context) (uint64, bool) {
	v, ok := ctx.Value(userIDKey).(uint64)
	return v, ok
}

// Base 内嵌进各业务 struct。PK 用 uint64 对齐 Django BigAutoField。
type Base struct {
	ID        uint64         `gorm:"primaryKey;column:id" json:"id"`
	CreatedAt time.Time      `gorm:"column:created_at" json:"created_at"`
	UpdatedAt time.Time      `gorm:"column:updated_at" json:"updated_at"`
	CreatedBy *uint64        `gorm:"column:created_by" json:"created_by,omitempty"`
	UpdatedBy *uint64        `gorm:"column:updated_by" json:"updated_by,omitempty"`
	IsDeleted bool           `gorm:"column:is_deleted;index" json:"is_deleted"`
	DeletedAt gorm.DeletedAt `gorm:"column:deleted_at;index" json:"-"`
}

// BeforeCreate 注入操作人。
func (b *Base) BeforeCreate(tx *gorm.DB) error {
	if uid, ok := UserIDFrom(tx.Statement.Context); ok {
		if b.CreatedBy == nil {
			b.CreatedBy = &uid
		}
		b.UpdatedBy = &uid
	}
	return nil
}

// BeforeUpdate 注入更新人。
func (b *Base) BeforeUpdate(tx *gorm.DB) error {
	if uid, ok := UserIDFrom(tx.Statement.Context); ok {
		b.UpdatedBy = &uid
	}
	return nil
}

// BeforeDelete 在软删除的 UPDATE 中同步写入 is_deleted=true(与 Django soft_delete 互认)。
// gorm.DeletedAt 默认只写 deleted_at;此处用 SetColumn 把 is_deleted 一并纳入更新。
func (b *Base) BeforeDelete(tx *gorm.DB) error {
	tx.Statement.SetColumn("is_deleted", true)
	if uid, ok := UserIDFrom(tx.Statement.Context); ok {
		tx.Statement.SetColumn("updated_by", uid)
	}
	return nil
}
