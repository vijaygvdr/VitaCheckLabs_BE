"""Add core database models: User, LabTest, Report, Company

Revision ID: 670c8942a3c0
Revises: 
Create Date: 2025-07-12 15:51:03.730422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '670c8942a3c0'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE userRole AS ENUM ('admin', 'user', 'lab_technician')")
    op.execute("CREATE TYPE reportstatus AS ENUM ('pending', 'in_progress', 'completed', 'reviewed', 'delivered', 'cancelled')")
    
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('first_name', sa.String(length=50), nullable=True),
        sa.Column('last_name', sa.String(length=50), nullable=True),
        sa.Column('phone_number', sa.String(length=20), nullable=True),
        sa.Column('role', sa.Enum('admin', 'user', 'lab_technician', name='userrole'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_user_created_at', 'users', ['created_at'], unique=False)
    op.create_index('idx_user_email_active', 'users', ['email', 'is_active'], unique=False)
    op.create_index('idx_user_role', 'users', ['role'], unique=False)
    op.create_index('idx_user_username_active', 'users', ['username', 'is_active'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # Create lab_tests table
    op.create_table('lab_tests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('sub_category', sa.String(length=100), nullable=True),
        sa.Column('sample_type', sa.String(length=50), nullable=True),
        sa.Column('requirements', sa.Text(), nullable=True),
        sa.Column('procedure', sa.Text(), nullable=True),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('report_delivery_hours', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_home_collection_available', sa.Boolean(), nullable=False),
        sa.Column('minimum_age', sa.Integer(), nullable=True),
        sa.Column('maximum_age', sa.Integer(), nullable=True),
        sa.Column('reference_ranges', sa.Text(), nullable=True),
        sa.Column('units', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_labtest_category_active', 'lab_tests', ['category', 'is_active'], unique=False)
    op.create_index('idx_labtest_code_active', 'lab_tests', ['code', 'is_active'], unique=False)
    op.create_index('idx_labtest_name_category', 'lab_tests', ['name', 'category'], unique=False)
    op.create_index('idx_labtest_price_active', 'lab_tests', ['price', 'is_active'], unique=False)
    op.create_index('idx_labtest_sample_type', 'lab_tests', ['sample_type'], unique=False)
    op.create_index(op.f('ix_lab_tests_category'), 'lab_tests', ['category'], unique=False)
    op.create_index(op.f('ix_lab_tests_code'), 'lab_tests', ['code'], unique=True)
    op.create_index(op.f('ix_lab_tests_id'), 'lab_tests', ['id'], unique=False)
    op.create_index(op.f('ix_lab_tests_name'), 'lab_tests', ['name'], unique=False)
    op.create_index(op.f('ix_lab_tests_price'), 'lab_tests', ['price'], unique=False)

    # Create company table
    op.create_table('company',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('legal_name', sa.String(length=300), nullable=True),
        sa.Column('registration_number', sa.String(length=100), nullable=True),
        sa.Column('tax_id', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('mission_statement', sa.Text(), nullable=True),
        sa.Column('vision_statement', sa.Text(), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone_primary', sa.String(length=20), nullable=True),
        sa.Column('phone_secondary', sa.String(length=20), nullable=True),
        sa.Column('website', sa.String(length=255), nullable=True),
        sa.Column('address_line1', sa.String(length=255), nullable=True),
        sa.Column('address_line2', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('postal_code', sa.String(length=20), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=False),
        sa.Column('established_year', sa.Integer(), nullable=True),
        sa.Column('license_number', sa.String(length=100), nullable=True),
        sa.Column('accreditation', sa.String(length=200), nullable=True),
        sa.Column('services', sa.JSON(), nullable=True),
        sa.Column('specializations', sa.JSON(), nullable=True),
        sa.Column('certifications', sa.JSON(), nullable=True),
        sa.Column('operating_hours', sa.JSON(), nullable=True),
        sa.Column('emergency_contact', sa.String(length=20), nullable=True),
        sa.Column('is_24x7', sa.Boolean(), nullable=False),
        sa.Column('social_media_links', sa.JSON(), nullable=True),
        sa.Column('google_maps_link', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('accepts_home_collection', sa.Boolean(), nullable=False),
        sa.Column('home_collection_radius_km', sa.Integer(), nullable=True),
        sa.Column('minimum_order_amount', sa.Integer(), nullable=False),
        sa.Column('quality_policy', sa.Text(), nullable=True),
        sa.Column('privacy_policy', sa.Text(), nullable=True),
        sa.Column('terms_of_service', sa.Text(), nullable=True),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('brand_colors', sa.JSON(), nullable=True),
        sa.Column('tagline', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_company_id'), 'company', ['id'], unique=False)
    op.create_index(op.f('ix_company_registration_number'), 'company', ['registration_number'], unique=True)

    # Create reports table
    op.create_table('reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('lab_test_id', sa.Integer(), nullable=False),
        sa.Column('report_number', sa.String(length=50), nullable=False),
        sa.Column('status', sa.Enum('pending', 'in_progress', 'completed', 'reviewed', 'delivered', 'cancelled', name='reportstatus'), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sample_collected_by', sa.String(length=100), nullable=True),
        sa.Column('collection_location', sa.String(length=200), nullable=True),
        sa.Column('collection_notes', sa.Text(), nullable=True),
        sa.Column('results', sa.Text(), nullable=True),
        sa.Column('observations', sa.Text(), nullable=True),
        sa.Column('recommendations', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_original_name', sa.String(length=255), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_type', sa.String(length=50), nullable=True),
        sa.Column('is_shared', sa.Boolean(), nullable=False),
        sa.Column('shared_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('shared_with', sa.Text(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('verified_by', sa.String(length=100), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('amount_charged', sa.Integer(), nullable=True),
        sa.Column('payment_status', sa.String(length=20), nullable=False),
        sa.Column('payment_reference', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['lab_test_id'], ['lab_tests.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_report_labtest_status', 'reports', ['lab_test_id', 'status'], unique=False)
    op.create_index('idx_report_number', 'reports', ['report_number'], unique=False)
    op.create_index('idx_report_payment_status', 'reports', ['payment_status'], unique=False)
    op.create_index('idx_report_scheduled_at', 'reports', ['scheduled_at'], unique=False)
    op.create_index('idx_report_status_created', 'reports', ['status', 'created_at'], unique=False)
    op.create_index('idx_report_user_created', 'reports', ['user_id', 'created_at'], unique=False)
    op.create_index('idx_report_user_status', 'reports', ['user_id', 'status'], unique=False)
    op.create_index(op.f('ix_reports_id'), 'reports', ['id'], unique=False)
    op.create_index(op.f('ix_reports_lab_test_id'), 'reports', ['lab_test_id'], unique=False)
    op.create_index(op.f('ix_reports_report_number'), 'reports', ['report_number'], unique=True)
    op.create_index(op.f('ix_reports_status'), 'reports', ['status'], unique=False)
    op.create_index(op.f('ix_reports_user_id'), 'reports', ['user_id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_reports_user_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_status'), table_name='reports')
    op.drop_index(op.f('ix_reports_report_number'), table_name='reports')
    op.drop_index(op.f('ix_reports_lab_test_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_id'), table_name='reports')
    op.drop_index('idx_report_user_status', table_name='reports')
    op.drop_index('idx_report_user_created', table_name='reports')
    op.drop_index('idx_report_status_created', table_name='reports')
    op.drop_index('idx_report_scheduled_at', table_name='reports')
    op.drop_index('idx_report_payment_status', table_name='reports')
    op.drop_index('idx_report_number', table_name='reports')
    op.drop_index('idx_report_labtest_status', table_name='reports')
    op.drop_table('reports')
    
    op.drop_index(op.f('ix_company_registration_number'), table_name='company')
    op.drop_index(op.f('ix_company_id'), table_name='company')
    op.drop_table('company')
    
    op.drop_index(op.f('ix_lab_tests_price'), table_name='lab_tests')
    op.drop_index(op.f('ix_lab_tests_name'), table_name='lab_tests')
    op.drop_index(op.f('ix_lab_tests_id'), table_name='lab_tests')
    op.drop_index(op.f('ix_lab_tests_code'), table_name='lab_tests')
    op.drop_index(op.f('ix_lab_tests_category'), table_name='lab_tests')
    op.drop_index('idx_labtest_sample_type', table_name='lab_tests')
    op.drop_index('idx_labtest_price_active', table_name='lab_tests')
    op.drop_index('idx_labtest_name_category', table_name='lab_tests')
    op.drop_index('idx_labtest_code_active', table_name='lab_tests')
    op.drop_index('idx_labtest_category_active', table_name='lab_tests')
    op.drop_table('lab_tests')
    
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index('idx_user_username_active', table_name='users')
    op.drop_index('idx_user_role', table_name='users')
    op.drop_index('idx_user_email_active', table_name='users')
    op.drop_index('idx_user_created_at', table_name='users')
    op.drop_table('users')
    
    # Drop enum types
    op.execute("DROP TYPE reportstatus")
    op.execute("DROP TYPE userrole")
