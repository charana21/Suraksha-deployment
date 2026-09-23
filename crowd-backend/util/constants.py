# utils/constants.py

# Common error messages
DATABASE_UNAVAILABLE = "Database unavailable"
DATABASE_NOT_CONNECTED= "Database not connected"
ROLE_NOT_FOUND = "Role not found"
USER_NOT_FOUND = "User not found"
CAMERA_NOT_FOUND = "Camera not found"
ZONE_NOT_FOUND = "Zone not found"
NO_VALID_RECORDS_FOUND = "No valid records found"

# Common Pydantic field descriptions (models/schemas.py)
DESC_ZONE_NAME = "Human-readable zone name"
DESC_AGGREGATION_TIMESTAMP = "Aggregation timestamp"
DESC_OVERALL_DENSITY_STATUS = "Overall density status"
DESC_RENDERING_ORDER = "Rendering order"
DESC_ISO8601_TIMESTAMP = "ISO 8601 timestamp"
DESC_CAMERA_ID = "Camera identifier"
DESC_PHYSICAL_ZONE_TYPE = "Physical zone type"
DESC_STATION_ID = "Station identifier (e.g. 'HYB')"

ERR_INVALID_MODULE_ID = "Invalid module id"
INVALID_ROLEID = "Invalid role id"
USER_ALREADY_EXISTS = "User already exists"
INVALID_USER_ID = "Invalid user id"
WHATSAPP_PREFIX = "whatsapp:"
FILE_MUST_BE_EXCEL_FORMAT = "File must be Excel format"
EXCEL_FILE_EXTENSIONS = (".xlsx", ".xls")
THRESHOLD_EXCEEDED = "Threshold exceeded"