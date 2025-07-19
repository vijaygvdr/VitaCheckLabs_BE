from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, Boolean, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class LabTest(Base):
    """Lab test model for managing available medical tests"""
    
    __tablename__ = "lab_tests"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Test identification
    name = Column(String(200), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)  # Test code like "CBC", "LFT", etc.
    description = Column(Text, nullable=True)
    
    # Test categorization
    category = Column(String(100), nullable=False, index=True)  # e.g., "Blood Test", "Urine Test", "Imaging"
    sub_category = Column(String(100), nullable=True)  # e.g., "Liver Function", "Kidney Function"
    
    # Test details
    sample_type = Column(String(50), nullable=True)  # e.g., "Blood", "Urine", "Saliva"
    requirements = Column(Text, nullable=True)  # Pre-test requirements like fasting
    procedure = Column(Text, nullable=True)  # How the test is performed
    
    # Pricing and timing
    price = Column(Numeric(10, 2), nullable=False, index=True)  # Test price
    duration_minutes = Column(Integer, nullable=True)  # Time to complete test
    report_delivery_hours = Column(Integer, nullable=True)  # Time to deliver results
    
    # Test availability and status
    is_active = Column(Boolean, default=True, nullable=False)
    is_home_collection_available = Column(Boolean, default=False, nullable=False)
    minimum_age = Column(Integer, nullable=True)  # Minimum age for the test
    maximum_age = Column(Integer, nullable=True)  # Maximum age for the test
    
    # Reference ranges and normal values
    reference_ranges = Column(Text, nullable=True)  # JSON string with normal ranges
    units = Column(String(50), nullable=True)  # Measurement units
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    reports = relationship("Report", back_populates="lab_test")
    bookings = relationship("Booking", back_populates="test")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_labtest_category_active', 'category', 'is_active'),
        Index('idx_labtest_price_active', 'price', 'is_active'),
        Index('idx_labtest_name_category', 'name', 'category'),
        Index('idx_labtest_code_active', 'code', 'is_active'),
        Index('idx_labtest_sample_type', 'sample_type'),
    )
    
    def __repr__(self):
        return f"<LabTest(id={self.id}, name='{self.name}', code='{self.code}', category='{self.category}', price={self.price})>"
    
    @property
    def display_name(self):
        """Return formatted display name"""
        return f"{self.name} ({self.code})"
    
    @property
    def price_formatted(self):
        """Return formatted price"""
        return f"₹{self.price:.2f}"
    
    def is_available_for_age(self, age):
        """Check if test is available for given age"""
        if self.minimum_age and age < self.minimum_age:
            return False
        if self.maximum_age and age > self.maximum_age:
            return False
        return True
    
    def get_estimated_completion_time(self):
        """Get estimated time for test completion and report delivery"""
        test_time = self.duration_minutes or 30  # Default 30 minutes
        report_time = (self.report_delivery_hours or 24) * 60  # Convert to minutes
        return test_time + report_time