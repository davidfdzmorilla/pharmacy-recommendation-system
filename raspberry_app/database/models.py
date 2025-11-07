"""
Data models for Pharmacy Recommendation System.
Defines dataclasses for database entities with conversion methods.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any
import sqlite3


@dataclass
class Product:
    """Pharmaceutical product model."""

    ean: str
    name: str
    price: float
    category: str
    active_ingredient: Optional[str] = None
    description: Optional[str] = None
    stock: int = 0
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "Product":
        """
        Create Product instance from database row.

        Args:
            row: sqlite3.Row from database query

        Returns:
            Product: New Product instance
        """
        return cls(
            id=row["id"],
            ean=row["ean"],
            name=row["name"],
            price=row["price"],
            category=row["category"],
            active_ingredient=row["active_ingredient"],
            description=row["description"],
            stock=row["stock"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for API responses.

        Returns:
            dict: Product data as dictionary
        """
        data = asdict(self)
        # Convert datetime objects to ISO format strings
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            data["updated_at"] = self.updated_at.isoformat()
        return data

    def __str__(self) -> str:
        """String representation for logging."""
        return f"Product({self.ean}, {self.name}, €{self.price:.2f})"


@dataclass
class Sale:
    """Sales transaction model."""

    total: float
    items_count: int
    id: Optional[int] = None
    completed_at: Optional[datetime] = None

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "Sale":
        """Create Sale instance from database row."""
        return cls(
            id=row["id"],
            total=row["total"],
            items_count=row["items_count"],
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        if self.completed_at:
            data["completed_at"] = self.completed_at.isoformat()
        return data

    def __str__(self) -> str:
        """String representation."""
        return f"Sale({self.id}, €{self.total:.2f}, {self.items_count} items)"


@dataclass
class SaleItem:
    """Individual item in a sale transaction."""

    sale_id: int
    product_id: int
    quantity: int
    unit_price: float
    subtotal: float
    id: Optional[int] = None

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "SaleItem":
        """Create SaleItem instance from database row."""
        return cls(
            id=row["id"],
            sale_id=row["sale_id"],
            product_id=row["product_id"],
            quantity=row["quantity"],
            unit_price=row["unit_price"],
            subtotal=row["subtotal"]
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def __str__(self) -> str:
        """String representation."""
        return f"SaleItem(product_id={self.product_id}, qty={self.quantity}, €{self.subtotal:.2f})"


@dataclass
class RecommendationCache:
    """Cached recommendation entry."""

    cart_hash: str
    recommendations: str  # JSON string
    expires_at: datetime
    hit_count: int = 0
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "RecommendationCache":
        """Create RecommendationCache instance from database row."""
        return cls(
            id=row["id"],
            cart_hash=row["cart_hash"],
            recommendations=row["recommendations"],
            hit_count=row["hit_count"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            last_accessed_at=datetime.fromisoformat(row["last_accessed_at"]) if row["last_accessed_at"] else None,
            expires_at=datetime.fromisoformat(row["expires_at"])
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        if self.last_accessed_at:
            data["last_accessed_at"] = self.last_accessed_at.isoformat()
        if self.expires_at:
            data["expires_at"] = self.expires_at.isoformat()
        return data

    def __str__(self) -> str:
        """String representation."""
        return f"Cache({self.cart_hash[:8]}..., hits={self.hit_count})"


@dataclass
class APILog:
    """API call log entry."""

    request_type: str
    success: bool
    cart_items: Optional[int] = None
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "APILog":
        """Create APILog instance from database row."""
        return cls(
            id=row["id"],
            request_type=row["request_type"],
            cart_items=row["cart_items"],
            response_time_ms=row["response_time_ms"],
            success=bool(row["success"]),
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        return data

    def __str__(self) -> str:
        """String representation."""
        status = "✓" if self.success else "✗"
        return f"APILog({status} {self.request_type}, {self.response_time_ms}ms)"
