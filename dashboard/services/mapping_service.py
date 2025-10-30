"""
CRM Mapping Service
Manages ID mappings between CRM system and POS system

This service handles the SystemMapping model which stores:
- Tenant UUID (CRM) <-> Business ID (POS)
- Customer UUID (CRM) <-> Customer ID (POS)
- Transaction UUID (CRM) <-> Transaction ID (POS)
"""

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from customers.models import SystemMapping, Customer
from tenants.models import Tenant
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


class MappingService:
    """Service for managing system ID mappings between CRM and POS"""

    @staticmethod
    def create_mapping(entity_type, crm_id, pos_id, tenant, metadata=None):
        """
        Create or update a mapping between CRM and POS entities
        
        Args:
            entity_type (str): Type of entity ('BUSINESS', 'CUSTOMER', 'TRANSACTION')
            crm_id (str): UUID in CRM system
            pos_id (str): ID in POS system
            tenant (Tenant): Tenant instance
            metadata (dict): Optional additional data
            
        Returns:
            SystemMapping: Created or updated mapping
        """
        try:
            # Check if mapping already exists
            mapping, created = SystemMapping.objects.update_or_create(
                entity_type=entity_type,
                crm_id=crm_id,
                defaults={
                    'pos_id': pos_id,
                    'tenant': tenant,
                    'last_synced_at': datetime.now(),
                    'sync_status': 'ACTIVE',
                    'metadata': metadata or {},
                }
            )
            
            action = "created" if created else "updated"
            logger.info(f"Mapping {action}: {entity_type} {crm_id} <-> {pos_id}")
            
            return mapping
            
        except Exception as e:
            logger.error(f"Error creating mapping: {e}")
            raise

    @staticmethod
    def get_pos_id(entity_type, crm_id):
        """
        Get POS ID from CRM ID
        
        Args:
            entity_type (str): Type of entity
            crm_id (str): CRM system UUID
            
        Returns:
            str: POS ID or None if not found
        """
        try:
            mapping = SystemMapping.objects.get(
                entity_type=entity_type,
                crm_id=crm_id
            )
            return mapping.pos_id
        except SystemMapping.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting POS ID: {e}")
            return None

    @staticmethod
    def get_crm_id(entity_type, pos_id):
        """
        Get CRM ID from POS ID
        
        Args:
            entity_type (str): Type of entity
            pos_id (str): POS system ID
            
        Returns:
            str: CRM UUID or None if not found
        """
        try:
            mapping = SystemMapping.objects.get(
                entity_type=entity_type,
                pos_id=pos_id
            )
            return mapping.crm_id
        except SystemMapping.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting CRM ID: {e}")
            return None

    @staticmethod
    def get_mapping(entity_type, crm_id=None, pos_id=None):
        """
        Get complete mapping record
        
        Args:
            entity_type (str): Type of entity
            crm_id (str): CRM system UUID (optional)
            pos_id (str): POS system ID (optional)
            
        Returns:
            SystemMapping: Complete mapping record or None
        """
        try:
            if crm_id:
                return SystemMapping.objects.select_related('tenant').get(
                    entity_type=entity_type,
                    crm_id=crm_id
                )
            elif pos_id:
                return SystemMapping.objects.select_related('tenant').get(
                    entity_type=entity_type,
                    pos_id=pos_id
                )
            else:
                raise ValueError("Either crm_id or pos_id must be provided")
        except SystemMapping.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting mapping: {e}")
            return None

    @staticmethod
    def get_tenant_mappings(tenant, entity_type=None):
        """
        Get all mappings for a tenant
        
        Args:
            tenant (Tenant): Tenant instance
            entity_type (str): Optional filter by entity type
            
        Returns:
            QuerySet: Mapping records
        """
        try:
            queryset = SystemMapping.objects.filter(tenant=tenant)
            if entity_type:
                queryset = queryset.filter(entity_type=entity_type)
            return queryset.order_by('-created_at')
        except Exception as e:
            logger.error(f"Error getting tenant mappings: {e}")
            return SystemMapping.objects.none()

    @staticmethod
    def delete_mapping(entity_type, crm_id=None, pos_id=None):
        """
        Delete a mapping
        
        Args:
            entity_type (str): Type of entity
            crm_id (str): CRM system UUID (optional)
            pos_id (str): POS system ID (optional)
            
        Returns:
            bool: Success status
        """
        try:
            if crm_id:
                SystemMapping.objects.filter(
                    entity_type=entity_type,
                    crm_id=crm_id
                ).delete()
            elif pos_id:
                SystemMapping.objects.filter(
                    entity_type=entity_type,
                    pos_id=pos_id
                ).delete()
            else:
                raise ValueError("Either crm_id or pos_id must be provided")
            return True
        except Exception as e:
            logger.error(f"Error deleting mapping: {e}")
            return False

    @staticmethod
    def update_mapping_status(entity_type, crm_id, status):
        """
        Update mapping status
        
        Args:
            entity_type (str): Type of entity
            crm_id (str): CRM system UUID
            status (str): New status ('ACTIVE', 'PENDING', 'FAILED', 'ARCHIVED')
            
        Returns:
            SystemMapping: Updated mapping or None
        """
        try:
            mapping = SystemMapping.objects.get(
                entity_type=entity_type,
                crm_id=crm_id
            )
            mapping.sync_status = status
            mapping.last_synced_at = datetime.now()
            mapping.save()
            return mapping
        except SystemMapping.DoesNotExist:
            logger.warning(f"Mapping not found: {entity_type} {crm_id}")
            return None
        except Exception as e:
            logger.error(f"Error updating mapping status: {e}")
            return None

    @staticmethod
    @transaction.atomic
    def create_tenant_mapping(tenant_uuid, business_id, metadata=None):
        """
        Create tenant-business mapping
        This is the primary mapping that must exist before any other mappings
        
        Args:
            tenant_uuid (str): CRM Tenant UUID
            business_id (str): POS Business ID
            metadata (dict): Optional metadata
            
        Returns:
            SystemMapping: Created mapping
        """
        try:
            # Verify tenant exists
            tenant = Tenant.objects.get(tenant_uuid=tenant_uuid)
            
            # Create mapping
            mapping = MappingService.create_mapping(
                entity_type='BUSINESS',
                crm_id=str(tenant_uuid),
                pos_id=business_id,
                tenant=tenant,
                metadata={
                    **(metadata or {}),
                    'tenant_name': tenant.name,
                    'created_at': datetime.now().isoformat(),
                }
            )
            
            # Update Tenant with external_business_id
            tenant.external_business_id = business_id
            tenant.last_synced_at = datetime.now()
            tenant.sync_status = 'ACTIVE'
            tenant.save()
            
            logger.info(f"Tenant mapping created: {tenant_uuid} <-> {business_id}")
            return mapping
            
        except Tenant.DoesNotExist:
            logger.error(f"Tenant not found: {tenant_uuid}")
            raise
        except Exception as e:
            logger.error(f"Error creating tenant mapping: {e}")
            raise

    @staticmethod
    @transaction.atomic
    def create_customer_mapping(customer_uuid, customer_id, tenant, metadata=None):
        """
        Create customer mapping
        
        Args:
            customer_uuid (str): CRM Customer UUID
            customer_id (str): POS Customer ID
            tenant (Tenant): Tenant instance
            metadata (dict): Optional metadata
            
        Returns:
            SystemMapping: Created mapping
        """
        try:
            # Verify customer exists
            customer = Customer.objects.get(
                customer_uuid=customer_uuid,
                tenant=tenant
            )
            
            # Create mapping
            mapping = MappingService.create_mapping(
                entity_type='CUSTOMER',
                crm_id=str(customer_uuid),
                pos_id=customer_id,
                tenant=tenant,
                metadata={
                    **(metadata or {}),
                    'customer_name': f"{customer.first_name} {customer.last_name}",
                    'email': customer.email,
                    'created_at': datetime.now().isoformat(),
                }
            )
            
            # Update Customer with external_id
            customer.external_id = customer_id
            customer.last_synced_at = datetime.now()
            customer.sync_status = 'ACTIVE'
            customer.save()
            
            logger.info(f"Customer mapping created: {customer_uuid} <-> {customer_id}")
            return mapping
            
        except Customer.DoesNotExist:
            logger.error(f"Customer not found: {customer_uuid}")
            raise
        except Exception as e:
            logger.error(f"Error creating customer mapping: {e}")
            raise

    @staticmethod
    def get_business_id(tenant_uuid):
        """
        Get POS business ID for a tenant
        
        Args:
            tenant_uuid (str): CRM Tenant UUID
            
        Returns:
            str: Business ID or None
        """
        return MappingService.get_pos_id('BUSINESS', str(tenant_uuid))

    @staticmethod
    def get_tenant_uuid(business_id):
        """
        Get tenant UUID from business ID
        
        Args:
            business_id (str): POS Business ID
            
        Returns:
            str: Tenant UUID or None
        """
        return MappingService.get_crm_id('BUSINESS', business_id)

    @staticmethod
    def get_mapping_stats(tenant):
        """
        Get mapping statistics for a tenant
        
        Args:
            tenant (Tenant): Tenant instance
            
        Returns:
            dict: Statistics object
        """
        try:
            total = SystemMapping.objects.filter(tenant=tenant).count()
            customer_count = SystemMapping.objects.filter(
                tenant=tenant,
                entity_type='CUSTOMER'
            ).count()
            transaction_count = SystemMapping.objects.filter(
                tenant=tenant,
                entity_type='TRANSACTION'
            ).count()
            active_count = SystemMapping.objects.filter(
                tenant=tenant,
                sync_status='ACTIVE'
            ).count()
            failed_count = SystemMapping.objects.filter(
                tenant=tenant,
                sync_status='FAILED'
            ).count()
            
            return {
                'total': total,
                'by_type': {
                    'business': 1,  # Should always be 1
                    'customer': customer_count,
                    'transaction': transaction_count,
                },
                'by_status': {
                    'active': active_count,
                    'failed': failed_count,
                }
            }
        except Exception as e:
            logger.error(f"Error getting mapping stats: {e}")
            return None

    @staticmethod
    def validate_mappings(tenant):
        """
        Validate mapping integrity
        Checks that all mapped entities still exist in the CRM system
        
        Args:
            tenant (Tenant): Tenant instance to validate
            
        Returns:
            dict: Validation results
        """
        try:
            mappings = MappingService.get_tenant_mappings(tenant)
            results = {
                'total': mappings.count(),
                'valid': 0,
                'invalid': []
            }
            
            for mapping in mappings:
                exists = False
                
                # Check if entity exists in CRM system
                if mapping.entity_type == 'CUSTOMER':
                    exists = Customer.objects.filter(
                        customer_uuid=mapping.crm_id,
                        tenant=tenant
                    ).exists()
                elif mapping.entity_type == 'BUSINESS':
                    exists = Tenant.objects.filter(
                        tenant_uuid=mapping.crm_id
                    ).exists()
                # Add TRANSACTION check when transaction model exists
                
                if exists:
                    results['valid'] += 1
                else:
                    results['invalid'].append({
                        'mapping_id': str(mapping.id),
                        'entity_type': mapping.entity_type,
                        'crm_id': mapping.crm_id,
                        'pos_id': mapping.pos_id,
                        'reason': 'Entity not found in CRM system'
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error validating mappings: {e}")
            raise

    @staticmethod
    def bulk_create_customer_mappings(customer_pairs, tenant):
        """
        Bulk create customer mappings
        
        Args:
            customer_pairs (list): List of tuples (customer_uuid, customer_id)
            tenant (Tenant): Tenant instance
            
        Returns:
            dict: Results with success/failure counts
        """
        results = {
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for customer_uuid, customer_id in customer_pairs:
            try:
                MappingService.create_customer_mapping(
                    customer_uuid=customer_uuid,
                    customer_id=customer_id,
                    tenant=tenant
                )
                results['success'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'customer_uuid': str(customer_uuid),
                    'customer_id': customer_id,
                    'error': str(e)
                })
                logger.error(f"Failed to create mapping for {customer_uuid}: {e}")
        
        return results


# Convenience functions for common operations

def get_or_create_customer_mapping(customer, pos_customer_id, tenant):
    """
    Get existing mapping or create new one for a customer
    
    Args:
        customer (Customer): Customer instance
        pos_customer_id (str): POS customer ID
        tenant (Tenant): Tenant instance
        
    Returns:
        SystemMapping: Mapping instance
    """
    mapping = MappingService.get_mapping(
        entity_type='CUSTOMER',
        crm_id=str(customer.customer_uuid)
    )
    
    if not mapping:
        mapping = MappingService.create_customer_mapping(
            customer_uuid=customer.customer_uuid,
            customer_id=pos_customer_id,
            tenant=tenant
        )
    
    return mapping


def sync_customer_ids(crm_customer_uuid, pos_customer_id):
    """
    Ensure customer IDs are synced in both directions
    
    Args:
        crm_customer_uuid (str): CRM customer UUID
        pos_customer_id (str): POS customer ID
        
    Returns:
        bool: Success status
    """
    try:
        customer = Customer.objects.get(customer_uuid=crm_customer_uuid)
        
        if not customer.external_id:
            customer.external_id = pos_customer_id
            customer.last_synced_at = datetime.now()
            customer.sync_status = 'ACTIVE'
            customer.save()
        
        return True
    except Customer.DoesNotExist:
        logger.error(f"Customer not found: {crm_customer_uuid}")
        return False
    except Exception as e:
        logger.error(f"Error syncing customer IDs: {e}")
        return False
