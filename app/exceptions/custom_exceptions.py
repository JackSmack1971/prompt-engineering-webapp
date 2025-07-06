from fastapi import status
from pydantic import BaseModel
from typing import Optional, Any, Dict

class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None

class APIException(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Optional[Any] = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)

class AuthError(APIException):
    def __init__(self, message: str = "Authentication failed", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTHENTICATION_ERROR",
            message=message,
            details=details
        )

class ForbiddenError(APIException):
    def __init__(self, message: str = "Forbidden", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_ERROR",
            message=message,
            details=details
        )

class NotFoundError(APIException):
    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND_ERROR",
            message=message,
            details=details
        )

class BadRequestError(APIException):
    def __init__(self, message: str = "Bad request", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BAD_REQUEST_ERROR",
            message=message,
            details=details
        )

class InternalServerError(APIException):
    def __init__(self, message: str = "Internal server error", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            message=message,
            details=details
        )