from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class Company(Base):
    """Company model for managing organization information and settings"""
    
    __tablename__ = "company"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Basic company information
    name = Column(String(200), nullable=False)
    legal_name = Column(String(300), nullable=True)  # Legal business name
    registration_number = Column(String(100), nullable=True, unique=True)  # Business registration
    tax_id = Column(String(50), nullable=True)  # GST/Tax identification
    
    # Company description and mission
    description = Column(Text, nullable=True)
    mission_statement = Column(Text, nullable=True)
    vision_statement = Column(Text, nullable=True)
    
    # Contact information
    email = Column(String(255), nullable=True)
    phone_primary = Column(String(20), nullable=True)
    phone_secondary = Column(String(20), nullable=True)
    website = Column(String(255), nullable=True)
    
    # Address information
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), default="India", nullable=False)
    
    # Business information
    established_year = Column(Integer, nullable=True)
    license_number = Column(String(100), nullable=True)  # Medical/Lab license
    accreditation = Column(String(200), nullable=True)   # NABL, ISO certifications
    
    # Services and specializations
    services = Column(JSON, nullable=True)  # List of services offered
    specializations = Column(JSON, nullable=True)  # Areas of expertise
    certifications = Column(JSON, nullable=True)  # Certifications and awards
    
    # Operating hours
    operating_hours = Column(JSON, nullable=True)  # Weekly schedule
    emergency_contact = Column(String(20), nullable=True)
    is_24x7 = Column(Boolean, default=False, nullable=False)
    
    # Social media and online presence
    social_media_links = Column(JSON, nullable=True)  # Facebook, Twitter, LinkedIn etc.
    google_maps_link = Column(String(500), nullable=True)
    
    # Business settings
    is_active = Column(Boolean, default=True, nullable=False)
    accepts_home_collection = Column(Boolean, default=True, nullable=False)
    home_collection_radius_km = Column(Integer, default=25, nullable=True)
    minimum_order_amount = Column(Integer, default=0, nullable=False)  # In paisa
    
    # Quality and compliance
    quality_policy = Column(Text, nullable=True)
    privacy_policy = Column(Text, nullable=True)
    terms_of_service = Column(Text, nullable=True)
    
    # Branding
    logo_url = Column(String(500), nullable=True)  # S3 URL for logo
    brand_colors = Column(JSON, nullable=True)  # Primary, secondary colors
    tagline = Column(String(200), nullable=True)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Company(id={self.id}, name='{self.name}', city='{self.city}')>"
    
    @property
    def full_address(self):
        """Return formatted full address"""
        address_parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.state,
            self.postal_code,
            self.country
        ]
        return ", ".join([part for part in address_parts if part])
    
    @property
    def primary_contact(self):
        """Return primary contact information"""
        return {
            "email": self.email,
            "phone": self.phone_primary,
            "address": self.full_address
        }
    
    def get_service_list(self):
        """Return list of services offered"""
        if self.services and isinstance(self.services, list):
            return self.services
        return []
    
    def add_service(self, service_name):
        """Add a new service to the list"""
        services = self.get_service_list()
        if service_name not in services:
            services.append(service_name)
            self.services = services
    
    def remove_service(self, service_name):
        """Remove a service from the list"""
        services = self.get_service_list()
        if service_name in services:
            services.remove(service_name)
            self.services = services
    
    def is_within_service_area(self, distance_km):
        """Check if location is within service area"""
        if not self.accepts_home_collection:
            return False
        return distance_km <= (self.home_collection_radius_km or 25)
    
    def get_operating_hours_today(self, day_of_week):
        """Get operating hours for specific day (0=Monday, 6=Sunday)"""
        if not self.operating_hours:
            return None
        
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if 0 <= day_of_week <= 6:
            day_name = days[day_of_week]
            return self.operating_hours.get(day_name)
        return None


class MessageStatus(enum.Enum):
    """Contact message status"""
    NEW = "new"
    READ = "read"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ContactMessage(Base):
    """Contact message model for customer inquiries and feedback"""
    
    __tablename__ = "contact_messages"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Contact information
    full_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    
    # Message details
    subject = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    inquiry_type = Column(String(50), nullable=True)  # general, support, complaint, feedback
    
    # Status tracking
    status = Column(Enum(MessageStatus), default=MessageStatus.NEW, nullable=False, index=True)
    priority = Column(String(20), default="normal", nullable=False)  # urgent, high, normal, low
    
    # Response tracking
    responded_at = Column(DateTime(timezone=True), nullable=True)
    response_message = Column(Text, nullable=True)
    responded_by = Column(String(100), nullable=True)  # Admin/staff who responded
    
    # Additional metadata
    source = Column(String(50), default="website", nullable=False)  # website, mobile_app, phone, email
    user_agent = Column(String(500), nullable=True)  # Browser/device info
    ip_address = Column(String(45), nullable=True)  # IPv4/IPv6 address
    
    # Follow-up
    follow_up_required = Column(Boolean, default=False, nullable=False)
    follow_up_date = Column(DateTime(timezone=True), nullable=True)
    internal_notes = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<ContactMessage(id={self.id}, email='{self.email}', subject='{self.subject[:30]}...', status='{self.status.value}')>"
    
    @property
    def is_urgent(self):
        """Check if message is urgent"""
        return self.priority in ["urgent", "high"]
    
    @property
    def response_time_hours(self):
        """Calculate response time in hours"""
        if self.responded_at and self.created_at:
            delta = self.responded_at - self.created_at
            return delta.total_seconds() / 3600
        return None
    
    def mark_as_read(self):
        """Mark message as read"""
        if self.status == MessageStatus.NEW:
            self.status = MessageStatus.READ
    
    def mark_as_resolved(self, response_message=None, responded_by=None):
        """Mark message as resolved with optional response"""
        self.status = MessageStatus.RESOLVED
        self.responded_at = func.now()
        if response_message:
            self.response_message = response_message
        if responded_by:
            self.responded_by = responded_by