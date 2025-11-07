"""
Unit tests for barcode module.
Tests EAN-13 validation, formatting, and barcode processing.
"""
import pytest
from raspberry_app.barcode.validator import (
    calculate_ean13_checksum,
    validate_ean13,
    format_ean13,
    is_spanish_ean,
    get_ean_country_code,
    BarcodeValidator
)


# ==================== CHECKSUM TESTS ====================

def test_calculate_checksum():
    """Test EAN-13 checksum calculation."""
    # Known valid checksums
    test_cases = [
        ("847000123456", 8),  # Spanish product
        ("590123412345", 7),  # Polish product
        ("400638133393", 1),  # German product
        ("012345678901", 2),  # UPC-A compatible
    ]

    for ean_12, expected_checksum in test_cases:
        calculated = calculate_ean13_checksum(ean_12)
        assert calculated == expected_checksum, f"Checksum for {ean_12} should be {expected_checksum}, got {calculated}"


def test_calculate_checksum_invalid_length():
    """Test that checksum calculation fails with invalid length."""
    with pytest.raises(ValueError):
        calculate_ean13_checksum("12345")  # Too short

    with pytest.raises(ValueError):
        calculate_ean13_checksum("12345678901234")  # Too long


# ==================== VALIDATION TESTS ====================

def test_validate_valid_eans():
    """Test validation of known valid EAN-13 codes."""
    valid_eans = [
        "8470001234568",  # Spanish
        "5901234123457",  # Polish
        "4006381333931",  # German
        "0123456789012",  # UPC-A
        "9780201379624",  # ISBN-13
    ]

    for ean in valid_eans:
        assert validate_ean13(ean), f"EAN {ean} should be valid"


def test_validate_invalid_eans():
    """Test validation rejects invalid EAN-13 codes."""
    invalid_eans = [
        "1234567890123",  # Invalid checksum
        "847000123456",   # Too short (12 digits)
        "84700012345678", # Too long (14 digits)
        "84700012345AB",  # Contains letters
        "8470 0012 3456", # Contains spaces (not stripped)
        "",               # Empty
        "8470001234567",  # Wrong checksum (should be 8)
    ]

    for ean in invalid_eans:
        assert not validate_ean13(ean), f"EAN {ean} should be invalid"


def test_validate_whitespace_handling():
    """Test that validation handles whitespace."""
    # With leading/trailing whitespace
    assert validate_ean13(" 8470001234568 ")
    assert validate_ean13("\t8470001234568\n")


# ==================== FORMATTING TESTS ====================

def test_format_ean13():
    """Test EAN-13 formatting."""
    # Valid EAN with whitespace
    assert format_ean13(" 8470001234568 ") == "8470001234568"

    # Valid EAN with hyphens
    assert format_ean13("847-0001-234-568") == "8470001234568"

    # Invalid EAN
    assert format_ean13("1234567890123") is None
    assert format_ean13("invalid") is None


# ==================== COUNTRY CODE TESTS ====================

def test_is_spanish_ean():
    """Test Spanish EAN detection."""
    # Spanish EANs (start with 84)
    assert is_spanish_ean("8470001234568")
    assert is_spanish_ean("8400012345670")

    # Non-Spanish EANs
    assert not is_spanish_ean("5901234123457")  # Polish
    assert not is_spanish_ean("4006381333931")  # German


def test_get_country_code():
    """Test country code extraction."""
    test_cases = [
        ("8470001234568", "84"),   # Spain/Portugal
        ("5901234123457", "590"),  # Poland (3-digit)
        ("4006381333931", "40"),   # Germany
        ("0123456789012", "01"),   # USA/Canada
        ("9780201379624", "978"),  # ISBN (3-digit)
    ]

    for ean, expected_code in test_cases:
        code = get_ean_country_code(ean)
        assert code == expected_code, f"Country code for {ean} should be {expected_code}, got {code}"


def test_get_country_code_invalid():
    """Test country code extraction with invalid EAN."""
    assert get_ean_country_code("1234567890123") is None
    assert get_ean_country_code("invalid") is None


# ==================== BARCODE VALIDATOR CLASS TESTS ====================

def test_validator_default():
    """Test BarcodeValidator with default settings."""
    validator = BarcodeValidator()

    # Valid EAN-13
    assert validator.validate("8470001234568")

    # Invalid
    assert not validator.validate("1234567890123")


def test_validator_require_spanish():
    """Test BarcodeValidator with Spanish requirement."""
    validator = BarcodeValidator(require_spanish=True)

    # Spanish EAN
    assert validator.validate("8470001234568")

    # Non-Spanish valid EAN
    assert not validator.validate("5901234123457")


def test_validator_length_constraints():
    """Test BarcodeValidator with custom length constraints."""
    # Allow only 13 digits (default)
    validator = BarcodeValidator(min_length=13, max_length=13)
    assert validator.validate("8470001234568")
    assert not validator.validate("84700012345")  # Too short


def test_validator_format():
    """Test BarcodeValidator format method."""
    validator = BarcodeValidator()

    # Valid EAN
    formatted = validator.format(" 8470001234568 ")
    assert formatted == "8470001234568"

    # Invalid EAN
    assert validator.format("1234567890123") is None


def test_validator_format_spanish_only():
    """Test format with Spanish requirement."""
    validator = BarcodeValidator(require_spanish=True)

    # Spanish EAN
    assert validator.format("8470001234568") == "8470001234568"

    # Non-Spanish EAN
    assert validator.format("5901234123457") is None


# ==================== EDGE CASES ====================

def test_all_zeros():
    """Test EAN with all zeros."""
    # All zeros except checksum
    ean = "0000000000000"
    # Should be valid if checksum is correct
    checksum = calculate_ean13_checksum(ean[:12])
    full_ean = ean[:12] + str(checksum)
    assert validate_ean13(full_ean)


def test_all_nines():
    """Test EAN with all nines."""
    # All nines
    ean = "9999999999999"
    # May or may not be valid depending on checksum
    # Just test it doesn't crash
    result = validate_ean13(ean)
    assert isinstance(result, bool)


def test_unicode_handling():
    """Test handling of unicode characters."""
    # Should reject non-ASCII digits
    assert not validate_ean13("８４７０００１２３４５６７")  # Full-width digits


# ==================== INTEGRATION TESTS ====================

def test_full_workflow():
    """Test complete workflow: format, validate, extract country."""
    raw_input = " 8470-001-234-568 "

    # Format
    formatted = format_ean13(raw_input)
    assert formatted == "8470001234568"

    # Validate
    assert validate_ean13(formatted)

    # Check Spanish
    assert is_spanish_ean(formatted)

    # Get country code
    assert get_ean_country_code(formatted) == "84"


def test_validator_workflow():
    """Test BarcodeValidator complete workflow."""
    validator = BarcodeValidator(require_spanish=True)

    # Valid Spanish barcode
    barcode = " 8470001234568 "

    # Validate
    assert validator.validate(barcode)

    # Format
    formatted = validator.format(barcode)
    assert formatted == "8470001234568"


# ==================== REAL-WORLD EAN TESTS ====================

def test_real_product_eans():
    """Test with real pharmaceutical product EANs."""
    # These should all be valid Spanish EANs (with correct checksums)
    real_eans = [
        "8470001234568",  # Ibuprofeno
        "8470002345676",  # Omeprazol
        "8470003456784",  # Redoxon
    ]

    for ean in real_eans:
        assert validate_ean13(ean), f"Real EAN {ean} should be valid"
        assert is_spanish_ean(ean), f"EAN {ean} should be Spanish"


# ==================== PERFORMANCE TESTS ====================

def test_validation_performance():
    """Test validation performance with many barcodes."""
    import time

    validator = BarcodeValidator()
    test_ean = "8470001234568"

    start = time.time()
    for _ in range(10000):
        validator.validate(test_ean)
    elapsed = time.time() - start

    # Should validate 10k barcodes in less than 1 second
    assert elapsed < 1.0, f"Validation too slow: {elapsed:.3f}s for 10k validations"
