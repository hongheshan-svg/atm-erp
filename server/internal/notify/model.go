// Package notify 提供站内信(系统通知)最小实现:落库 + 我的通知/未读数/标记已读。
// 对齐 Django apps.core SystemNotification / db_table=system_notification(plain 模型,无 BaseModel)。
package notify

import "time"

// 通知类型(对齐 Django TYPE_CHOICES)。
const (
	TypeInfo    = "INFO"
	TypeWarning = "WARNING"
	TypeError   = "ERROR"
	TypeSuccess = "SUCCESS"
)

// Notification 系统通知。注意:真表无 created_by/updated_at/软删除列,故不内嵌 model.Base。
type Notification struct {
	ID        uint64     `gorm:"primaryKey;column:id" json:"id"`
	UserID    uint64     `gorm:"column:user_id;index" json:"user_id"`
	Type      string     `gorm:"column:type;size:20;default:INFO" json:"type"`
	Title     string     `gorm:"column:title;size:200" json:"title"`
	Message   string     `gorm:"column:message;type:text" json:"message"`
	IsRead    bool       `gorm:"column:is_read;default:false" json:"is_read"`
	CreatedAt time.Time  `gorm:"column:created_at" json:"created_at"`
	ReadAt    *time.Time `gorm:"column:read_at" json:"read_at"`
}

func (Notification) TableName() string { return "system_notification" }
