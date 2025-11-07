"""
EAN-13 barcode validation module.
Validates barcode format and checksum according to GS1 standards.
"""
from typing import Optional


def calculate_ean13_checksum(ean: str) -> int:
    """
    Calculate EAN-13 checksum digit.

    The checksum is calculated by:
    1. Sum odd-positioned digits (1st, 3rd, 5th, etc.)
    2. Sum even-positioned digits and multiply by 3
    3. Add both sums
    4. Subtract from nearest equal or higher multiple of 10

    Args:
        ean: 12-digit EAN code (without checksum)

    Returns:
        int: Checksum digit (0-9)

    Example:
        >>> calculate_ean13_checksum("847000123456")
        7
    """
    if len(ean) != 12:
        raise ValueError(f"EAN must be 12 digits for checksum calculation, got {len(ean)}")

    # Sum odd positions (1st, 3rd, 5th, etc.) - indices 0, 2, 4, ...
    odd_sum = sum(int(ean[i]) for i in range(0, 12, 2))

    # Sum even positions (2nd, 4th, 6th, etc.) - indices 1, 3, 5, ...
    even_sum = sum(int(ean[i]) for i in range(1, 12, 2))

    # Calculate checksum
    total = odd_sum + (even_sum * 3)
    checksum = (10 - (total % 10)) % 10

    return checksum


def validate_ean13(ean: str) -> bool:
    """
    Validate EAN-13 barcode format and checksum.

    Args:
        ean: EAN-13 barcode string

    Returns:
        bool: True if valid, False otherwise

    Example:
        >>> validate_ean13("8470001234567")
        True
        >>> validate_ean13("1234567890123")
        False
    """
    # Remove whitespace
    ean = ean.strip()

    # Check length
    if len(ean) != 13:
        return False

    # Check all digits
    if not ean.isdigit():
        return False

    # Extract checksum digit
    provided_checksum = int(ean[-1])

    # Calculate expected checksum
    expected_checksum = calculate_ean13_checksum(ean[:12])

    # Validate
    return provided_checksum == expected_checksum


def format_ean13(ean: str) -> Optional[str]:
    """
    Format and validate EAN-13 barcode.

    Args:
        ean: Raw barcode input

    Returns:
        str: Formatted EAN-13 if valid, None otherwise

    Example:
        >>> format_ean13(" 8470001234567 ")
        "8470001234567"
        >>> format_ean13("invalid")
        None
    """
    # Clean input
    ean = ean.strip().replace("-", "").replace(" ", "")

    # Validate
    if validate_ean13(ean):
        return ean

    return None


def is_spanish_ean(ean: str) -> bool:
    """
    Check if EAN-13 is a Spanish product (starts with 84).

    Args:
        ean: EAN-13 barcode

    Returns:
        bool: True if Spanish product code

    Example:
        >>> is_spanish_ean("8470001234567")
        True
        >>> is_spanish_ean("5901234123457")
        False
    """
    if not validate_ean13(ean):
        return False

    return ean.startswith("84")


def get_ean_country_code(ean: str) -> Optional[str]:
    """
    Extract country/region code from EAN-13.

    Args:
        ean: EAN-13 barcode

    Returns:
        str: 2-3 digit country code, None if invalid

    Example:
        >>> get_ean_country_code("8470001234567")
        "84"
        >>> get_ean_country_code("5901234123457")
        "590"
    """
    if not validate_ean13(ean):
        return None

    # Spain and Portugal use 84
    if ean.startswith("84"):
        return "84"

    # Most countries use 2-digit codes
    # Some use 3-digit codes (590-599, 978-979, etc.)
    prefix3 = ean[:3]
    if prefix3 in ["590", "591", "592", "593", "594", "595", "596", "597", "598", "599",
                   "978", "979"]:
        return prefix3

    # Default to 2-digit
    return ean[:2]


class BarcodeValidator:
    """
    Barcode validation class with configurable settings.

    Example:
        >>> validator = BarcodeValidator(require_spanish=True)
        >>> validator.validate("8470001234567")
        True
        >>> validator.validate("5901234123457")
        False
    """

    def __init__(self, require_spanish: bool = False, min_length: int = 13, max_length: int = 13):
        """
        Initialize validator.

        Args:
            require_spanish: Only accept Spanish EAN codes (84)
            min_length: Minimum barcode length
            max_length: Maximum barcode length
        """
        self.require_spanish = require_spanish
        self.min_length = min_length
        self.max_length = max_length

    def validate(self, ean: str) -> bool:
        """
        Validate barcode according to configured rules.

        Args:
            ean: Barcode string

        Returns:
            bool: True if valid according to rules
        """
        # Clean input
        ean = ean.strip()

        # Length check
        if not (self.min_length <= len(ean) <= self.max_length):
            return False

        # EAN-13 validation
        if not validate_ean13(ean):
            return False

        # Spanish requirement
        if self.require_spanish and not is_spanish_ean(ean):
            return False

        return True

    def format(self, ean: str) -> Optional[str]:
        """Format barcode if valid."""
        if self.validate(ean):
            return format_ean13(ean)
        return None


# Example usage and testing
if __name__ == "__main__":
    # Test valid EAN-13
    test_eans = [
        "8470001234567",  # Spanish
        "5901234123457",  # Polish
        "4006381333931",  # German
    ]

    print("Testing EAN-13 validation:\n")
    for ean in test_eans:
        is_valid = validate_ean13(ean)
        is_spanish = is_spanish_ean(ean)
        country = get_ean_country_code(ean)

        print(f"EAN: {ean}")
        print(f"  Valid: {is_valid}")
        print(f"  Spanish: {is_spanish}")
        print(f"  Country Code: {country}")
        print()

    # Test checksum calculation
    print("\nChecksum calculation examples:")
    for ean in ["847000123456", "590123412345"]:
        checksum = calculate_ean13_checksum(ean)
        full_ean = ean + str(checksum)
        print(f"{ean} + {checksum} = {full_ean} (valid: {validate_ean13(full_ean)})")
