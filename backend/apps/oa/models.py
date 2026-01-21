
# Import models from archive
from .archive import ArchiveCategory, Archive, ArchiveBorrow, ArchiveTransfer, ArchiveDestruction

# Import models from electronic_signature
from .electronic_signature import SignatureSeal, SignatureDocument, SignatureParticipant, SignatureLog

# Import models from vehicle
from .vehicle import Vehicle, VehicleRequest, VehicleMaintenance

# Import models from asset
from .asset import OAAssetCategory, Asset, AssetBorrow, OAAssetTransfer, AssetMaintenance
# Aliases
AssetCategory = OAAssetCategory
AssetTransfer = OAAssetTransfer

# Import models from attendance_device
from .attendance_device import (
    AttendanceDevice, DeviceUserMapping, DeviceAttendanceLog, DeviceSyncLog
)
