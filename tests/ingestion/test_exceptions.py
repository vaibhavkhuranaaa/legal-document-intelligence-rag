import pytest

from legal_rag.ingestion.exceptions import (
    AzureServiceError,
    CorruptedDocumentError,
    EmptyExtractionError,
    ExtractionError,
    InfrastructureError,
    IngestionError,
    SchemaValidationError,
    SemanticValidationError,
    StorageError,
    UnsupportedFormatError,
    UserInputError,
    ValidationFailedError,
)


@pytest.mark.parametrize(
    ("exc_type", "expected_base"),
    [
        (UserInputError, IngestionError),
        (UnsupportedFormatError, UserInputError),
        (CorruptedDocumentError, UserInputError),
        (InfrastructureError, IngestionError),
        (AzureServiceError, InfrastructureError),
        (StorageError, InfrastructureError),
        (ExtractionError, IngestionError),
        (EmptyExtractionError, ExtractionError),
        (ValidationFailedError, IngestionError),
        (SchemaValidationError, ValidationFailedError),
        (SemanticValidationError, ValidationFailedError),
    ],
)
def test_exception_hierarchy(exc_type: type[IngestionError], expected_base: type) -> None:
    assert issubclass(exc_type, expected_base)


def test_context_defaults_to_empty_dict() -> None:
    error = IngestionError("something went wrong")

    assert error.message == "something went wrong"
    assert error.context == {}


def test_context_is_preserved() -> None:
    error = CorruptedDocumentError(
        "could not open PDF", context={"file_path": "data/raw/broken.pdf"}
    )

    assert error.context == {"file_path": "data/raw/broken.pdf"}
    assert str(error) == "could not open PDF"
