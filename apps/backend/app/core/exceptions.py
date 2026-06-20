class AppError(Exception):
    status_code = 500
    error_code = "INTERNAL_ERROR"

    def __init__(self, message: str, *, error_code: str | None = None):
        self.message = message
        if error_code:
            self.error_code = error_code
        super().__init__(message)


class ValidationError(AppError):
    status_code = 400
    error_code = "VALIDATION_ERROR"


class UnauthorizedError(AppError):
    status_code = 401
    error_code = "UNAUTHORIZED"


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    error_code = "CONFLICT"


class PayloadTooLargeError(AppError):
    status_code = 413
    error_code = "PAYLOAD_TOO_LARGE"


class ExternalServiceError(AppError):
    status_code = 502
    error_code = "EXTERNAL_SERVICE_ERROR"


class ServiceUnavailableError(AppError):
    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"


class UserAlreadyExistsError(ConflictError):
    error_code = "USER_ALREADY_EXISTS"


class DocumentNotFoundError(NotFoundError):
    error_code = "DOCUMENT_NOT_FOUND"


class UnsupportedFileTypeError(ValidationError):
    error_code = "UNSUPPORTED_FILE_TYPE"


class DocumentTooLargeError(PayloadTooLargeError):
    error_code = "DOCUMENT_TOO_LARGE"


class StorageError(ExternalServiceError):
    error_code = "STORAGE_ERROR"


class DocumentParsingError(ValidationError):
    error_code = "DOCUMENT_PARSING_ERROR"


class EmbeddingServiceError(ExternalServiceError):
    error_code = "EMBEDDING_SERVICE_ERROR"


class VectorStoreError(ExternalServiceError):
    error_code = "VECTOR_STORE_ERROR"


class LLMServiceError(ExternalServiceError):
    error_code = "LLM_SERVICE_ERROR"
